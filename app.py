import sqlite3
import os
import sys
import time

DB_PATH = "database.sqlite"

def get_connection():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file '{DB_PATH}' not found.")
        print("Please run the sync script first to create it: python sync_eshop.py")
        print("Or choose the Sync option from the menu if you want to initialize it.")
    return sqlite3.connect(DB_PATH)

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')

def press_enter():
    input("\nPress Enter to return to the menu...")

def show_header(title):
    print("=" * 60)
    print(f" {title:^58} ")
    print("=" * 60)

def show_game_detail(nsuid, title, release_date):
    clear_screen()
    show_header("게임 상세 정보 및 가격 히스토리")
    print(f"🎮 게임명: {title}")
    print(f"🆔 NSUID : {nsuid}")
    print(f"📅 발매일: {release_date}")
    print("-" * 60)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Get current price
    cursor.execute('''
        SELECT regular_price, discount_price, is_discounted, logged_date
        FROM price_history
        WHERE nsuid = ?
        ORDER BY logged_date DESC
        LIMIT 1
    ''', (nsuid,))
    current_price_row = cursor.fetchone()
    
    # 2. Get lowest price ever (where is_discounted=1 or general minimum discount_price)
    cursor.execute('''
        SELECT MIN(discount_price), logged_date
        FROM price_history
        WHERE nsuid = ? AND discount_price = (
            SELECT MIN(discount_price) FROM price_history WHERE nsuid = ?
        )
        ORDER BY logged_date ASC
        LIMIT 1
    ''', (nsuid, nsuid))
    lowest_price_row = cursor.fetchone()
    
    # 3. Get all price history logs
    cursor.execute('''
        SELECT logged_date, regular_price, discount_price, is_discounted
        FROM price_history
        WHERE nsuid = ?
        ORDER BY logged_date DESC
    ''', (nsuid,))
    history_rows = cursor.fetchall()
    
    conn.close()
    
    if current_price_row:
        reg_p, disc_p, is_disc, log_d = current_price_row
        price_str = f"₩{reg_p:,}"
        if is_disc:
            pct = int((reg_p - disc_p) / reg_p * 100)
            price_str = f"₩{disc_p:,} ({pct}% 할인) [정가: ₩{reg_p:,}]"
        print(f"💵 현재 가격: {price_str} (기준일: {log_d})")
    else:
        print("💵 현재 가격: 정보 없음")
        
    if lowest_price_row and lowest_price_row[0] is not None:
        low_p, low_d = lowest_price_row
        print(f"🔥 역대 최저가: ₩{low_p:,} (기록일: {low_d})")
    else:
        print("🔥 역대 최저가: 정보 없음")
        
    print("-" * 60)
    print("📈 가격 변동 기록 (최신순):")
    if not history_rows:
        print("  기록된 가격 변동 정보가 없습니다.")
    else:
        # We group logs to show clean changes
        last_price = None
        last_disc = None
        for row in history_rows:
            log_d, reg_p, disc_p, is_disc = row
            pct = int((reg_p - disc_p) / reg_p * 100) if reg_p > 0 else 0
            
            # Show change indicators or just the price line
            status = f"{pct}% 할인" if is_disc else "정가 판매"
            print(f"  [{log_d}]  ₩{disc_p:,} ({status})")
            
    print("=" * 60)
    press_enter()

