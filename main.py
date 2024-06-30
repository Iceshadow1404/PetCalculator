import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
import asyncio
import aiohttp
from typing import List, Dict
import logging
from collections import defaultdict

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
        self.master.geometry("1400x700")  # Increased width of the window

        self.label = tk.Label(self.master, text="Auction Analyzer", font=("Arial", 24), fg='white', bg='black')
        self.label.pack(pady=10)

        self.setup_search_bar()
        self.setup_skill_dropdown()
        self.setup_analyze_button()
        self.setup_output_text()
        self.setup_progress_bar()  # Setup progress bar

    def setup_search_bar(self):
        self.search_frame = tk.Frame(self.master, bg='black')
        self.search_frame.pack(pady=5, padx=10, anchor='e')

        self.search_label = tk.Label(self.search_frame, text="Search Pet:", font=("Arial", 12), fg='white', bg='black')
        self.search_label.pack(side='left')

        self.search_entry = tk.Entry(self.search_frame, font=("Arial", 12), bg='white', fg='black')
        self.search_entry.pack(side='left', padx=5)

        self.search_button = tk.Button(self.search_frame, text="Search", command=self.search_pet, bg='white', fg='black', font=("Arial", 12))
        self.search_button.pack(side='left')

    def setup_skill_dropdown(self):
        self.skill_label = tk.Label(self.master, text="Select Skill:", font=("Arial", 12), fg='white', bg='black')
        self.skill_label.pack()

        self.skill_options = ["Mining", "Fishing", "Combat", "Farming", "Foraging", "Enchanting", "Alchemy"]
        self.selected_skill = tk.StringVar(self.master)
        self.selected_skill.set(DEFAULT_SKILL)

        self.skill_dropdown = tk.OptionMenu(self.master, self.selected_skill, *self.skill_options,
                                            command=self.on_skill_selected)
        self.skill_dropdown.config(bg='white', fg='black', font=("Arial", 12))
        self.skill_dropdown.pack(pady=5)

    def setup_analyze_button(self):
        self.button = tk.Button(self.master, text="Analyze Auctions", command=self.analyze_auctions, bg='white',
                                fg='black', font=("Arial", 16))
        self.button.pack(pady=10)

    def setup_output_text(self):
        self.output_frame = tk.Frame(self.master, bg='black')
        self.output_frame.pack(padx=10, pady=10)

        self.output_text = scrolledtext.ScrolledText(self.output_frame, width=140, height=30, bg='black', fg='white',
                                                     font=("Courier", 12))  # Increased width to 140
        self.output_text.pack()

        for rarity, color in RARITY_COLORS.items():
            self.output_text.tag_configure(rarity, background=color)

    def setup_progress_bar(self):
        self.progress_bar = ttk.Progressbar(self.master, orient='horizontal', length=200, mode='determinate')
        self.progress_bar.pack(pady=10)

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
                    self.progress_bar['maximum'] = total_pages

                    tasks = [self.fetch_page(session, i, total_pages) for i in range(total_pages)]
                    await asyncio.gather(*tasks)

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
                self.progress_bar['value'] = page + 1
                logging.info(f"Fetched page {page + 1}/{total_pages}")  # Log progress
        except Exception as e:
            logging.error(f"Error fetching page {page + 1}: {str(e)}")

    def analyze_auctions(self):
        try:
            self.pet_list = self.load_pet_list("petlist.json")
            asyncio.run(self.fetch_auctions())
            output_list = self.calculate_profit(self.pet_list, self.total_auctions, self.selected_skill.get())
            formatted_output = self.format_output(output_list)
            self.update_output_text(formatted_output)
            logging.info("Auction analysis completed.")  # Log completion
        except Exception as e:
            logging.error(f"An error occurred during analysis: {str(e)}")
            messagebox.showerror("Error", f"An error occurred during analysis: {str(e)}")

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
        # Group auctions by 'tier' and 'item_name'
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
                        low_lvl, high_lvl = f"[Lvl 1] {pet}", f"[Lvl 100] {pet}"
                        low_pet = self.find_min_auction(auctions_by_category.get((tier, low_lvl), []))
                        high_pet = self.find_min_auction(auctions_by_category.get((tier, high_lvl), []))

                        if low_pet and high_pet:
                            gross_profit = high_pet["starting_bid"] - low_pet["starting_bid"]
                            ah_tax = self.calculate_ah_tax(high_pet["starting_bid"])
                            claim_tax = gross_profit * 0.01
                            net_profit = gross_profit - ah_tax - claim_tax
                            profit_without_tax = gross_profit

                            # Calculate coins per XP based on the XP required for the rarity
                            coins_per_xp = net_profit / XP_REQUIRED[tier]

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

        return sorted(new_pet_list, key=lambda p: p["profit"], reverse=True)

    def find_min_auction(self, auctions):
        return min((a for a in auctions if "Tier Boost" not in a.get("item_lore", "")),
                   key=lambda x: x["starting_bid"], default=None)

    def format_output(self, output_list):
        return "\n".join(
            f"Pet: {item['name']} Rarity: {item['tier']} "
            f"Profit: {self.format_price(item['profit'])} "
            f"Profit (without tax): {self.format_price(item['profit_without_tax'])} "
            f"Coins per XP: {self.format_price(item['coins_per_xp'])} "
            f"LVL 1 Price: {self.format_price(item['low_price'])} "
            f"LVL 100 Price: {self.format_price(item['high_price'])}"
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
    def format_price(price):
        if price >= 1e6:
            return f"{price / 1e6:.1f}m"
        elif price >= 1e3:
            return f"{price / 1e3:.1f}k"
        return str(price)

    @staticmethod
    def calculate_ah_tax(price):
        if price < 10000000:
            return price * 0.01
        elif price < 100000000:
            return price * 0.02
        else:
            return price * 0.025


def main():
    root = tk.Tk()
    AuctionAnalyzerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
