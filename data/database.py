import sqlite3
import os

class DatabaseManager:
    def __init__(self, db_path="data/murim_warrior.db"):
        self.db_path = db_path
        # data 폴더가 없으면 자동 생성
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
            
            # 2. Portfolio Table (개별 비급 수집 내역)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    userid TEXT,
                    ticker TEXT,
                    quantity REAL,
                    UNIQUE(userid, ticker)
                )
            """)
            
            # 3. Warrior Stats Table (개별 종목 스탯)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS warrior_stats (
                    ticker TEXT PRIMARY KEY,
                    yesterday_price REAL,
                    sharp REAL,
                    beta REAL,
                    mdd REAL,
                    stand_dev REAL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 4. Portfolio Summary Table (계좌 전체 5대 지표 및 총자산)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_summary (
                    userid TEXT PRIMARY KEY,
                    total_value REAL,
                    sharp REAL,
                    beta REAL,
                    mdd REAL,
                    upside_dev REAL,
                    stand_dev REAL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    # ==========================================
    # 개별 종목 (Portfolio & Warrior Stats) 관련 함수
    # ==========================================
    def get_user_portfolio(self, userid):
        """[조회] 유저의 포트폴리오 목록(종목, 수량)만 가져옵니다."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker, quantity FROM portfolio WHERE userid=?", (userid,))
            return [dict(row) for row in cursor.fetchall()]

    def clear_portfolio(self, userid):
        """[삭제] 유저의 기존 포트폴리오를 모두 비웁니다."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM portfolio WHERE userid=?", (userid,))
            conn.commit()

    def save_portfolio_item(self, userid, ticker, quantity):
        """[저장] 개별 종목과 수량을 DB에 저장합니다."""
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
        """[저장] 개별 종목의 분석 스탯을 업데이트합니다."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO warrior_stats (ticker, yesterday_price, sharp, beta, mdd, stand_dev, last_updated)
                VALUES (:ticker, :yesterday_price, :sharp, :beta, :mdd, :stand_dev, CURRENT_TIMESTAMP)
                ON CONFLICT(ticker) DO UPDATE SET
                    yesterday_price = excluded.yesterday_price,
                    sharp = excluded.sharp,
                    beta = excluded.beta,
                    mdd = excluded.mdd,
                    stand_dev = excluded.stand_dev,
                    last_updated = CURRENT_TIMESTAMP
            """, stats_dict)
            conn.commit()

    def get_user_portfolio_stats(self, userid):
        """[조회] 대시보드 하단 표를 위해 보유 종목과 그 스탯을 합쳐서 가져옵니다."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    p.ticker, 
                    p.quantity, 
                    w.yesterday_price, 
                    w.sharp, 
                    w.beta, 
                    w.mdd, 
                    w.stand_dev
                FROM portfolio p
                LEFT JOIN warrior_stats w ON p.ticker = w.ticker
                WHERE p.userid = ?
            """, (userid,))
            return [dict(row) for row in cursor.fetchall()]

    # ==========================================
    # 포트폴리오 전체 종합 (Portfolio Summary) 관련 함수
    # ==========================================
    def update_portfolio_summary(self, userid, stats_dict):
        """[저장] 계좌 전체의 종합 분석 결과(5대 지표)를 저장합니다."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO portfolio_summary 
                (userid, total_value, sharp, beta, mdd, upside_dev, stand_dev, last_updated)
                VALUES (:userid, :total_value, :sharp, :beta, :mdd, :upside_dev, :stand_dev, CURRENT_TIMESTAMP)
                ON CONFLICT(userid) DO UPDATE SET
                    total_value = excluded.total_value,
                    sharp = excluded.sharp,
                    beta = excluded.beta,
                    mdd = excluded.mdd,
                    upside_dev = excluded.upside_dev,
                    stand_dev = excluded.stand_dev,
                    last_updated = CURRENT_TIMESTAMP
            """, {'userid': userid, **stats_dict})
            conn.commit()

    def get_portfolio_summary(self, userid):
        """[조회] 대시보드 상단 카드를 위해 계좌 종합 스탯을 가져옵니다."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM portfolio_summary WHERE userid=?", (userid,))
            row = cursor.fetchone()
            return dict(row) if row else None

# 다른 파일에서 db.get_user_portfolio() 처럼 바로 쓸 수 있게 객체 생성
db = DatabaseManager()