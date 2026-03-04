import flet as ft
import yfinance as yf
import threading
import pandas as pd
import requests
from data.database import db
from src.analysis import AnalysisEngine

_krx_cache_df = None

class PortfolioEditor(ft.UserControl):
    def __init__(self, on_analysis_complete=None):
        super().__init__()
        self.rows = []
        self.analysis_engine = AnalysisEngine()
        self.on_analysis_complete = on_analysis_complete
        
        self.paste_field = ft.TextField(
            label="[비급 전수] 엑셀 복사/붙여넣기 (종목 수량)",
            multiline=True, min_lines=3, max_lines=5,
            hint_text="예:\n삼성전자 10\nAAPL 5\n제주반도체 20",
            on_submit=self.parse_paste_data
        )
        
        self.btn_group_edit = ft.Row([
            ft.ElevatedButton("데이터 적용", on_click=self.parse_paste_data, icon=ft.icons.DOWNLOAD),
            ft.ElevatedButton("행 추가 (+)", on_click=self.add_empty_row),
            ft.ElevatedButton("선택 삭제", on_click=self.delete_selected, icon=ft.icons.DELETE, color="orange"),
            ft.ElevatedButton("전체 초기화", on_click=self.clear_all_data, icon=ft.icons.DELETE_FOREVER, color="red"),
        ])

        self.btn_confirm = ft.ElevatedButton(
            text="입력 완료 (Confirm)", 
            on_click=self.switch_to_confirm_mode, 
            icon=ft.icons.CHECK, 
            bgcolor="blue", color="white",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=20),
            width=200
        )

        self.btn_analyze = ft.ElevatedButton(
            text="분석 시작 (Save & Analyze)", 
            on_click=self.execute_analysis, 
            icon=ft.icons.ROCKET_LAUNCH, 
            bgcolor="green", color="white",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=20),
            visible=False
        )
        
        self.btn_cancel = ft.ElevatedButton(
            text="취소 (Unlock)", 
            on_click=self.cancel_confirm_mode, 
            icon=ft.icons.CANCEL, 
            color="grey",
            visible=False
        )

        # 🚀 [핵심 수정] DataColumn 자체에 너비를 강제 부여
        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("선택")),
                ft.DataColumn(ft.Text("종목명 / 티커")),
                ft.DataColumn(ft.Text("수량")),
                ft.DataColumn(ft.Text("상태")),
            ],
            rows=[]
        )

    def did_mount(self):
        self.rows.clear()
        self.data_table.rows.clear()
        current_user = "test_user"
        saved_portfolio = db.get_user_portfolio(current_user)
        for item in saved_portfolio:
            self.add_row(item['ticker'], item['quantity'])

    def build(self):
        return ft.Column([
            ft.Text("보유 비급 목록 (Portfolio)", size=20, weight="bold"),
            ft.Container(
                content=ft.Column([self.paste_field, self.btn_group_edit]),
                padding=10, border=ft.border.all(1, ft.colors.GREY_400), border_radius=10
            ),
            ft.Container(
                # 🚀 [핵심 해결] vertical_alignment=ft.CrossAxisAlignment.START 를 추가하여 표를 위쪽에 찰싹 붙입니다!
                content=ft.Row(
                    [self.data_table], 
                    scroll=ft.ScrollMode.ALWAYS,
                    vertical_alignment=ft.CrossAxisAlignment.START 
                ),
                border=ft.border.all(1, ft.colors.GREY_300), 
                border_radius=10, 
                padding=10, 
                height=300,
                alignment=ft.alignment.top_left # 🚀 컨테이너 내부 기준 위치도 상단 좌측으로 강제 고정
            ),
            ft.Container(
                content=ft.Row([self.btn_confirm, self.btn_analyze, self.btn_cancel], alignment=ft.MainAxisAlignment.CENTER),
                padding=20
            )
        ], scroll=ft.ScrollMode.ADAPTIVE)

    def _resolve_stock_info(self, user_input):
        global _krx_cache_df
        clean_input = user_input.replace(" ", "").upper()
        
        mapping = {
            "테슬라": "TSLA", "애플": "AAPL", "마이크로소프트": "MSFT", "엔비디아": "NVDA", "팔란티어":"PLTR",
            "구글": "GOOGL", "아마존": "AMZN", "메타": "META", "브로드컴": "AVGO",
            "티에스엠": "TSM", "AMD": "AMD", "인텔": "INTC", "마이크론": "MU",
            "스타벅스": "SBUX", "코카콜라": "KO", "나이키": "NKE", "리얼티인컴": "O",
            "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "카카오": "035720.KS", "네이버": "035420.KS",
            "현대차": "005380.KS", "기아": "000270.KS"
        }
        for key, val in mapping.items():
            if key.replace(" ", "").upper() == clean_input:
                return key, val
        for key, val in mapping.items():
            if val.upper() == clean_input:
                return key, val

        try:
            if _krx_cache_df is None:
                url = "https://raw.githubusercontent.com/corazzon/finance-data-analysis/main/krx.csv"
                df = pd.read_csv(url, dtype={'Symbol': str}) 
                df['CleanName'] = df['Name'].astype(str).str.replace(" ", "").str.upper()
                _krx_cache_df = df

            if _krx_cache_df is not None:
                match = _krx_cache_df[_krx_cache_df['CleanName'] == clean_input]
                if match.empty:
                    base_code = clean_input.replace(".KS", "").replace(".KQ", "")
                    match = _krx_cache_df[_krx_cache_df['Symbol'] == base_code]

                if not match.empty:
                    code = str(match.iloc[0]['Symbol']).zfill(6)
                    mkt = str(match.iloc[0].get('Market', 'KOSPI')).upper()
                    suffix = ".KQ" if 'KOSDAQ' in mkt else ".KS"
                    ticker = f"{code}{suffix}"
                    name = str(match.iloc[0]['Name'])
                    return name, ticker
        except Exception as e:
            pass

        try:
            url = f"https://query2.finance.yahoo.com/v1/finance/search?q={user_input}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                quotes = res.json().get('quotes', [])
                if quotes:
                    target_q = None
                    for q in quotes:
                        if q.get('symbol', '').endswith('.KS') or q.get('symbol', '').endswith('.KQ'):
                            target_q = q; break
                    if not target_q: target_q = quotes[0]
                    sym = target_q.get('symbol', '')
                    name = target_q.get('shortname', sym) 
                    return name, sym
        except:
            pass

        return user_input.upper(), user_input.upper()

    def add_row(self, ticker="", quantity=""):
        checkbox = ft.Checkbox()
        ticker_val = ticker.strip() if ticker else ""
        
        ticker_field = ft.TextField(
            value=ticker_val, 
            width=200,          
            dense=True,
            content_padding=10,
            on_change=lambda e: self.validate_row_change(e)
        )
        qty_field = ft.TextField(
            value=str(quantity), 
            width=120,          
            dense=True,
            content_padding=10,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        status_icon = ft.Icon(name=ft.icons.QUESTION_MARK, color="grey")
        
        row_controls = {
            "check": checkbox, 
            "ticker": ticker_field, 
            "qty": qty_field, 
            "status": status_icon,
            "actual_ticker": ticker_val.upper()
        }
        
        new_row = ft.DataRow(cells=[
            ft.DataCell(checkbox), ft.DataCell(ticker_field), ft.DataCell(qty_field), ft.DataCell(status_icon),
        ])
        
        ticker_field.data = row_controls 
        self.rows.append({"ui": new_row, "controls": row_controls})
        self.data_table.rows.append(new_row)
        self.update()
        
        if ticker_val: 
            self.validate_single_row(row_controls)

    def add_empty_row(self, e):
        self.add_row()

    def validate_row_change(self, e):
        row_controls = e.control.data
        self.validate_single_row(row_controls)

    def parse_paste_data(self, e):
        raw_text = self.paste_field.value
        if not raw_text: return
        lines = raw_text.strip().split('\n')
        count = 0
        for line in lines:
            line = line.strip()
            if not line: continue
            parts = line.rsplit(None, 1)
            if len(parts) == 2:
                ticker_part = parts[0].strip()
                qty_part = parts[1]
                qty_clean = ''.join(filter(str.isdigit, qty_part))
                if qty_clean:
                    self.add_row(ticker_part, qty_clean)
                    count += 1
        self.paste_field.value = ""
        self.update()
        if count > 0:
            self.page.snack_bar = ft.SnackBar(ft.Text(f"✅ {count}개의 종목이 표에 추가되었습니다."), bgcolor="green")
            self.page.snack_bar.open = True
            self.page.update()

    def validate_single_row(self, row_data):
        raw_input = row_data["ticker"].value.strip()
        if not raw_input:
            self._update_icon(row_data, ft.icons.QUESTION_MARK, "grey", "입력 대기")
            return

        self._update_icon(row_data, ft.icons.HOURGLASS_BOTTOM, "blue", "조회 중...")
        
        def _check():
            try:
                display_name, actual_ticker = self._resolve_stock_info(raw_input)
                
                if row_data["ticker"].value != display_name:
                    row_data["ticker"].value = display_name
                    row_data["ticker"].update()
                
                row_data["actual_ticker"] = actual_ticker

                stock = yf.Ticker(actual_ticker)
                is_valid = False
                try:
                    if stock.fast_info.get('lastPrice') is not None: is_valid = True
                    elif not stock.history(period="5d").empty: is_valid = True
                except:
                    if not stock.history(period="5d").empty: is_valid = True

                if is_valid: self._update_icon(row_data, ft.icons.CHECK_CIRCLE, "green", "확인 완료")
                else: self._update_icon(row_data, ft.icons.WARNING, "red", "확인 불가")
            except:
                self._update_icon(row_data, ft.icons.WARNING, "red", "오류 발생")

        threading.Thread(target=_check, daemon=True).start()

    def _update_icon(self, row_data, icon, color, tooltip):
        row_data["status"].name = icon
        row_data["status"].color = color
        row_data["status"].tooltip = tooltip
        row_data["status"].update()

    def delete_selected(self, e):
        self.rows = [row for row in self.rows if not row["controls"]["check"].value]
        self.data_table.rows = [row["ui"] for row in self.rows]
        self.update()

    def clear_all_data(self, e):
        self.rows.clear()
        self.data_table.rows.clear()
        current_user = "test_user"
        db.clear_portfolio(current_user)
        db.update_portfolio_summary(current_user, {
            "total_value": 0, "sharp": 0, "beta": 0, "mdd": 0, "stand_dev": 0, "upside_dev": 0
        })
        self.update()
        self.page.snack_bar = ft.SnackBar(ft.Text("🗑️ 삭제 완료!"), bgcolor="red")
        self.page.snack_bar.open = True
        self.page.update()

    def switch_to_confirm_mode(self, e):
        valid_cnt = sum(1 for r in self.rows if r["controls"]["status"].name == ft.icons.CHECK_CIRCLE)
        if valid_cnt == 0:
            self.page.snack_bar = ft.SnackBar(ft.Text("⚠️ 저장할 수 있는 검증된 종목이 없습니다."), bgcolor="red")
            self.page.snack_bar.open = True; self.page.update()
            return
        self.btn_group_edit.visible = False; self.paste_field.disabled = True
        self.btn_confirm.visible = False; self.btn_analyze.visible = True; self.btn_cancel.visible = True
        for r in self.rows:
            r["controls"]["ticker"].read_only = True; r["controls"]["qty"].read_only = True; r["controls"]["check"].disabled = True
        self.update()

    def cancel_confirm_mode(self, e):
        self.btn_group_edit.visible = True; self.paste_field.disabled = False
        self.btn_confirm.visible = True; self.btn_analyze.visible = False; self.btn_cancel.visible = False
        for r in self.rows:
            r["controls"]["ticker"].read_only = False; r["controls"]["qty"].read_only = False; r["controls"]["check"].disabled = False
        self.update()

    def execute_analysis(self, e):
        count = 0
        current_user = "test_user"
        self.page.snack_bar = ft.SnackBar(ft.Text("⏳ 분석 중..."), bgcolor="blue")
        self.page.snack_bar.open = True; self.page.update()

        db.clear_portfolio(current_user)
        portfolio_items = []

        for r in self.rows:
            if r["controls"]["status"].name == ft.icons.CHECK_CIRCLE:
                actual_ticker = r["controls"].get("actual_ticker", r["controls"]["ticker"].value).strip().upper()
                qty = float(r["controls"]["qty"].value)
                
                db.save_portfolio_item(current_user, actual_ticker, qty)
                stats = self.analysis_engine.analyze_ticker(actual_ticker)
                db.update_warrior_stats(stats)
                
                portfolio_items.append({'ticker': actual_ticker, 'quantity': qty})
                count += 1
        
        if portfolio_items:
            port_stats = self.analysis_engine.analyze_portfolio(portfolio_items)
            db.update_portfolio_summary(current_user, port_stats)
        else:
            db.update_portfolio_summary(current_user, {"total_value": 0, "sharp": 0, "beta": 0, "mdd": 0, "stand_dev": 0, "upside_dev": 0})
        
        self.page.snack_bar = ft.SnackBar(ft.Text(f"✅ {count}개 종목 분석 완료!"), bgcolor="green")
        self.page.snack_bar.open = True
        self.cancel_confirm_mode(e)
        
        if self.on_analysis_complete: 
            self.on_analysis_complete()