def search_games():
    clear_screen()
    show_header("검색 (Search Games)")
    query = input("검색할 게임 제목을 입력하세요 (또는 엔터로 취소): ").strip()
    if not query:
        return
        
    conn = get_connection()
    cursor = conn.cursor()
    
    # We join games with the latest price record in price_history
    cursor.execute('''
        SELECT g.nsuid, g.title, g.release_date, p.regular_price, p.discount_price, p.is_discounted 
        FROM games g
        LEFT JOIN price_history p ON g.nsuid = p.nsuid AND p.logged_date = (
            SELECT MAX(logged_date) FROM price_history ph WHERE ph.nsuid = g.nsuid
        )
        WHERE g.title LIKE ? 
        ORDER BY g.release_date DESC
    ''', (f"%{query}%",))
    
    rows = cursor.fetchall()
    conn.close()
    
    print("\n" + "-" * 60)
    if not rows:
        print("검색 결과가 없습니다.")
        press_enter()
        return
        
    print(f"총 {len(rows)}개의 게임이 검색되었습니다:\n")
    for i, row in enumerate(rows, 1):
        nsuid, title, rel_date, reg_p, disc_p, is_disc = row
        price_str = "정보 없음"
        if reg_p is not None:
            price_str = f"₩{reg_p:,}"
            if is_disc:
                pct = int((reg_p - disc_p) / reg_p * 100) if reg_p > 0 else 0
                price_str = f"₩{disc_p:,} ({pct}% 할인) [정가: ₩{reg_p:,}]"
        print(f"{i:2d}. {title}")
        print(f"    [ID: {nsuid}] | 발매일: {rel_date} | 현재가: {price_str}")
        print("-" * 60)
        
    choice = input("\n상세 가격 히스토리를 볼 게임 번호를 입력하세요 (엔터는 취소): ").strip()
    if not choice:
        return
        
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(rows):
            nsuid, title, rel_date, _, _, _ = rows[idx]
            show_game_detail(nsuid, title, rel_date)
        else:
            print("범위를 벗어난 번호입니다.")
            time.sleep(1)
    except ValueError:
        print("잘못된 입력입니다.")
        time.sleep(1)

def view_discounts():
    clear_screen()
    show_header("현재 할인 중인 게임 목록 (Discounted Games)")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT g.nsuid, g.title, g.release_date, p.regular_price, p.discount_price 
        FROM games g
        JOIN price_history p ON g.nsuid = p.nsuid AND p.logged_date = (
            SELECT MAX(logged_date) FROM price_history ph WHERE ph.nsuid = g.nsuid
        )
        WHERE p.is_discounted = 1 
        ORDER BY ((p.regular_price - p.discount_price) * 1.0 / p.regular_price) DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    print("\n" + "-" * 60)
    if not rows:
        print("현재 할인 중인 게임이 없습니다. DB가 업데이트되지 않았거나 세일이 없을 수 있습니다.")
        press_enter()
        return
        
    print(f"총 {len(rows)}개의 할인 게임이 있습니다 (할인율 높은 순):\n")
    for i, row in enumerate(rows, 1):
        nsuid, title, rel_date, reg_p, disc_p = row
        pct = int((reg_p - disc_p) / reg_p * 100) if reg_p > 0 else 0
        print(f"{i:2d}. {title}")
        print(f"    할인가: ₩{disc_p:,} ({pct}% 할인) | 정가: ₩{reg_p:,} | 발매일: {rel_date}")
        print("-" * 60)
        
    choice = input("\n상세 가격 히스토리를 볼 게임 번호를 입력하세요 (엔터는 취소): ").strip()
    if not choice:
        return
        
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(rows):
            nsuid, title, rel_date, _, _ = rows[idx]
            show_game_detail(nsuid, title, rel_date)
        else:
            print("범위를 벗어난 번호입니다.")
            time.sleep(1)
    except ValueError:
        print("잘못된 입력입니다.")
        time.sleep(1)

def view_new_releases():
    clear_screen()
    show_header("최신 출시 게임 목록 (New Releases)")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT g.nsuid, g.title, g.release_date, p.regular_price, p.discount_price, p.is_discounted 
        FROM games g
        LEFT JOIN price_history p ON g.nsuid = p.nsuid AND p.logged_date = (
            SELECT MAX(logged_date) FROM price_history ph WHERE ph.nsuid = g.nsuid
        )
        ORDER BY g.release_date DESC 
        LIMIT 20
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    print("\n" + "-" * 60)
    if not rows:
        print("DB에 저장된 게임이 없습니다. 먼저 데이터 동기화를 진행해 주세요.")
        press_enter()
        return
        
    print("최신 출시된 게임 20개:\n")
    for i, row in enumerate(rows, 1):
        nsuid, title, rel_date, reg_p, disc_p, is_disc = row
        price_str = "정보 없음"
        if reg_p is not None:
            price_str = f"₩{reg_p:,}"
            if is_disc:
                pct = int((reg_p - disc_p) / reg_p * 100) if reg_p > 0 else 0
                price_str = f"₩{disc_p:,} ({pct}% 할인) [정가: ₩{reg_p:,}]"
        print(f"{i:2d}. {title}")
        print(f"    발매일: {rel_date} | 가격: {price_str}")
        print("-" * 60)
        
    choice = input("\n상세 가격 히스토리를 볼 게임 번호를 입력하세요 (엔터는 취소): ").strip()
    if not choice:
        return
        
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(rows):
            nsuid, title, rel_date, _, _, _ = rows[idx]
            show_game_detail(nsuid, title, rel_date)
        else:
            print("범위를 벗어난 번호입니다.")
            time.sleep(1)
    except ValueError:
        print("잘못된 입력입니다.")
        time.sleep(1)

