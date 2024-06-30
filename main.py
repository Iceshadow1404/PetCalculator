import tkinter as tk
from tkinter import scrolledtext
from tkinter import messagebox
import json
import requests

# Configuration
SKILL = "Mining"
API_URL = "https://api.hypixel.net/v2/skyblock/auctions"

# Dictionary for color mapping based on rarity
RARITY_COLORS = {
    "COMMON": "gray",
    "UNCOMMON": "green",
    "RARE": "blue",
    "EPIC": "purple",
    "LEGENDARY": "#FFB200",
    "MYTHIC": "#FF94E3"
}


class AuctionAnalyzerApp:
    def __init__(self, master):
        self.master = master
        master.title("Auction Analyzer")
        master.configure(bg='black')

        self.label = tk.Label(master, text="Auction Analyzer", font=("Arial", 24), fg='white', bg='black')
        self.label.pack(pady=10)

        self.button = tk.Button(master, text="Analyze Auctions", command=self.analyze_auctions, bg='white', fg='black',
                                font=("Arial", 16))
        self.button.pack(pady=10)

        self.progress_label = tk.Label(master, text="", font=("Arial", 12), fg='white', bg='black')
        self.progress_label.pack()

        # Create a Frame to hold the scrolledtext with black background
        self.output_frame = tk.Frame(master, bg='black')
        self.output_frame.pack(padx=10, pady=10)

        self.output_text = scrolledtext.ScrolledText(self.output_frame, width=100, height=30, bg='black', fg='white',
                                                     font=("Courier", 12))
        self.output_text.pack()

        # Initialize total_auctions attribute
        self.total_auctions = []

        # Configure tags for different rarity colors
        for rarity, color in RARITY_COLORS.items():
            self.output_text.tag_configure(rarity, background=color)

    def analyze_auctions(self):
        try:
            pet_list = load_pet_list("petlist.json")

            if not self.total_auctions:  # Fetch auctions only if total_auctions is empty
                self.total_auctions = fetch_auctions(self.master, self.progress_label)

            output_list = calculate_profit(pet_list, self.total_auctions)
            formatted_output = self.format_output(output_list)
            self.update_output_text(formatted_output)

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")

    def format_output(self, output_list):
        formatted_output = []
        for item in output_list:
            profit = format_profit(item["profit"])
            low_price = format_price(item["low_price"])
            high_price = format_price(item["high_price"])
            rarity = item["tier"]

            # Append formatted string with rarity tag
            formatted_output.append(
                f"Pet: {item['name']} Rarity: {item['tier']} Profit: {profit} LVL 1 Price: {low_price} LVL 100 Price: {high_price}"
            )

        return "\n".join(formatted_output)

    def update_output_text(self, formatted_output):
        self.output_text.delete('1.0', tk.END)  # Clear previous output

        # Insert formatted output line by line with proper tags for rarity colors
        for line in formatted_output.splitlines():
            # Extract rarity from line
            rarity = line.split("Rarity: ")[-1].split()[0]
            self.insert_colored_text(line, rarity)  # Insert line with appropriate tag

    def insert_colored_text(self, text, tag):
        self.output_text.insert(tk.END, text + "\n", tag)  # Insert line with appropriate tag

        # Get the indices of the inserted text
        start_index = self.output_text.index(tk.END + "-2l")
        end_index = self.output_text.index(tk.END + "-1l")

        # Add a thicker black outline around the inserted line
        self.add_outline(start_index, end_index)

    def add_outline(self, start_index, end_index):
        # Iterate over each line and add a fake outline effect
        line_count = int(start_index.split('.')[0]), int(end_index.split('.')[0])
        for line in range(line_count[0], line_count[1] + 1):
            # Add 1.5px thick black border on top and bottom of each line
            self.output_text.tag_add('outline', f"{line}.0", f"{line}.end")
            self.output_text.tag_config('outline', foreground='black')


def fetch_auctions(master, progress_label):
    try:
        session = requests.Session()
        res = session.get(API_URL)
        response = res.json()

        if "totalPages" not in response or "auctions" not in response:
            raise ValueError("Invalid API response: 'totalPages' or 'auctions' missing")

        pages = response["totalPages"]
        total_auctions = []

        for i in range(1, pages + 1):
            print(f"Fetching page {i}")
            progress_label.config(text=f"Fetching page {i}/{pages}")
            master.update()  # Update GUI to show progress label change
            res_new = session.get(f"{API_URL}?page={i}")
            response_new = res_new.json()
            if "auctions" in response_new:
                total_auctions.extend(response_new["auctions"])
            else:
                print(f"Page {i} has no 'auctions'")

        progress_label.config(text="Auction check complete")
        master.update()  # Update GUI to show final progress label

        return total_auctions

    except requests.RequestException as e:
        messagebox.showerror("Error", f"An error occurred while fetching auctions: {str(e)}")
        return []
    except ValueError as ve:
        messagebox.showerror("Error", str(ve))
        return []


def load_pet_list(file_path):
    with open(file_path, "r") as f:
        return json.load(f)


def calculate_profit(pet_list, total_auctions):
    new_pet_list = []

    def find_best_pets(tier, pets):
        for pet in pets:
            low_lvl, high_lvl = f"[Lvl 1] {pet}", f"[Lvl 100] {pet}"
            low_pet, high_pet = None, None

            for auction in total_auctions:
                if auction.get("bin") and auction.get("tier") == tier and "Tier Boost" not in auction.get("item_lore",
                                                                                                          ""):
                    if auction.get("item_name") == low_lvl:
                        if low_pet is None or auction["starting_bid"] < low_pet["starting_bid"]:
                            low_pet = auction
                    elif auction.get("item_name") == high_lvl:
                        if high_pet is None or auction["starting_bid"] < high_pet["starting_bid"]:
                            high_pet = auction

            try:
                profit = high_pet["starting_bid"] - low_pet["starting_bid"]
            except TypeError:
                profit = 0

            if key != SKILL:
                profit /= 3
                if key == "Alchemy":
                    profit /= 4

            new_pet_list.append({
                "name": pet,
                "tier": tier,
                "profit": int(profit),
                "low_price": low_pet["starting_bid"] if low_pet else 0,
                "high_price": high_pet["starting_bid"] if high_pet else 0
            })

    for category in pet_list:
        for key, pets in category.items():
            find_best_pets("COMMON", pets)
            find_best_pets("UNCOMMON", pets)
            find_best_pets("RARE", pets)
            find_best_pets("EPIC", pets)
            find_best_pets("LEGENDARY", pets)
            find_best_pets("MYTHIC", pets)

    return sorted(new_pet_list, key=lambda p: p["profit"], reverse=True)


def format_profit(profit):
    if profit >= 1e6:
        return f"{profit / 1e6:.1f}m"
    elif profit >= 1e3:
        return f"{profit / 1e3:.1f}k"
    return str(profit)


def format_price(price):
    if price >= 1e6:
        return f"{price / 1e6:.1f}m"
    elif price >= 1e3:
        return f"{price / 1e3:.1f}k"
    return str(price)


def main():
    root = tk.Tk()
    app = AuctionAnalyzerApp(root)
    root.geometry("1000x700")  # Set window size to 1000x700 pixels
    root.mainloop()


if __name__ == "__main__":
    main()
