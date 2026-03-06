import yfinance as yf
import FinanceDataReader as fdr  
import pandas as pd
import numpy as np
import requests
import urllib3
from datetime import datetime, timedelta
from data.database import db

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class AnalysisEngine:
    # 🚀 [핵심] 기본 12개월, 최대 60개월까지 월 단위로 정밀 조절하는 다이얼!
    def __init__(self, months=12):
        self.benchmark_ticker = "SPY" 
        self._bm_cache = None  
        self._fx_cache = None  
        
        # 입력값이 12~60 사이를 벗어나지 않도록 안전장치(Clamping)
        self.months = max(1, min(60, int(months)))
        
        # 🚀 [정밀 타격] 개월 수를 정확한 날짜(시작일/종료일)로 변환합니다.
        # 1개월 = 평균 30.436875일로 계산하여 윤년까지 커버
        self.end_date = datetime.today()
        self.start_date = self.end_date - timedelta(days=int(30.437 * self.months))
        
        self.start_str = self.start_date.strftime('%Y-%m-%d')
        self.end_str = self.end_date.strftime('%Y-%m-%d')

    def _get_fx_data(self):
        if self._fx_cache is not None:
            return self._fx_cache
            
        try:
            # 🚀 정확한 날짜로 기간 통일
            fx = yf.download("USDKRW=X", start=self.start_str, end=self.end_str, progress=False)['Close']
            if isinstance(fx, pd.DataFrame):
                fx = fx.iloc[:, 0]
                
            fx.index = fx.index.astype(str).str[:10]
            self._fx_cache = fx.ffill().dropna()
            return self._fx_cache
            
        except Exception as e:
            print(f"⚠️ 환율 로드 실패 (기본값 1400원 적용): {e}")
            # 한 달 평균 21영업일 기준으로 더미 데이터 길이 맞춤
            dates = pd.date_range(end=self.end_date, periods=int(21 * self.months)).astype(str).str[:10]
            return pd.Series(1400.0, index=dates)

    def _get_benchmark_data(self):
        if self._bm_cache is not None:
            return self._bm_cache
            
        try:
            # 🚀 정확한 날짜로 기간 통일
            bm_data = yf.download(self.benchmark_ticker, start=self.start_str, end=self.end_str, progress=False)['Close']
            if isinstance(bm_data, pd.DataFrame):
                bm_data = bm_data.iloc[:, 0]
                
            bm_data.index = bm_data.index.astype(str).str[:10]
            
            fx_data = self._get_fx_data()
            combined = pd.DataFrame({'spy': bm_data, 'fx': fx_data}).ffill().dropna()
            bm_data_krw = combined['spy'] * combined['fx']
            
            self._bm_cache = bm_data_krw.pct_change().dropna()
            return self._bm_cache
            
        except Exception as e:
            print(f"⚠️ 벤치마크 데이터 로드 실패: {e}")
            return pd.Series(dtype=float)

    def _get_realtime_price(self, ticker, fallback_price):
        try:
            if ticker.endswith('.KS') or ticker.endswith('.KQ'):
                code = ticker.split('.')[0]
                url = f"https://m.stock.naver.com/api/stock/{code}/basic"
                headers = {'User-Agent': 'Mozilla/5.0'}
                res = requests.get(url, headers=headers, timeout=3, verify=False)
                if res.status_code == 200:
                    price_str = res.json().get('closePrice', '0').replace(',', '')
                    return float(price_str)
                    
            stock = yf.Ticker(ticker)
            price = stock.fast_info.get('lastPrice')
            return float(price) if price is not None else fallback_price
        except Exception:
            return fallback_price

    def _fetch_hybrid_data(self, ticker):
        """
        🚀 [TR 연산 폐기 & 수정주가 직접 적용]
        FDR과 yfinance의 수정주가(Adjusted Close)를 곧바로 TR_Price로 활용하여
        가볍고 빠른 캐싱 처리를 구현합니다.
        """
        is_korean = ticker.endswith('.KS') or ticker.endswith('.KQ')
        
        if is_korean:
            code = ticker.split('.')[0]
            print(f"🇰🇷 [수정주가 엔진] 한국 종목({self.months}개월) 데이터 로드 중: {code}")
            try:
                df = fdr.DataReader(code, self.start_str, self.end_str)
                if df.empty or 'Close' not in df.columns: 
                    raise Exception("FDR 데이터 없음")
                
                df = df[['Close']].copy()
                df.index = df.index.astype(str).str[:10]
                
                # FDR의 Close는 기본적으로 수정주가이므로 이를 그대로 TR_Price로 사용합니다.
                df['TR_Price'] = df['Close']
                return df[['Close', 'TR_Price']]
                
            except Exception as e:
                print(f"⚠️ FDR 로드 실패. 빈 데이터 반환: {e}")
                return pd.DataFrame()
        
        else:
            print(f"🇺🇸 [수정주가 엔진] 글로벌 종목({self.months}개월) 다운로드 중: {ticker}")
            df = yf.download(ticker, start=self.start_str, end=self.end_str, progress=False)
            
            if df.empty:
                return pd.DataFrame()

            if isinstance(df.columns, pd.MultiIndex):
                close_s = df['Close'][ticker]
                adj_close_s = df['Adj Close'][ticker]
            else:
                close_s = df['Close']
                adj_close_s = df['Adj Close']
                
            # yfinance의 Adj Close를 TR_Price로 사용합니다.
            res_df = pd.DataFrame({'Close': close_s, 'TR_Price': adj_close_s})
            res_df.index = res_df.index.astype(str).str[:10]
            return res_df

    def analyze_ticker(self, ticker):
        today_str = datetime.now().strftime('%Y-%m-%d')
        cached_data = db.get_market_data(ticker)
        
        if cached_data and cached_data.get('last_updated') == today_str and cached_data.get('months') == self.months:
            print(f"⚡ [Cache Hit] {ticker} - DB에서 즉시 지표를 불러옵니다.")
            return cached_data
            
        print(f"⏳ [Cache Miss] {ticker} - 듀얼 코어 엔진이 데이터를 수집합니다.")

        stats = {
            "ticker": ticker, "yesterday_price": 0.0, "sharp": 0.0,
            "beta": 0.0, "mdd": 0.0, "stand_dev": 0.0, 
            "last_updated": today_str, "months": self.months
        }
        
        try:
            df = self._fetch_hybrid_data(ticker).ffill().dropna()
            if df.empty: return stats

            is_korean = ticker.endswith('.KS') or ticker.endswith('.KQ')
            realtime_local_price = self._get_realtime_price(ticker, fallback_price=float(df['Close'].iloc[-1]))
            
            if not is_korean:
                fx_data = self._get_fx_data()
                combined = pd.DataFrame({'TR_Price': df['TR_Price'], 'fx': fx_data}).ffill().dropna()
                tr_krw = combined['TR_Price'] * combined['fx']
                
                current_fx = float(fx_data.iloc[-1])
                stats['yesterday_price'] = float(realtime_local_price * current_fx) 
            else:
                tr_krw = df['TR_Price']
                stats['yesterday_price'] = float(realtime_local_price)

            returns = tr_krw.pct_change().dropna()
            volatility = returns.std() * np.sqrt(252)
            stats['stand_dev'] = float(volatility)

            mean_return = returns.mean() * 252
            if volatility > 0:
                stats['sharp'] = float((mean_return - 0.02) / volatility)

            cum_returns = (1 + returns).cumprod()
            running_max = cum_returns.cummax()
            drawdown = (cum_returns / running_max) - 1
            stats['mdd'] = float(drawdown.min())

            bm_returns = self._get_benchmark_data()
            combined_bm = pd.DataFrame({'asset': returns, 'market': bm_returns}).dropna()
            if not combined_bm.empty and combined_bm['market'].var() > 0:
                cov = combined_bm['asset'].cov(combined_bm['market'])
                var = combined_bm['market'].var()
                stats['beta'] = float(cov / var)

            db.save_market_data(stats)

        except Exception as e:
            print(f"🚨 개별 종목 분석 실패 ({ticker}): {e}")

        return stats

    def analyze_portfolio(self, portfolio_items):
        stats = {
            "total_value": 0.0, "sharp": 0.0, "beta": 0.0, 
            "mdd": 0.0, "stand_dev": 0.0, "upside_dev": 0.0,
            "cum_return": 0.0, "cagr": 0.0, "simulated_profit": 0.0
        }
        if not portfolio_items: return stats

        try:
            real_total_value = 0.0 
            tr_port_value_series = None 
            fx_data = self._get_fx_data()

            for item in portfolio_items:
                t = item['ticker']
                q = item['quantity']
                df = self._fetch_hybrid_data(t).ffill().dropna()
                if df.empty: continue

                rt_local_price = self._get_realtime_price(t, fallback_price=float(df['Close'].iloc[-1]))
                is_korean = t.endswith('.KS') or t.endswith('.KQ')
                
                if is_korean:
                    real_total_value += rt_local_price * q
                    item_tr_value = df['TR_Price'] * q
                else:
                    current_fx = float(fx_data.iloc[-1])
                    real_total_value += (rt_local_price * current_fx) * q
                    
                    combined = pd.DataFrame({'TR_Price': df['TR_Price'], 'fx': fx_data}).ffill().dropna()
                    item_tr_value = combined['TR_Price'] * combined['fx'] * q

                if tr_port_value_series is None:
                    tr_port_value_series = item_tr_value
                else:
                    tr_port_value_series = tr_port_value_series.add(item_tr_value, fill_value=0)

            stats['total_value'] = float(real_total_value)
            if stats['total_value'] <= 0 or tr_port_value_series is None: return stats

            tr_port_value_series = tr_port_value_series.ffill().dropna()
            port_returns = tr_port_value_series.pct_change().dropna()
            
            volatility = port_returns.std() * np.sqrt(252)
            stats['stand_dev'] = float(volatility)

            upside_returns = port_returns[port_returns > 0]
            if not upside_returns.empty:
                stats['upside_dev'] = float(upside_returns.std() * np.sqrt(252))

            mean_return = port_returns.mean() * 252
            if volatility > 0:
                stats['sharp'] = float((mean_return - 0.02) / volatility)

            cum_returns = (1 + port_returns).cumprod()
            running_max = cum_returns.cummax()
            drawdown = (cum_returns / running_max) - 1
            stats['mdd'] = float(drawdown.min())

            if not cum_returns.empty:
                total_cum_return = cum_returns.iloc[-1] - 1
                stats['cum_return'] = float(total_cum_return)
                
                years = len(port_returns) / 252
                if years > 0:
                    stats['cagr'] = float((1 + total_cum_return) ** (1 / years) - 1)
                
                stats['simulated_profit'] = float(stats['total_value'] * total_cum_return)

            bm_returns = self._get_benchmark_data()
            combined_bm = pd.DataFrame({'port': port_returns, 'market': bm_returns}).dropna()
            
            if not combined_bm.empty and combined_bm['market'].var() > 0:
                cov = combined_bm['port'].cov(combined_bm['market'])
                var = combined_bm['market'].var()
                stats['beta'] = float(cov / var)

        except Exception as e:
            print(f"🚨 포트폴리오 종합 분석 실패: {e}")

        return stats
    
    def analyze_ticker(self, ticker):
        today_str = datetime.now().strftime('%Y-%m-%d')
        cached_data = db.get_market_data(ticker)
        
        if cached_data and cached_data.get('last_updated') == today_str and cached_data.get('months') == self.months:
            print(f"⚡ [Cache Hit] {ticker} - DB에서 즉시 지표를 불러옵니다.")
            return cached_data
            
        print(f"⏳ [Cache Miss] {ticker} - 듀얼 코어 엔진이 데이터를 수집합니다.")

        # 🚀 [수정 포인트 1] 초기 stats 딕셔너리에 cum_return과 cagr 추가
        stats = {
            "ticker": ticker, "yesterday_price": 0.0, "sharp": 0.0,
            "beta": 0.0, "mdd": 0.0, "stand_dev": 0.0, 
            "cum_return": 0.0, "cagr": 0.0,  # <-- 개별 종목 수익률용 자리표시자
            "last_updated": today_str, "months": self.months
        }
        
        try:
            df = self._fetch_hybrid_data(ticker).ffill().dropna()
            if df.empty: return stats

            is_korean = ticker.endswith('.KS') or ticker.endswith('.KQ')
            realtime_local_price = self._get_realtime_price(ticker, fallback_price=float(df['Close'].iloc[-1]))
            
            if not is_korean:
                fx_data = self._get_fx_data()
                combined = pd.DataFrame({'TR_Price': df['TR_Price'], 'fx': fx_data}).ffill().dropna()
                tr_krw = combined['TR_Price'] * combined['fx']
                
                current_fx = float(fx_data.iloc[-1])
                stats['yesterday_price'] = float(realtime_local_price * current_fx) 
            else:
                tr_krw = df['TR_Price']
                stats['yesterday_price'] = float(realtime_local_price)

            returns = tr_krw.pct_change().dropna()
            volatility = returns.std() * np.sqrt(252)
            stats['stand_dev'] = float(volatility)

            mean_return = returns.mean() * 252
            if volatility > 0:
                stats['sharp'] = float((mean_return - 0.02) / volatility)

            cum_returns = (1 + returns).cumprod()
            running_max = cum_returns.cummax()
            drawdown = (cum_returns / running_max) - 1
            stats['mdd'] = float(drawdown.min())

            # 🚀 [수정 포인트 2] 개별 종목 누적 수익률(cum_return) 및 연환산(CAGR) 계산 로직 추가
            if not cum_returns.empty:
                total_cum_return = cum_returns.iloc[-1] - 1
                stats['cum_return'] = float(total_cum_return)
                
                years = len(returns) / 252
                if years > 0:
                    stats['cagr'] = float((1 + total_cum_return) ** (1 / years) - 1)

            bm_returns = self._get_benchmark_data()
            combined_bm = pd.DataFrame({'asset': returns, 'market': bm_returns}).dropna()
            if not combined_bm.empty and combined_bm['market'].var() > 0:
                cov = combined_bm['asset'].cov(combined_bm['market'])
                var = combined_bm['market'].var()
                stats['beta'] = float(cov / var)

            db.save_market_data(stats)

        except Exception as e:
            print(f"🚨 개별 종목 분석 실패 ({ticker}): {e}")

        return stats