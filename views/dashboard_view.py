import flet as ft
import yfinance as yf
import threading
from data.database import db

class DashboardView(ft.UserControl):
    def __init__(self):
        super().__init__()
        
        self.current_fx = 1400.0
        self.fetch_fx_rate_in_background()

        self.currency_selector = ft.Dropdown(
            options=[
                ft.dropdown.Option("KRW", "🇰🇷 원화 (KRW)"),
                ft.dropdown.Option("USD", "🇺🇸 달러 (USD)")
            ],
            value="KRW",
            width=160,
            dense=True,
            on_change=self.on_currency_change
        )

        self.summary_cards = ft.Row(wrap=True, spacing=15, alignment=ft.MainAxisAlignment.CENTER)

        # 🚀 [업그레이드] 테이블에 수익률(CAGR) 등 중요 지표 컬럼 추가!
        self.stat_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("종목코드(비급)")),
                ft.DataColumn(ft.Text("보유 수량", text_align="right")),
                ft.DataColumn(ft.Text("최근 종가", text_align="right")),
                ft.DataColumn(ft.Text("누적 수익률", text_align="right")), # 🚀 신규
                ft.DataColumn(ft.Text("연환산(CAGR)", text_align="right")), # 🚀 신규
                ft.DataColumn(ft.Text("샤프 지수", text_align="right")),
                ft.DataColumn(ft.Text("베타", text_align="right")),
                ft.DataColumn(ft.Text("MDD", text_align="right")),
            ],
            rows=[],
            heading_row_color=ft.colors.BLUE_GREY_50,
        )

    def fetch_fx_rate_in_background(self):
        def _fetch():
            try:
                ticker = yf.Ticker("USDKRW=X")
                price = ticker.fast_info.get('lastPrice')
                if price:
                    self.current_fx = float(price)
                    print(f"🌍 [시스템] 최신 환율 업데이트 완료: 1$ = {self.current_fx:.2f}원")
            except Exception as e:
                print(f"⚠️ 실시간 환율 로드 실패 (1400원 고정): {e}")
        threading.Thread(target=_fetch, daemon=True).start()

    def on_currency_change(self, e):
        self.load_data()
        self.update()

    def _create_summary_card(self, title, value, value_color="black"):
        return ft.Card(
            elevation=4,
            content=ft.Container(
                content=ft.Column([
                    ft.Text(title, size=13, color="grey", weight="bold"),
                    ft.Text(value, size=22, weight="bold", color=value_color)
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=15, width=180, border_radius=10
            )
        )

    def build(self):
        return ft.Column([
            ft.Row([
                ft.Row([
                    ft.Icon(ft.icons.ANALYTICS, size=30, color="blue"),
                    ft.Text("나의 무공 상태창 (Dashboard)", size=24, weight="bold"),
                ]),
                self.currency_selector 
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            ft.Divider(thickness=2),
            ft.Container(content=self.summary_cards, padding=10),
            ft.Divider(thickness=1),
            ft.Text("개별 비급 상세 내역", size=18, weight="bold"),
            
            ft.Container(
                content=ft.Column([self.stat_table], scroll=ft.ScrollMode.ADAPTIVE),
                border=ft.border.all(1, ft.colors.GREY_300),
                border_radius=10, padding=10, expand=True
            )
        ], expand=True)

    def load_data(self):
        self.stat_table.rows.clear()
        self.summary_cards.controls.clear()
        
        current_user = "test_user"
        summary = db.get_portfolio_summary(current_user)
        
        is_usd = (self.currency_selector.value == "USD")
        
        if summary:
            tv_krw = summary.get('total_value') or 0.0
            sh = summary.get('sharp') or 0.0
            bt = summary.get('beta') or 0.0
            md = summary.get('mdd') or 0.0
            # 🚀 [추가] DB에서 새로운 수익 지표 가져오기
            cum_ret = summary.get('cum_return') or 0.0
            cagr = summary.get('cagr') or 0.0
            sim_profit = summary.get('simulated_profit') or 0.0
            
            # 🚀 금액 포맷 변환 (총 자산 및 백테스트 수익금)
            if is_usd:
                tv_display = f"$ {(tv_krw / self.current_fx):,.2f}"
                sim_profit_display = f"$ {(sim_profit / self.current_fx):,.2f}"
            else:
                tv_display = f"₩ {tv_krw:,.0f}"
                sim_profit_display = f"₩ {sim_profit:,.0f}"
            
            # 색상 설정 (+면 빨강/초록, -면 파랑)
            ret_color = "red" if cum_ret > 0 else "blue" if cum_ret < 0 else "black"
            
            # 🚀 [업그레이드] 요약 카드에 중요 지표 우선 배치!
            self.summary_cards.controls.extend([
                self._create_summary_card("총 자산 (Total)", tv_display, "black"),
                self._create_summary_card("가상 수익금 (TR)", sim_profit_display, ret_color),
                self._create_summary_card("누적 수익률", f"{cum_ret * 100:.2f} %", ret_color),
                self._create_summary_card("연평균 (CAGR)", f"{cagr * 100:.2f} %", ret_color),
                self._create_summary_card("MDD (최대 낙폭)", f"{md * 100:.2f} %", "blue" if md < -0.2 else "black"),
                self._create_summary_card("샤프 지수 (가성비)", f"{sh:.2f}", "green" if sh >= 1 else "black"),
            ])
        else:
            self.summary_cards.controls.append(
                ft.Text("데이터가 없습니다. 비급 수집 탭에서 종목을 넣고 분석을 실행해 주세요.", color="grey")
            )

        portfolio_data = db.get_user_portfolio_stats(current_user)
        for item in portfolio_data:
            price_krw = item.get('yesterday_price') or 0.0
            sharp = item.get('sharp') or 0.0
            beta = item.get('beta') or 0.0
            mdd = item.get('mdd') or 0.0
            # 🚀 개별 종목의 수익률 데이터 가져오기 (DB에 없다면 0으로 처리)
            item_cum_ret = item.get('cum_return') or 0.0
            item_cagr = item.get('cagr') or 0.0

            if is_usd:
                price_display = f"$ {(price_krw / self.current_fx):,.2f}"
            else:
                price_display = f"₩ {price_krw:,.0f}"

            item_color = "red" if item_cum_ret > 0 else "blue" if item_cum_ret < 0 else "black"

            # 🚀 [업그레이드] 테이블에 수익률과 CAGR 추가 표시!
            row = ft.DataRow(cells=[
                ft.DataCell(ft.Text(item['ticker'], weight="bold")),
                ft.DataCell(ft.Text(f"{item['quantity']:g}")),
                ft.DataCell(ft.Text(price_display)), 
                ft.DataCell(ft.Text(f"{item_cum_ret * 100:.2f}%", color=item_color, weight="bold")), # 누적 수익률
                ft.DataCell(ft.Text(f"{item_cagr * 100:.2f}%", color=item_color)), # 연환산(CAGR)
                ft.DataCell(ft.Text(f"{sharp:.2f}", color="green" if sharp >= 1.0 else None)),
                ft.DataCell(ft.Text(f"{beta:.2f}")),
                ft.DataCell(ft.Text(f"{mdd * 100:.2f} %", color="blue" if mdd < -0.2 else None)),
            ])
            self.stat_table.rows.append(row)
            
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