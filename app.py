import time

from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, session
from functools import wraps
import json
import aiohttp
import asyncio
from collections import defaultdict
from operator import itemgetter
import logging
from flask_cors import CORS
import os
import sqlite3
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from flask import send_from_directory

# Initialize the database
def init_db():
    conn = sqlite3.connect('pet_prices.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS pet_prices
                 (pet_name TEXT, rarity TEXT, level TEXT, price INTEGER, timestamp DATETIME, uuid TEXT)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_pet_prices ON pet_prices 
                 (pet_name, rarity, level, timestamp)''')
    conn.commit()
    conn.close()

def reset_db():
    conn = sqlite3.connect('pet_prices.db')
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS pet_prices")
    conn.commit()
    conn.close()
    init_db()


app = Flask(__name__, static_folder='static')
CORS(app)

app.config['SECRET_KEY'] = 'ihr_geheimer_schlüssel'
PASSWORD = '1404'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)

    return decorated_function


API_URL = "https://api.hypixel.net/v2/skyblock/auctions"
RARITY_COLORS = {
    "COMMON": "gray", "UNCOMMON": "green", "RARE": "blue",
    "EPIC": "purple", "LEGENDARY": "#FFB200", "MYTHIC": "#FF94E3"
}
DEFAULT_SKILL = "Mining"

XP_REQUIRED = {
    "COMMON": 5624785,
    "UNCOMMON": 8644220,
    "RARE": 12626665,
    "EPIC": 18608500,
    "LEGENDARY": 25353230,
    "MYTHIC": 25353230
}

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['password'] == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            error = 'Incorrect password. Please try again.'
            return render_template('login.html', error=error)
    return render_template('login.html')


@app.route('/')
@login_required
def index():
    return render_template('index.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))


@app.route('/analyze', methods=['POST'])
@login_required
def analyze_auctions():
    selected_skill = request.form.get('skill', DEFAULT_SKILL)
    return jsonify(asyncio.run(fetch_and_analyze_auctions(selected_skill)))


@app.route('/search', methods=['POST'])
@login_required
def search_pet():
    search_term = request.form.get('search_term', '').strip()
    selected_skill = request.form.get('skill', DEFAULT_SKILL)

    conn = sqlite3.connect('pet_prices.db')
    c = conn.cursor()

    query = """
    SELECT pet_name, rarity, 
           MIN(CASE WHEN level = 'low' THEN price END) as low_price,
           MAX(CASE WHEN level = 'high' THEN price END) as high_price,
           MIN(CASE WHEN level = 'low' THEN uuid END) as low_uuid,
           MAX(CASE WHEN level = 'high' THEN uuid END) as high_uuid,
           AVG(CASE WHEN level = 'low' AND timestamp > datetime('now', '-1 day') THEN price END) as low_day_avg,
           AVG(CASE WHEN level = 'low' AND timestamp > datetime('now', '-7 day') THEN price END) as low_week_avg,
           AVG(CASE WHEN level = 'high' AND timestamp > datetime('now', '-1 day') THEN price END) as high_day_avg,
           AVG(CASE WHEN level = 'high' AND timestamp > datetime('now', '-7 day') THEN price END) as high_week_avg
    FROM pet_prices
    WHERE LOWER(pet_name) LIKE ?
    GROUP BY pet_name, rarity
    """

    c.execute(query, (f"%{search_term}%",))
    results = c.fetchall()
    conn.close()

    pet_list = load_pet_list("petlist.json")
    output_list = []

    for row in results:
        pet_name, rarity, low_price, high_price, low_uuid, high_uuid, low_day_avg, low_week_avg, high_day_avg, high_week_avg = row

        # Ensure low_price and high_price are not None
        if low_price is None or high_price is None:
            continue

        # Find the skill for this pet
        skill = next((key for category in pet_list for key, pets in category.items() if pet_name in pets), None)

        if skill is None:
            continue  # Skip this pet if we can't determine its skill

        if pet_name == "Golden Dragon":
            xp_required = get_golden_dragon_xp()
        else:
            xp_required = XP_REQUIRED[rarity]

        gross_profit = high_price - low_price
        ah_tax = calculate_ah_tax(high_price)
        claim_tax = gross_profit * 0.01
        net_profit = gross_profit - ah_tax - claim_tax
        profit_without_tax = gross_profit

        coins_per_xp = net_profit / xp_required if xp_required else 0
        coins_per_xp = round(coins_per_xp, 2)

        coins_per_xp_note = None
        if selected_skill in ["Mining", "Fishing", "Combat", "Farming", "Foraging"] and skill != selected_skill:
            coins_per_xp /= 4
            coins_per_xp_note = f" /4 because its not a {selected_skill} Pet"
        elif selected_skill in ["Enchanting", "Alchemy"] and skill != selected_skill:
            coins_per_xp /= 12
            coins_per_xp_note = f" /12 not a {selected_skill} Pet"

        output_list.append({
            "name": pet_name,
            "rarity": rarity,
            "profit": int(net_profit),
            "profit_without_tax": int(profit_without_tax),
            "coins_per_xp": coins_per_xp,
            "coins_per_xp_note": coins_per_xp_note,
            "low_price": low_price,
            "high_price": high_price,
            "low_uuid": low_uuid,
            "high_uuid": high_uuid,
            "skill": skill,
            "low_day_avg": low_day_avg,
            "low_week_avg": low_week_avg,
            "high_day_avg": high_day_avg,
            "high_week_avg": high_week_avg
        })

    output_list.sort(key=lambda x: x["coins_per_xp"], reverse=True)
    return jsonify(output_list)



@app.route('/images/pets/<path:filename>')
def get_pet_image(filename):
    return send_from_directory('images/pets', filename)


async def fetch_auctions():
    total_auctions = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as response:
                data = await response.json()
                if "totalPages" not in data or "auctions" not in data:
                    raise ValueError("Invalid API response: 'totalPages' or 'auctions' missing")

                total_pages = data["totalPages"]

                # Fetch pages in batches to avoid overwhelming the server
                batch_size = 1
                logging.info("Starting API Calls")
                for i in range(0, total_pages, batch_size):
                    logging.debug(f"Fetching batch starting at page {i}")
                    batch_tasks = [fetch_page(session, page, total_pages) for page in range(i, min(i + batch_size, total_pages))]
                    batch_results = await asyncio.gather(*batch_tasks)

                    for result in batch_results:
                        total_auctions.extend(result)

                logging.info(f"Fetched {len(total_auctions)} auctions across {total_pages} pages")
    except Exception as e:
        logging.error(f"Error fetching auctions: {str(e)}")

    return total_auctions


async def fetch_page(session, page, total_pages):
    page_url = f"{API_URL}?page={page}"
    try:
        async with session.get(page_url) as response:
            logging.debug(f"Fetching page {page}/{total_pages}")
            if response.status != 200:
                logging.error(f"Failed to fetch page {page}: {response.status}")
                return []

            data = await response.json()
            if "auctions" not in data:
                logging.error(f"Invalid API response on page {page}: 'auctions' missing")
                return []

            logging.debug(f"Successfully fetched page {page}")
            return data["auctions"]
    except Exception as e:
        logging.error(f"Exception while fetching page {page}: {str(e)}")
        return []


async def fetch_and_analyze_auctions(selected_skill):
    pet_list = load_pet_list("petlist.json")
    pet_data = fetch_pet_data_from_db()
    output_list = calculate_profit_from_db(pet_list, pet_data, selected_skill)
    return output_list


def calculate_profit_from_db(pet_list, pet_data, selected_skill):
    logging.debug(f"Pet data structure: {json.dumps(pet_data, indent=2)}")
    new_pet_list = []
    for category in pet_list:
        for key, pets in category.items():
            for pet in pets:
                if pet not in pet_data:
                    logging.debug(f"Pet {pet} not found in pet_data")
                    continue

                for rarity, pet_info in pet_data[pet].items():
                    logging.debug(f"Processing {pet} with rarity {rarity}")

                    if pet == "Golden Dragon":
                        xp_required = get_golden_dragon_xp()
                    else:
                        xp_required = XP_REQUIRED[rarity]

                    low_price = pet_info.get("low_price", 0)
                    high_price = pet_info.get("high_price", 0)
                    low_uuid = pet_info.get("low_uuid", "N/A")
                    high_uuid = pet_info.get("high_uuid", "N/A")
                    low_day_avg = pet_info.get("low_day_avg", 0)
                    low_week_avg = pet_info.get("low_week_avg", 0)
                    high_day_avg = pet_info.get("high_day_avg", 0)
                    high_week_avg = pet_info.get("high_week_avg", 0)

                    # Only calculate profit if both low and high prices are available for the same rarity
                    if low_price and high_price:
                        gross_profit = high_price - low_price
                        ah_tax = calculate_ah_tax(high_price)
                        claim_tax = gross_profit * 0.01
                        net_profit = gross_profit - ah_tax - claim_tax
                        profit_without_tax = gross_profit

                        coins_per_xp = net_profit / xp_required if xp_required else 0
                        coins_per_xp = round(coins_per_xp, 2)

                        coins_per_xp_note = None
                        if selected_skill in ["Mining", "Fishing", "Combat", "Farming",
                                              "Foraging"] and key != selected_skill:
                            coins_per_xp /= 4
                            coins_per_xp_note = f" /4 because its not a {selected_skill} Pet"
                        elif selected_skill in ["Enchanting", "Alchemy"] and key != selected_skill:
                            coins_per_xp /= 12
                            coins_per_xp_note = f" /12 not a {selected_skill} Pet"

                        new_pet_list.append({
                            "name": pet,
                            "rarity": rarity,
                            "profit": int(net_profit),
                            "profit_without_tax": int(profit_without_tax),
                            "coins_per_xp": coins_per_xp,
                            "coins_per_xp_note": coins_per_xp_note,
                            "low_price": low_price,
                            "high_price": high_price,
                            "low_uuid": low_uuid,
                            "high_uuid": high_uuid,
                            "skill": key,
                            "low_day_avg": low_day_avg,
                            "low_week_avg": low_week_avg,
                            "high_day_avg": high_day_avg,
                            "high_week_avg": high_week_avg
                        })

    new_pet_list.sort(key=lambda x: x["coins_per_xp"], reverse=True)
    return new_pet_list

def load_pet_list(file_path):
    with open(file_path, "r") as f:
        return json.load(f)


def filter_pets_by_name(pet_list, search_term):
    filtered_pet_list = []
    for category in pet_list:
        filtered_category = {k: [pet for pet in v if search_term in pet.lower()] for k, v in category.items()}
        filtered_pet_list.append(filtered_category)
    return filtered_pet_list


def calculate_profit(pet_list, total_auctions, selected_skill):
    auctions_by_category = defaultdict(list)
    for auction in total_auctions:
        if not auction.get("bin"):
            continue
        tier = auction.get("tier")
        item_name = auction.get("item_name")
        auctions_by_category[(tier, item_name)].append(auction)

    pet_data = []
    for category in pet_list:
        for key, pets in category.items():
            for tier in RARITY_COLORS.keys():
                for pet in pets:
                    pet_data.append((pet, tier, "low"))
                    pet_data.append((pet, tier, "high"))

    average_prices = get_average_prices_batch(pet_data)

    new_pet_list = []
    for category in pet_list:
        for key, pets in category.items():
            for tier in RARITY_COLORS.keys():
                for pet in pets:
                    if pet == "Golden Dragon":
                        low_lvl, high_lvl = "[Lvl 102] Golden Dragon", "[Lvl 200] Golden Dragon"
                        xp_required = get_golden_dragon_xp()
                    else:
                        low_lvl, high_lvl = f"[Lvl 1] {pet}", f"[Lvl 100] {pet}"
                        xp_required = XP_REQUIRED[tier]

                    low_pet = find_min_auction(auctions_by_category.get((tier, low_lvl), []))
                    high_pet = find_min_auction(auctions_by_category.get((tier, high_lvl), []))

                    low_day_avg, low_week_avg = average_prices.get((pet, tier, "low"), (0, 0))
                    high_day_avg, high_week_avg = average_prices.get((pet, tier, "high"), (0, 0))

                    if low_pet and high_pet:
                        low_price = low_pet["starting_bid"]
                        high_price = high_pet["starting_bid"]
                        low_uuid = low_pet.get("uuid", "N/A")
                        high_uuid = high_pet.get("uuid", "N/A")
                    elif low_day_avg and high_day_avg:
                        low_price = low_day_avg
                        high_price = high_day_avg
                        low_uuid = "N/A"
                        high_uuid = "N/A"
                    else:
                        continue  # Skip this pet if we have no data

                    gross_profit = high_price - low_price
                    ah_tax = calculate_ah_tax(high_price)
                    claim_tax = gross_profit * 0.01
                    net_profit = gross_profit - ah_tax - claim_tax
                    profit_without_tax = gross_profit

                    coins_per_xp = net_profit / xp_required
                    coins_per_xp = round(coins_per_xp, 2)

                    coins_per_xp_note = None
                    if selected_skill in ["Mining", "Fishing", "Combat", "Farming",
                                          "Foraging"] and key != selected_skill:
                        coins_per_xp /= 4
                        coins_per_xp_note = f" /4 because its not a {selected_skill} Pet"
                    elif selected_skill in ["Enchanting", "Alchemy"] and key != selected_skill:
                        coins_per_xp /= 12
                        coins_per_xp_note = f" /12 not a {selected_skill} Pet"

                    new_pet_list.append({
                        "name": pet,
                        "tier": tier,
                        "profit": int(net_profit),
                        "profit_without_tax": int(profit_without_tax),
                        "coins_per_xp": coins_per_xp,
                        "coins_per_xp_note": coins_per_xp_note,
                        "low_price": low_price,
                        "high_price": high_price,
                        "low_uuid": low_uuid,
                        "high_uuid": high_uuid,
                        "skill": key,
                        "low_day_avg": low_day_avg,
                        "low_week_avg": low_week_avg,
                        "high_day_avg": high_day_avg,
                        "high_week_avg": high_week_avg
                    })

    new_pet_list.sort(key=itemgetter("coins_per_xp"), reverse=True)
    return new_pet_list


def calculate_ah_tax(price):
    if price < 10000000:
        return price * 0.01
    elif price < 100000000:
        return price * 0.02
    else:
        return price * 0.025


def get_golden_dragon_xp():
    with open("GoldenDragon.json", "r") as f:
        data = json.load(f)
    levels = data["levels"]
    return levels[-1]["totalXP"] - levels[0]["totalXP"]


def get_average_prices_batch(pet_data):
    conn = sqlite3.connect('pet_prices.db')
    c = conn.cursor()

    now = datetime.now()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    placeholders = ','.join(['(?,?,?)' for _ in pet_data])
    query = f"""
    SELECT pet_name, rarity, level,
           AVG(CASE WHEN timestamp > ? THEN price ELSE NULL END) as day_avg,
           AVG(CASE WHEN timestamp > ? THEN price ELSE NULL END) as week_avg
    FROM pet_prices
    WHERE (pet_name, rarity, level) IN ({placeholders})
    GROUP BY pet_name, rarity, level
    """

    params = [day_ago, week_ago]
    params.extend([item for sublist in pet_data for item in sublist])

    c.execute(query, params)
    results = c.fetchall()

    conn.close()
    return {(row[0], row[1], row[2]): (row[3], row[4]) for row in results}


def fetch_pet_data_from_db():
    logging.debug("Starting fetch_pet_data_from_db")
    conn = sqlite3.connect('pet_prices.db')
    c = conn.cursor()

    c.execute("""
    SELECT pet_name, rarity, level, price, uuid,
           AVG(CASE WHEN timestamp > datetime('now', '-1 day') THEN price ELSE NULL END) OVER (PARTITION BY pet_name, rarity, level) as day_avg,
           AVG(CASE WHEN timestamp > datetime('now', '-7 day') THEN price ELSE NULL END) OVER (PARTITION BY pet_name, rarity, level) as week_avg
    FROM pet_prices
    WHERE (pet_name, rarity, level, timestamp) IN (
        SELECT pet_name, rarity, level, MAX(timestamp)
        FROM pet_prices
        GROUP BY pet_name, rarity, level
    )
    """)

    results = c.fetchall()
    conn.close()

    pet_data = {}
    for row in results:
        pet_name, rarity, level, price, uuid, day_avg, week_avg = row
        if pet_name not in pet_data:
            pet_data[pet_name] = {}
        if rarity not in pet_data[pet_name]:
            pet_data[pet_name][rarity] = {}
        pet_data[pet_name][rarity][f"{level}_price"] = price
        pet_data[pet_name][rarity][f"{level}_uuid"] = uuid
        pet_data[pet_name][rarity][f"{level}_day_avg"] = day_avg
        pet_data[pet_name][rarity][f"{level}_week_avg"] = week_avg

    logging.debug(f"Fetched data for {len(pet_data)} pets")
    for pet, rarities in pet_data.items():
        logging.debug(f"Pet: {pet}, Rarities: {list(rarities.keys())}")

    return pet_data

def update_pet_prices():
    print("Starting update_pet_prices")
    pet_list = load_pet_list("petlist.json")
    print("Pet list loaded")
    total_auctions = asyncio.run(fetch_auctions())
    print(f"Fetched {len(total_auctions)} auctions")

    auctions_by_category = defaultdict(list)
    for auction in total_auctions:
        if not auction.get("bin"):
            continue
        tier = auction.get("tier")
        item_name = auction.get("item_name")
        auctions_by_category[(tier, item_name)].append(auction)

    print(f"Categorized {len(auctions_by_category)} auction types")

    conn = sqlite3.connect('pet_prices.db')
    c = conn.cursor()

    for category in pet_list:
        for key, pets in category.items():
            for tier in RARITY_COLORS.keys():
                for pet in pets:
                    if pet == "Golden Dragon":
                        low_lvl, high_lvl = "[Lvl 102] Golden Dragon", "[Lvl 200] Golden Dragon"
                    else:
                        low_lvl, high_lvl = f"[Lvl 1] {pet}", f"[Lvl 100] {pet}"

                    low_pet = find_min_auction(auctions_by_category.get((tier, low_lvl), []))
                    high_pet = find_min_auction(auctions_by_category.get((tier, high_lvl), []))

                    if low_pet:
                        c.execute("INSERT INTO pet_prices VALUES (?, ?, ?, ?, ?, ?)",
                                  (pet, tier, "low", low_pet["starting_bid"], datetime.now(),
                                   low_pet.get("uuid", "N/A")))
                    if high_pet:
                        c.execute("INSERT INTO pet_prices VALUES (?, ?, ?, ?, ?, ?)",
                                  (pet, tier, "high", high_pet["starting_bid"], datetime.now(),
                                   high_pet.get("uuid", "N/A")))

    conn.commit()
    conn.close()
    print("Pet prices updated successfully")


def find_min_auction(auctions):
    return min((a for a in auctions if "Tier Boost" not in a.get("item_lore", "")),
               key=lambda x: x["starting_bid"], default=None)

scheduler = BackgroundScheduler()
scheduler.add_job(func=update_pet_prices, trigger="interval", minutes=5)
scheduler.start()

atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    pet_data = fetch_pet_data_from_db()
    logging.debug("Pet data structure:")
    logging.debug(json.dumps(pet_data, indent=2))

    init_db()
    app.run(host="0.0.0.0", port=8000, debug=True)
    #update_pet_prices()
    if not os.path.exists('images/pets'):
        os.makedirs('images/pets')
