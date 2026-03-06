import sqlite3
import os

class DatabaseManager:
    def __init__(self, db_path="data/murim_warrior.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Users Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    userid TEXT PRIMARY KEY,
                    password TEXT NOT NULL
                )
            """)
            
            # 2. Portfolio Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    userid TEXT,
                    ticker TEXT,
                    quantity REAL,
                    UNIQUE(userid, ticker)
                )
            """)
            
            # 3. Warrior Stats Table (초기 생성 시 신규 지표 포함)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS warrior_stats (
                    ticker TEXT PRIMARY KEY,
                    yesterday_price REAL,
                    sharp REAL,
                    beta REAL,
                    mdd REAL,
                    stand_dev REAL,
                    last_updated TEXT,
                    months INTEGER DEFAULT 12,
                    cum_return REAL DEFAULT 0.0,
                    cagr REAL DEFAULT 0.0
                )
            """)
            
            # 4. Portfolio Summary Table (초기 생성 시 신규 지표 포함)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_summary (
                    userid TEXT PRIMARY KEY,
                    total_value REAL,
                    sharp REAL,
                    beta REAL,
                    mdd REAL,
                    upside_dev REAL,
                    stand_dev REAL,
                    cum_return REAL DEFAULT 0.0,
                    cagr REAL DEFAULT 0.0,
                    simulated_profit REAL DEFAULT 0.0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 🚀 [DB 자동 진화 마법] 기존에 생성된 DB 파일용 하위 호환성 유지
            new_columns_warrior = [
                ("months", "INTEGER DEFAULT 12"),
                ("cum_return", "REAL DEFAULT 0.0"),
                ("cagr", "REAL DEFAULT 0.0")
            ]
            for col_name, col_type in new_columns_warrior:
                try:
                    cursor.execute(f"ALTER TABLE warrior_stats ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass 

            new_columns_summary = [
                ("cum_return", "REAL DEFAULT 0.0"),
                ("cagr", "REAL DEFAULT 0.0"),
                ("simulated_profit", "REAL DEFAULT 0.0")
            ]
            for col_name, col_type in new_columns_summary:
                try:
                    cursor.execute(f"ALTER TABLE portfolio_summary ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass

            conn.commit()

    # ==========================================
    # 🚀 캐싱 전용 통신 함수
    # ==========================================
    def get_market_data(self, ticker):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ticker, yesterday_price, sharp, beta, mdd, stand_dev, last_updated, months, cum_return, cagr
                FROM warrior_stats 
                WHERE ticker=?
            """, (ticker,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def save_market_data(self, stats_dict):
        self.update_warrior_stats(stats_dict)

    # ==========================================
    # 개별 종목 (Portfolio & Warrior Stats) 관련 함수
    # ==========================================
    def get_user_portfolio(self, userid):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker, quantity FROM portfolio WHERE userid=?", (userid,))
            return [dict(row) for row in cursor.fetchall()]

    def clear_portfolio(self, userid):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM portfolio WHERE userid=?", (userid,))
            conn.commit()

    def save_portfolio_item(self, userid, ticker, quantity):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, quantity FROM portfolio WHERE userid=? AND ticker=?", (userid, ticker))
            row = cursor.fetchone()
            if row:
                cursor.execute("UPDATE portfolio SET quantity=? WHERE id=?", (quantity, row['id']))
            else:
                cursor.execute("INSERT INTO portfolio (userid, ticker, quantity) VALUES (?, ?, ?)", (userid, ticker, quantity))
            conn.commit()

    def update_warrior_stats(self, stats_dict):
        if 'last_updated' not in stats_dict: stats_dict['last_updated'] = ''
        if 'months' not in stats_dict: stats_dict['months'] = 12
        if 'cum_return' not in stats_dict: stats_dict['cum_return'] = 0.0
        if 'cagr' not in stats_dict: stats_dict['cagr'] = 0.0
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO warrior_stats 
                (ticker, yesterday_price, sharp, beta, mdd, stand_dev, last_updated, months, cum_return, cagr)
                VALUES (:ticker, :yesterday_price, :sharp, :beta, :mdd, :stand_dev, :last_updated, :months, :cum_return, :cagr)
                ON CONFLICT(ticker) DO UPDATE SET
                    yesterday_price = excluded.yesterday_price,
                    sharp = excluded.sharp,
                    beta = excluded.beta,
                    mdd = excluded.mdd,
                    stand_dev = excluded.stand_dev,
                    last_updated = excluded.last_updated,
                    months = excluded.months,
                    cum_return = excluded.cum_return,
                    cagr = excluded.cagr
            """, stats_dict)
            conn.commit()

    def get_user_portfolio_stats(self, userid):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    p.ticker, p.quantity, 
                    w.yesterday_price, w.sharp, w.beta, w.mdd, w.stand_dev, w.cum_return, w.cagr
                FROM portfolio p
                LEFT JOIN warrior_stats w ON p.ticker = w.ticker
                WHERE p.userid = ?
            """, (userid,))
            return [dict(row) for row in cursor.fetchall()]

    # ==========================================
    # 포트폴리오 전체 종합 (Portfolio Summary) 관련 함수
    # ==========================================
    def update_portfolio_summary(self, userid, stats_dict):
        if 'cum_return' not in stats_dict: stats_dict['cum_return'] = 0.0
        if 'cagr' not in stats_dict: stats_dict['cagr'] = 0.0
        if 'simulated_profit' not in stats_dict: stats_dict['simulated_profit'] = 0.0

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO portfolio_summary 
                (userid, total_value, sharp, beta, mdd, upside_dev, stand_dev, cum_return, cagr, simulated_profit, last_updated)
                VALUES (:userid, :total_value, :sharp, :beta, :mdd, :upside_dev, :stand_dev, :cum_return, :cagr, :simulated_profit, CURRENT_TIMESTAMP)
                ON CONFLICT(userid) DO UPDATE SET
                    total_value = excluded.total_value,
                    sharp = excluded.sharp,
                    beta = excluded.beta,
                    mdd = excluded.mdd,
                    upside_dev = excluded.upside_dev,
                    stand_dev = excluded.stand_dev,
                    cum_return = excluded.cum_return,
                    cagr = excluded.cagr,
                    simulated_profit = excluded.simulated_profit,
                    last_updated = CURRENT_TIMESTAMP
            """, {'userid': userid, **stats_dict})
            conn.commit()

    def get_portfolio_summary(self, userid):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM portfolio_summary WHERE userid=?", (userid,))
            row = cursor.fetchone()
            return dict(row) if row else None

# 모듈 객체 생성
db = DatabaseManager()