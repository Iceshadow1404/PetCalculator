import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
import asyncio
import aiohttp
import logging
from collections import defaultdict
from operator import itemgetter

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
API_URL = "https://api.hypixel.net/v2/skyblock/auctions"
RARITY_COLORS = {
    "COMMON": "gray", "UNCOMMON": "green", "RARE": "blue",
    "EPIC": "purple", "LEGENDARY": "#FFB200", "MYTHIC": "#FF94E3"
}
DEFAULT_SKILL = "Mining"

# XP required per rarity
XP_REQUIRED = {
    "COMMON": 5624785,
    "UNCOMMON": 8644220,
    "RARE": 12626665,
    "EPIC": 18608500,
    "LEGENDARY": 25353230,
    "MYTHIC": 25353230
}


class AuctionAnalyzerApp:
    def __init__(self, master):
        self.master = master
        self.setup_ui()
        self.total_auctions = []
        self.pet_list = []

    def setup_ui(self):
        self.master.title("Auction Analyzer")
        self.master.configure(bg='black')
        self.master.geometry("1400x800")  # Increased height

        # Configure rows and columns to be stretchable
        self.master.grid_rowconfigure(3, weight=1)
        self.master.grid_columnconfigure(0, weight=1)

        self.label = tk.Label(self.master, text="Auction Analyzer", font=("Arial", 24), fg='white', bg='black')
        self.label.grid(row=0, column=0, pady=10)

        self.setup_search_bar()
        self.setup_skill_dropdown()
        self.setup_output_text()
        self.setup_status_label()

    def setup_search_bar(self):
        self.search_frame = tk.Frame(self.master, bg='black')
        self.search_frame.grid(row=1, column=0, pady=5, padx=10, sticky='e')

        self.search_label = tk.Label(self.search_frame, text="Search Pet:", font=("Arial", 12), fg='white', bg='black')
        self.search_label.pack(side='left')

        self.search_entry = tk.Entry(self.search_frame, font=("Arial", 12), bg='white', fg='black')
        self.search_entry.pack(side='left', padx=5)

        self.search_button = tk.Button(self.search_frame, text="Search", command=self.search_pet, bg='white',
                                       fg='black', font=("Arial", 12))
        self.search_button.pack(side='left')

    def setup_skill_dropdown(self):
        self.skill_frame = tk.Frame(self.master, bg='black')
        self.skill_frame.grid(row=2, column=0, pady=5)

        self.skill_label = tk.Label(self.skill_frame, text="Select Skill:", font=("Arial", 12), fg='white', bg='black')
        self.skill_label.pack(side='left')

        self.skill_options = ["Mining", "Fishing", "Combat", "Farming", "Foraging", "Enchanting", "Alchemy"]
        self.selected_skill = tk.StringVar(self.master)
        self.selected_skill.set(DEFAULT_SKILL)

        self.skill_dropdown = tk.OptionMenu(self.skill_frame, self.selected_skill, *self.skill_options,
                                            command=self.on_skill_selected)
        self.skill_dropdown.config(bg='white', fg='black', font=("Arial", 12))
        self.skill_dropdown.pack(side='left', padx=5)

        self.button = tk.Button(self.skill_frame, text="Analyze Auctions", command=self.analyze_auctions, bg='white',
                                fg='black', font=("Arial", 16))
        self.button.pack(side='left', padx=10)

    def setup_output_text(self):
        self.output_frame = tk.Frame(self.master, bg='black')
        self.output_frame.grid(row=3, column=0, padx=10, pady=10, sticky='nsew')

        self.output_text = scrolledtext.ScrolledText(self.output_frame, width=140, height=30, bg='black', fg='white',
                                                     font=("Courier", 14))
        self.output_text.pack(expand=True, fill='both')

        for rarity, color in RARITY_COLORS.items():
            self.output_text.tag_configure(rarity, background=color)

    def setup_status_label(self):
        self.status_label = tk.Label(self.master, text="", fg='white', bg='black')
        self.status_label.grid(row=4, column=0, pady=5)

    def on_skill_selected(self, event=None):
        self.total_auctions = []
        self.analyze_auctions()

    async def fetch_auctions(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(API_URL) as response:
                    data = await response.json()
                    if "totalPages" not in data or "auctions" not in data:
                        raise ValueError("Invalid API response: 'totalPages' or 'auctions' missing")

                    total_pages = data["totalPages"]

                    tasks = [self.fetch_page(session, i, total_pages) for i in range(total_pages)]
                    await asyncio.gather(*tasks)

            self.status_label.config(text="Fetch complete. Starting analysis...")
            self.master.update_idletasks()

        except Exception as e:
            logging.error(f"Error fetching auctions: {str(e)}")
            messagebox.showerror("Error", f"Failed to fetch auctions: {str(e)}")


    async def fetch_page(self, session, page, total_pages):
        try:
            async with session.get(f"{API_URL}?page={page}") as response:
                data = await response.json()
                if "auctions" in data:
                    self.total_auctions.extend(data["auctions"])
                else:
                    logging.warning(f"Page {page + 1} has no 'auctions'")
                self.status_label.config(text=f"Fetched page {page + 1}/{total_pages}")
                self.master.update_idletasks()
                logging.info(f"Fetched page {page + 1}/{total_pages}")
        except Exception as e:
            logging.error(f"Error fetching page {page + 1}: {str(e)}")

    def analyze_auctions(self):
        try:
            self.status_label.config(text="Loading pet list...")
            self.master.update_idletasks()
            self.pet_list = self.load_pet_list("petlist.json")

            self.status_label.config(text="Fetching auctions...")
            self.master.update_idletasks()
            asyncio.run(self.fetch_auctions())

            self.status_label.config(text="Calculating profits...")
            self.master.update_idletasks()
            output_list = self.calculate_profit(self.pet_list, self.total_auctions, self.selected_skill.get())

            self.status_label.config(text="Formatting output...")
            self.master.update_idletasks()
            formatted_output = self.format_output(output_list)

            self.status_label.config(text="Updating display...")
            self.master.update_idletasks()
            self.update_output_text(formatted_output)

            self.status_label.config(text="Analysis complete.")
            logging.info("Auction analysis completed.")
        except Exception as e:
            logging.error(f"An error occurred during analysis: {str(e)}")
            messagebox.showerror("Error", f"An error occurred during analysis: {str(e)}")
            self.status_label.config(text="Error occurred during analysis.")

    def search_pet(self):
        search_term = self.search_entry.get().strip().lower()
        filtered_pet_list = self.filter_pets_by_name(self.pet_list, search_term)
        output_list = self.calculate_profit(filtered_pet_list, self.total_auctions, self.selected_skill.get())
        formatted_output = self.format_output(output_list)
        self.update_output_text(formatted_output)

    @staticmethod
    def filter_pets_by_name(pet_list, search_term):
        filtered_pet_list = []
        for category in pet_list:
            filtered_category = {k: [pet for pet in v if search_term in pet.lower()] for k, v in category.items()}
            filtered_pet_list.append(filtered_category)
        return filtered_pet_list

    @staticmethod
    def load_pet_list(file_path):
        with open(file_path, "r") as f:
            return json.load(f)

    def calculate_profit(self, pet_list, total_auctions, selected_skill):
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
                            xp_required = self.get_golden_dragon_xp()
                        else:
                            low_lvl, high_lvl = f"[Lvl 1] {pet}", f"[Lvl 100] {pet}"
                            xp_required = XP_REQUIRED[tier]

                        low_pet = self.find_min_auction(auctions_by_category.get((tier, low_lvl), []))
                        high_pet = self.find_min_auction(auctions_by_category.get((tier, high_lvl), []))

                        if low_pet and high_pet:
                            gross_profit = high_pet["starting_bid"] - low_pet["starting_bid"]
                            ah_tax = self.calculate_ah_tax(high_pet["starting_bid"])
                            claim_tax = gross_profit * 0.01
                            net_profit = gross_profit - ah_tax - claim_tax
                            profit_without_tax = gross_profit

                            coins_per_xp = net_profit / xp_required
                            coins_per_xp = round(coins_per_xp, 2)

                            if selected_skill in ["Mining", "Fishing", "Combat", "Farming", "Foraging"] and key != selected_skill:
                                net_profit /= 3
                                profit_without_tax /= 3
                                coins_per_xp /= 3
                            elif selected_skill in ["Enchanting", "Alchemy"] and key != selected_skill:
                                net_profit /= 12
                                profit_without_tax /= 12
                                coins_per_xp /= 12

                            new_pet_list.append({
                                "name": pet,
                                "tier": tier,
                                "profit": int(net_profit),
                                "profit_without_tax": int(profit_without_tax),
                                "coins_per_xp": coins_per_xp,
                                "low_price": low_pet["starting_bid"],
                                "high_price": high_pet["starting_bid"]
                            })

        new_pet_list.sort(key=itemgetter("coins_per_xp"), reverse=True)
        return new_pet_list

    def find_min_auction(self, auctions):
        return min((a for a in auctions if "Tier Boost" not in a.get("item_lore", "")),
                   key=lambda x: x["starting_bid"], default=None)

    def format_output(self, output_list):
        return "\n".join(
            f"Pet: {item['name']} Rarity: {item['tier']} "
            f"Profit: {self.format_price(item['profit'])} "
            f"Profit (w/o tax): {self.format_price(item['profit_without_tax'])} "
            f"Coins per XP: {self.format_price(item['coins_per_xp'], is_coins_per_xp=True)} "
            f"{'LVL 102' if item['name'] == 'Golden Dragon' else 'LVL 1'} Price: {self.format_price(item['low_price'])} "
            f"LVL {200 if item['name'] == 'Golden Dragon' else 100} Price: {self.format_price(item['high_price'])}"
            for item in output_list
        )

    def update_output_text(self, formatted_output):
        self.output_text.delete('1.0', tk.END)
        for line in formatted_output.splitlines():
            rarity = line.split("Rarity: ")[-1].split()[0]
            self.insert_colored_text(line, rarity)

    def insert_colored_text(self, text, tag):
        self.output_text.insert(tk.END, text + "\n", tag)
        start_index = self.output_text.index(tk.END + "-2l")
        end_index = self.output_text.index(tk.END + "-1l")
        self.add_outline(start_index, end_index)

    def add_outline(self, start_index, end_index):
        line_count = int(start_index.split('.')[0]), int(end_index.split('.')[0])
        for line in range(line_count[0], line_count[1] + 1):
            self.output_text.tag_add('outline', f"{line}.0", f"{line}.end")
            self.output_text.tag_config('outline', foreground='black')

    @staticmethod
    def format_price(price, is_coins_per_xp=False):
        if isinstance(price, str):
            return price

        if is_coins_per_xp:
            return f"{price:.2f}".rstrip('0').rstrip('.')

        if price >= 1e6:
            return f"{price / 1e6:.1f}m".rstrip('0').rstrip('.')
        elif price >= 1e3:
            return f"{price / 1e3:.1f}k".rstrip('0').rstrip('.')
        else:
            return f"{price:.1f}".rstrip('0').rstrip('.')

    @staticmethod
    def calculate_ah_tax(price):
        if price < 10000000:
            return price * 0.01
        elif price < 100000000:
            return price * 0.02
        else:
            return price * 0.025

    @staticmethod
    def get_golden_dragon_xp():
        with open("GoldenDragon.json", "r") as f:
            data = json.load(f)
        levels = data["levels"]
        return levels[-1]["totalXP"] - levels[0]["totalXP"]


def main():
    root = tk.Tk()
    AuctionAnalyzerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
