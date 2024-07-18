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
from collections import defaultdict

# Initialize the database
def init_db():
    conn = sqlite3.connect('pet_prices.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS pet_prices
                 (pet_name TEXT, tier TEXT, level TEXT, price INTEGER, timestamp DATETIME)''')
    conn.commit()
    conn.close()

# Call this function when your app starts
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
    search_term = request.form.get('search_term', '').strip().lower()
    selected_skill = request.form.get('skill', DEFAULT_SKILL)
    pet_list = load_pet_list("petlist.json")
    filtered_pet_list = filter_pets_by_name(pet_list, search_term)
    total_auctions = asyncio.run(fetch_auctions())
    output_list = calculate_profit(filtered_pet_list, total_auctions, selected_skill)
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
                batch_size = 40
                for i in range(0, total_pages, batch_size):
                    batch_tasks = [fetch_page(session, page, total_pages) for page in range(i, min(i + batch_size, total_pages))]
                    batch_results = await asyncio.gather(*batch_tasks)
                    for result in batch_results:
                        total_auctions.extend(result)

        logging.info("Fetch complete. Starting analysis...")
    except Exception as e:
        logging.error(f"Error fetching auctions: {str(e)}")

    return total_auctions

async def fetch_page(session, page, total_pages):
    retries = 3
    for attempt in range(retries):
        try:
            async with session.get(f"{API_URL}?page={page}") as response:
                data = await response.json()
                if "auctions" in data:
                    return data["auctions"]
                else:
                    logging.warning(f"Page {page + 1} has no 'auctions'")
                    return []
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(1)  # Wait for 1 second before retrying
            else:
                logging.error(f"Error fetching page {page + 1} after {retries} attempts: {str(e)}")
                return []

async def fetch_and_analyze_auctions(selected_skill):
    pet_list = load_pet_list("petlist.json")
    total_auctions = await fetch_auctions()
    output_list = calculate_profit(pet_list, total_auctions, selected_skill)
    return output_list

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

                    if low_pet and high_pet:
                        gross_profit = high_pet["starting_bid"] - low_pet["starting_bid"]
                        ah_tax = calculate_ah_tax(high_pet["starting_bid"])
                        claim_tax = gross_profit * 0.01
                        net_profit = gross_profit - ah_tax - claim_tax
                        profit_without_tax = gross_profit

                        low_day_avg, low_week_avg = get_average_prices(pet, tier, "low")
                        high_day_avg, high_week_avg = get_average_prices(pet, tier, "high")

                        coins_per_xp = net_profit / xp_required
                        coins_per_xp = round(coins_per_xp, 2)

                        coins_per_xp_note = None
                        if selected_skill in ["Mining", "Fishing", "Combat", "Farming", "Foraging"] and key != selected_skill:
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
                            "low_price": low_pet["starting_bid"],
                            "high_price": high_pet["starting_bid"],
                            "low_uuid": low_pet.get("uuid", "N/A"),
                            "high_uuid": high_pet.get("uuid", "N/A"),
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

def get_average_prices(pet_name, tier, level):
    conn = sqlite3.connect('pet_prices.db')
    c = conn.cursor()
    
    now = datetime.now()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    
    c.execute("""SELECT AVG(price) FROM pet_prices 
                 WHERE pet_name = ? AND tier = ? AND level = ? AND timestamp > ?""",
              (pet_name, tier, level, day_ago))
    day_avg = c.fetchone()[0]
    
    c.execute("""SELECT AVG(price) FROM pet_prices 
                 WHERE pet_name = ? AND tier = ? AND level = ? AND timestamp > ?""",
              (pet_name, tier, level, week_ago))
    week_avg = c.fetchone()[0]
    
    conn.close()
    
    return day_avg, week_avg


def update_pet_prices():
    print("Starting update_pet_prices")
    pet_list = load_pet_list("petlist.json")
    print("Pet list loaded")
    total_auctions = asyncio.run(fetch_auctions())
    print(f"Fetched {len(total_auctions)} auctions")
    
    # Create auctions_by_category dictionary
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
                        c.execute("INSERT INTO pet_prices VALUES (?, ?, ?, ?, ?)",
                                  (pet, tier, "low", low_pet["starting_bid"], datetime.now()))
                    if high_pet:
                        c.execute("INSERT INTO pet_prices VALUES (?, ?, ?, ?, ?)",
                                  (pet, tier, "high", high_pet["starting_bid"], datetime.now()))
    
    conn.commit()
    conn.close()
    print("Pet prices updated successfully")

def find_min_auction(auctions):
    return min((a for a in auctions if "Tier Boost" not in a.get("item_lore", "")),
               key=lambda x: x["starting_bid"], default=None)

scheduler = BackgroundScheduler()
scheduler.add_job(func=update_pet_prices, trigger="interval", minutes=15)
scheduler.start()

atexit.register(lambda: scheduler.shutdown()) 

if __name__ == '__main__':
    if not os.path.exists('images/pets'):
        os.makedirs('images/pets')
    app.run(host="0.0.0.0", port=8000, debug=True)