def view_statistics():
    clear_screen()
    show_header("데이터베이스 통계 (Statistics)")
    
    if not os.path.exists(DB_PATH):
        print("데이터베이스 파일이 존재하지 않습니다. 먼저 동기화를 진행하세요.")
        press_enter()
        return

    conn = get_connection()
    cursor = conn.cursor()
    
    # Total games
    cursor.execute("SELECT COUNT(*) FROM games")
    total_games = cursor.fetchone()[0]
    
    # Discounted games (latest status)
    cursor.execute('''
        SELECT COUNT(*) FROM price_history p
        WHERE p.is_discounted = 1 AND p.logged_date = (
            SELECT MAX(logged_date) FROM price_history ph WHERE ph.nsuid = p.nsuid
        )
    ''')
    total_sales = cursor.fetchone()[0]
    
    # Total price records
    cursor.execute("SELECT COUNT(*) FROM price_history")
    total_records = cursor.fetchone()[0]
    
    # Last update time
    cursor.execute("SELECT MAX(last_updated) FROM games")
    last_update = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\n* 로컬 DB 파일 경로: {os.path.abspath(DB_PATH)}")
    print(f"* 전체 저장된 게임 수: {total_games:,} 개")
    print(f"* 현재 할인 중인 게임 수: {total_sales:,} 개")
    if total_games > 0:
        sale_ratio = (total_sales / total_games) * 100
        print(f"* 할인 중인 게임 비율: {sale_ratio:.1f}%")
    print(f"* 가격 히스토리 데이터 수: {total_records:,} 개")
    print(f"* 가장 최근 동기화 시간: {last_update or 'N/A'}")
    print("=" * 60)
    
    press_enter()

def local_sync():
    clear_screen()
    show_header("로컬 데이터 동기화 (Local Database Sync)")
    print("주의: 전체 DB 동기화(약 9,000개 상품)는 약 7~10분이 소요됩니다.")
    print("테스트를 위해 처음 2페이지만 빠르게 긁어오려면 'quick' 모드를 선택하세요.\n")
    print("1. 전체 동기화 실행 (Full Sync)")
    print("2. 테스트 동기화 실행 (Quick Sync - 2페이지 분량)")
    print("3. 취소하고 돌아가기")
    
    choice = input("\n메뉴 선택: ").strip()
    if choice == '3' or not choice:
        return
        
    quick_mode = (choice == '2')
    
    print("\n동기화 스크립트를 로드하는 중...")
    try:
        import sync_eshop
        # Override sys.argv
        sys.argv = [sys.argv[0]]
        if quick_mode:
            sys.argv.append("--quick")
            
        print("스크립트 실행 시작...")
        sync_eshop.main()
        
    except Exception as e:
        print(f"\n에러 발생: {e}")
        
    press_enter()

def main():
    while True:
        clear_screen()
        print("=" * 60)
        print("      🎮 Nintendo Switch KR eShop Database Viewer 🎮      ")
        print("=" * 60)
        print(" 1. 게임 제목 검색 (Search Games)")
        print(" 2. 현재 할인 상품 보기 (View Discounts - 할인율 순)")
        print(" 3. 최신 출시 게임 보기 (New Releases)")
        print(" 4. DB 통계 보기 (View Statistics)")
        print(" 5. 로컬 데이터 동기화 실행 (Sync Data)")
        print(" 0. 종료 (Exit)")
        print("=" * 60)
        
        choice = input("원하는 메뉴 번호를 입력하세요: ").strip()
        
        if choice == '1':
            search_games()
        elif choice == '2':
            view_discounts()
        elif choice == '3':
            view_new_releases()
        elif choice == '4':
            view_statistics()
        elif choice == '5':
            local_sync()
        elif choice == '0':
            print("\n프로그램을 종료합니다. 즐거운 게임 라이프 되세요!")
            sys.exit(0)
        else:
            print("\n잘못된 선택입니다. 다시 입력해 주세요.")
            time.sleep(1)

if __name__ == "__main__":
    main()
