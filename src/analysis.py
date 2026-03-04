import yfinance as yf
import pandas as pd
import numpy as np

class AnalysisEngine:
    def __init__(self):
        # 벤치마크(시장) 지수: S&P 500을 기준으로 삼습니다.
        self.benchmark_ticker = "^GSPC" 

    def _get_benchmark_data(self):
        """[내부 무공] 시장(S&P 500)의 1년 치 일일 수익률을 가져옵니다 (베타 계산용)."""
        try:
            bm_data = yf.download(self.benchmark_ticker, period="1y", progress=False)['Close']
            return bm_data.ffill().dropna().pct_change().dropna()
        except Exception as e:
            print(f"⚠️ 벤치마크 데이터 로드 실패: {e}")
            return pd.Series(dtype=float)

    def analyze_ticker(self, ticker):
        """
        [검술 분석] 개별 종목의 최근 종가 및 기본 스탯을 계산합니다.
        (표의 각 행에 들어갈 데이터)
        """
        stats = {
            "ticker": ticker,
            "yesterday_price": 0.0,
            "sharp": 0.0,
            "beta": 0.0,
            "mdd": 0.0,
            "stand_dev": 0.0
        }
        try:
            # 1. 1년 치 데이터 다운로드
            data = yf.download(ticker, period="1y", progress=False)['Close']
            
            # yfinance 버전에 따라 다를 수 있는 구조 통일화
            if isinstance(data, pd.DataFrame):
                data = data.iloc[:, 0]
                
            data = data.ffill().dropna()
            if data.empty: return stats

            # 최근 종가 저장
            stats['yesterday_price'] = float(data.iloc[-1])
            
            # 일일 수익률
            returns = data.pct_change().dropna()

            # 표준편차 (연율화)
            volatility = returns.std() * np.sqrt(252)
            stats['stand_dev'] = float(volatility)

            # 샤프 지수 (무위험 이자율 2% 가정)
            mean_return = returns.mean() * 252
            if volatility > 0:
                stats['sharp'] = float((mean_return - 0.02) / volatility)

            # MDD
            cum_returns = (1 + returns).cumprod()
            running_max = cum_returns.cummax()
            drawdown = (cum_returns / running_max) - 1
            stats['mdd'] = float(drawdown.min())

            # 베타
            bm_returns = self._get_benchmark_data()
            combined = pd.concat([returns, bm_returns], axis=1, join='inner')
            combined.columns = ['asset', 'market']
            if not combined.empty and combined['market'].var() > 0:
                cov = combined['asset'].cov(combined['market'])
                var = combined['market'].var()
                stats['beta'] = float(cov / var)

        except Exception as e:
            print(f"🚨 개별 종목 분석 실패 ({ticker}): {e}")

        return stats

    def analyze_portfolio(self, portfolio_items):
        """
        [진법 분석] 계좌 전체의 5대 핵심 지표(Sharpe, Beta, MDD, Std Dev, Upside Std Dev)와 총자산을 계산합니다.
        (대시보드 상단 요약 카드에 들어갈 데이터)
        """
        stats = {
            "total_value": 0.0, 
            "sharp": 0.0, 
            "beta": 0.0, 
            "mdd": 0.0, 
            "stand_dev": 0.0, 
            "upside_dev": 0.0
        }
        if not portfolio_items: return stats

        tickers = [item['ticker'] for item in portfolio_items]
        
        try:
            # 1. 포트폴리오 내 모든 종목의 1년 치 데이터를 한 번에 다운로드
            data = yf.download(tickers, period="1y", progress=False)['Close']
            
            # 종목이 1개일 경우 Series로 나오므로 DataFrame으로 변환
            if len(tickers) == 1:
                data = data.to_frame(name=tickers[0])
            data = data.ffill().dropna()

            # 2. 매일매일의 '내 계좌 총자산(일일 평가금액)' 흐름 계산
            daily_port_value = pd.Series(0.0, index=data.index)
            for item in portfolio_items:
                t = item['ticker']
                q = item['quantity']
                # 다운로드된 데이터 안에 해당 종목이 무사히 있을 경우 금액 합산
                if t in data.columns:
                    daily_port_value += data[t] * q

            # 현재 계좌 총자산 (가장 마지막 날짜의 평가금액)
            stats['total_value'] = float(daily_port_value.iloc[-1])
            if stats['total_value'] <= 0: return stats

            # 3. 계좌 전체의 일일 수익률 계산
            port_returns = daily_port_value.pct_change().dropna()

            # 4. [지표 1] 표준편차 (전체 변동성, 연율화)
            volatility = port_returns.std() * np.sqrt(252)
            stats['stand_dev'] = float(volatility)

            # 5. [지표 2] 업사이드 표준편차 (수익이 난 날들의 상승 변동성, 연율화)
            upside_returns = port_returns[port_returns > 0]
            if not upside_returns.empty:
                stats['upside_dev'] = float(upside_returns.std() * np.sqrt(252))

            # 6. [지표 3] 샤프 지수 (위험 대비 수익률, 무위험 이자율 2% 가정)
            mean_return = port_returns.mean() * 252
            if volatility > 0:
                stats['sharp'] = float((mean_return - 0.02) / volatility)

            # 7. [지표 4] MDD (최대 낙폭)
            cum_returns = (1 + port_returns).cumprod()
            running_max = cum_returns.cummax()
            drawdown = (cum_returns / running_max) - 1
            stats['mdd'] = float(drawdown.min())

            # 8. [지표 5] 베타 (시장 민감도)
            bm_returns = self._get_benchmark_data()
            combined = pd.concat([port_returns, bm_returns], axis=1, join='inner')
            combined.columns = ['port', 'market']
            if not combined.empty and combined['market'].var() > 0:
                cov = combined['port'].cov(combined['market'])
                var = combined['market'].var()
                stats['beta'] = float(cov / var)

        except Exception as e:
            print(f"🚨 포트폴리오 종합 분석 실패: {e}")

        return stats