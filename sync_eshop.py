import urllib.request
import re
import sqlite3
import time
import math
import sys
import argparse
import json
import os
from datetime import datetime

# Base URL for Nintendo Switch Korea online store
BASE_URL = "https://store.nintendo.co.kr/all-product"

def export_to_json(db_path, json_path):
    print("Exporting data to JSON for web viewer...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Get last updated time
    cursor.execute("SELECT MAX(last_updated) FROM games")
    last_updated = cursor.fetchone()[0] or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 2. Get latest logged date to determine current prices
    cursor.execute("SELECT MAX(logged_date) FROM price_history")
    latest_log_date = cursor.fetchone()[0]
    if not latest_log_date:
        print("No price history records found. Cannot export.")
        conn.close()
        return
    
    # 3. Fetch all games with their latest price info, ordered by store_position (position)
    cursor.execute('''
        SELECT g.nsuid, g.product_id, g.title, g.release_date, g.image_url,
               p.regular_price, p.discount_price, p.is_discounted
        FROM games g
        LEFT JOIN price_history p ON g.nsuid = p.nsuid AND p.logged_date = ?
        ORDER BY COALESCE(g.store_position, 999999) ASC
    ''', (latest_log_date,))
    
    rows = cursor.fetchall()
    
    # Fetch price histories for discounted games to show charts
    # We only fetch history for games that are currently discounted to keep the JSON small
    cursor.execute('''
        SELECT ph.nsuid, ph.logged_date, ph.discount_price
        FROM price_history ph
        WHERE ph.nsuid IN (
            SELECT nsuid FROM price_history WHERE logged_date = ? AND is_discounted = 1
        )
        ORDER BY ph.nsuid, ph.logged_date ASC
    ''', (latest_log_date,))
    
    history_rows = cursor.fetchall()
    history_map = {}
    for nsuid, logged_date, disc_price in history_rows:
        if nsuid not in history_map:
            history_map[nsuid] = []
        history_map[nsuid].append({"date": logged_date, "price": disc_price})
        
    games_list = []
    total_sales = 0
    
    for r in rows:
        nsuid, product_id, title, release_date, image_url, reg_price, disc_price, is_disc = r
        
        # Default fallback values if no price history is recorded yet
        reg_price = reg_price or 0
        disc_price = disc_price or reg_price or 0
        is_disc = is_disc or 0
        
        if is_disc:
            total_sales += 1
            
        discount_rate = 0
        if is_disc and reg_price > 0:
            discount_rate = int((reg_price - disc_price) / reg_price * 100)
            
        game_data = {
            "nsuid": nsuid,
            "title": title,
            "release_date": release_date,
            "image_url": image_url,
            "regular_price": reg_price,
            "discount_price": disc_price,
            "is_discounted": is_disc,
            "discount_rate": discount_rate
        }
        
        # Add history if available (only for discounted games to keep size down)
        if nsuid in history_map:
            game_data["history"] = history_map[nsuid]
            
        games_list.append(game_data)
        
    data = {
        "last_updated": last_updated,
        "total_games": len(games_list),
        "total_sales": total_sales,
        "games": games_list
    }
    
    os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully exported {len(games_list)} games (including {total_sales} discounts) to {json_path}")
    conn.close()

def get_html(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'Referer': 'https://store.nintendo.co.kr/'
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            print(f"\n[Warning] Request failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in 3 seconds...")
            time.sleep(3)

def parse_products_from_html(html):
    items = re.findall(r'<li class="item product product-item">.*?</li>', html, re.DOTALL)
    products = []
    
    for item in items:
        # Extract product link and NSUID
        href_match = re.search(r'href="https://store\.nintendo\.co\.kr/(\d+)"', item)
        nsuid = href_match.group(1) if href_match else None
        if not nsuid:
            href_match_alt = re.search(r'href="(https://store\.nintendo\.co\.kr/[^"]+)"', item)
            href = href_match_alt.group(1) if href_match_alt else None
            if not href:
                continue
            nsuid = href.split('/')[-1]
            
        # Extract product ID
        pid_match = re.search(r'data-product-id="(\d+)"', item)
        product_id = int(pid_match.group(1)) if pid_match else None
        
        # Extract image URL
        img_match = re.search(r'<img class="product-image-photo".*?src="([^"]+)"', item, re.DOTALL)
        image_url = img_match.group(1) if img_match else None
        
        # Extract release date
        release_match = re.search(r'category-product-item-released">.*?<span>발매</span>\s*([^<]+)', item, re.DOTALL)
        release_date = release_match.group(1).strip() if release_match else None
        
        # Extract title
        title_match = re.search(r'<a class="product-item-link"\s+href="[^"]+">\s*([^<]+?)\s*</a>', item)
        title = title_match.group(1).strip() if title_match else None
        if title:
            title = title.replace('&#x20;', ' ').replace('&amp;', '&')
            
        # Extract prices
        is_discounted = 0
        regular_price = None
        discount_price = None
        
        old_price_match = re.search(r'class="old-price".*?data-price-amount="(\d+)"', item, re.DOTALL)
        special_price_match = re.search(r'class="special-price".*?data-price-amount="(\d+)"', item, re.DOTALL)
        final_price_match = re.search(r'id="product-price-\d+".*?data-price-amount="(\d+)"', item, re.DOTALL)
        
        if old_price_match and special_price_match:
            is_discounted = 1
            regular_price = int(old_price_match.group(1))
            discount_price = int(special_price_match.group(1))
        elif final_price_match:
            regular_price = int(final_price_match.group(1))
            discount_price = regular_price
        
        products.append({
            "nsuid": nsuid,
            "product_id": product_id,
            "title": title,
            "release_date": release_date,
            "image_url": image_url,
            "regular_price": regular_price,
            "discount_price": discount_price,
            "is_discounted": is_discounted
        })
        
    return products

def get_total_products(html):
    amount_matches = re.findall(r'<span class="toolbar-number">([^<]+)</span>', html)
    if len(amount_matches) >= 3:
        try:
            return int(amount_matches[2].replace(',', ''))
        except ValueError:
            pass
    return None

def init_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Auto-migration: Check if old database format exists
    cursor.execute("PRAGMA table_info(games)")
    columns = [col[1] for col in cursor.fetchall()]
    if columns and "regular_price" in columns:
        print("Old database schema detected. Migrating database for price history tracking...")
        cursor.execute("DROP TABLE IF EXISTS games")
        cursor.execute("DROP TABLE IF EXISTS price_history")
        conn.commit()
    elif columns and "store_position" not in columns:
        print("Migrating games table to add store_position...")
        cursor.execute("ALTER TABLE games ADD COLUMN store_position INTEGER")
        conn.commit()

    # Games metadata table (rarely changes)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            nsuid TEXT PRIMARY KEY,
            product_id INTEGER,
            title TEXT,
            release_date TEXT,
            image_url TEXT,
            store_position INTEGER,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Pricing log table (accumulates daily records)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            nsuid TEXT,
            regular_price INTEGER,
            discount_price INTEGER,
            is_discounted INTEGER,
            logged_date TEXT, -- Format: YYYY-MM-DD
            PRIMARY KEY (nsuid, logged_date),
            FOREIGN KEY(nsuid) REFERENCES games(nsuid)
        )
    ''')
    conn.commit()
    return conn

def save_products_to_db(conn, products):
    cursor = conn.cursor()
    today_date = datetime.now().strftime('%Y-%m-%d')
    now_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    for p in products:
        # 1. Update general metadata
        cursor.execute('''
            INSERT OR REPLACE INTO games 
            (nsuid, product_id, title, release_date, image_url, store_position, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            p["nsuid"],
            p["product_id"],
            p["title"],
            p["release_date"],
            p["image_url"],
            p.get("store_position"),
            now_timestamp
        ))
        
        # 2. Add pricing record for today
        # If run multiple times on the same day, INSERT OR REPLACE will update today's record.
        # Otherwise, a new record is created for each new date.
        cursor.execute('''
            INSERT OR REPLACE INTO price_history
            (nsuid, regular_price, discount_price, is_discounted, logged_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            p["nsuid"],
            p["regular_price"],
            p["discount_price"],
            p["is_discounted"],
            today_date
        ))
        
    conn.commit()

def main():
    parser = argparse.ArgumentParser(description="Nintendo Switch Korea eShop Database Sync Script")
    parser.add_argument("--db", default="database.sqlite", help="Path to SQLite database file")
    parser.add_argument("--quick", action="store_true", help="Only sync the first 2 pages for a quick test")
    parser.add_argument("--limit-pages", type=int, default=0, help="Limit syncing to a maximum number of pages")
    parser.add_argument("--json-out", default="docs/data.json", help="Path to output JSON file for web viewer")
    args = parser.parse_args()

    print("Initializing Database...")
    conn = init_db(args.db)
    
    print("Fetching first page to determine total products...")
    try:
        first_page_html = get_html(BASE_URL)
    except Exception as e:
        print(f"Error fetching the homepage: {e}")
        sys.exit(1)
        
    total_products = get_total_products(first_page_html)
    if total_products:
        print(f"Total products found on Nintendo Store KR: {total_products}")
        total_pages = math.ceil(total_products / 24)
    else:
        print("Could not determine total products count. Defaulting pagination loop.")
        total_pages = 400
        
    if args.quick:
        total_pages = 2
        print("Quick mode active. Syncing limit set to 2 pages.")
    elif args.limit_pages > 0:
        total_pages = min(total_pages, args.limit_pages)
        print(f"Page limit set: Syncing maximum of {total_pages} pages.")

    print(f"Starting crawl of {total_pages} pages...")
    start_time = time.time()
    total_saved = 0

    for page in range(1, total_pages + 1):
        page_url = f"{BASE_URL}?p={page}"
        print(f"[{page}/{total_pages}] Syncing: {page_url} ... ", end="", flush=True)
        
        try:
            html = get_html(page_url)
            products = parse_products_from_html(html)
            
            if not products:
                print("No products found. Stopping.")
                break
                
            # Assign store_position based on crawling page and offset
            for idx, p in enumerate(products):
                p["store_position"] = (page - 1) * 24 + idx + 1
                
            save_products_to_db(conn, products)
            total_saved += len(products)
            print(f"Saved {len(products)} products.")
            
        except Exception as e:
            print(f"Failed! Error: {e}")
            
        time.sleep(1.0)

    conn.close()
    export_to_json(args.db, args.json_out)
    elapsed = time.time() - start_time
    print(f"\nSync Completed! Total products processed: {total_saved}")
    print(f"Elapsed Time: {elapsed:.2f} seconds.")

if __name__ == "__main__":
    main()
