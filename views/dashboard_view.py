import flet as ft
from data.database import db

class DashboardView(ft.UserControl):
    def __init__(self):
        super().__init__()
        
        # [상단] 계좌 요약 카드 영역 (카드가 6개로 늘어났으므로 wrap=True로 자동 줄바꿈 처리)
        self.summary_cards = ft.Row(wrap=True, spacing=15, alignment=ft.MainAxisAlignment.CENTER)

        # [하단] 개별 비급(종목) 테이블
        self.stat_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("종목코드(비급)")),
                ft.DataColumn(ft.Text("보유 수량", text_align="right")),
                ft.DataColumn(ft.Text("최근 종가($)", text_align="right")),
                ft.DataColumn(ft.Text("샤프 지수", text_align="right")),
                ft.DataColumn(ft.Text("베타", text_align="right")),
                ft.DataColumn(ft.Text("MDD", text_align="right")),
            ],
            rows=[],
            heading_row_color=ft.colors.BLUE_GREY_50,
        )

    def _create_summary_card(self, title, value, value_color="black"):
        """요약 카드를 예쁘게 생성해 주는 내부 도우미 함수"""
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
        # 화면의 전체적인 뼈대 구조를 조립합니다.
        return ft.Column([
            ft.Row([
                ft.Icon(ft.icons.ANALYTICS, size=30, color="blue"),
                ft.Text("나의 무공 상태창 (Dashboard)", size=24, weight="bold"),
            ]),
            
            ft.Divider(thickness=2),
            
            # 상단 6개의 요약 카드 컨테이너
            ft.Container(content=self.summary_cards, padding=10),
            
            ft.Divider(thickness=1),
            ft.Text("개별 비급 상세 내역", size=18, weight="bold"),
            
            # 하단 개별 종목 테이블 컨테이너 (종목이 많아지면 스크롤 가능)
            ft.Container(
                content=ft.Column([self.stat_table], scroll=ft.ScrollMode.ADAPTIVE),
                border=ft.border.all(1, ft.colors.GREY_300),
                border_radius=10, padding=10, expand=True
            )
        ], expand=True)

    def load_data(self):
        """DB에서 데이터를 불러와 화면(카드와 표)을 최신 상태로 갱신합니다."""
        # 기존 화면에 있던 내용 초기화
        self.stat_table.rows.clear()
        self.summary_cards.controls.clear()
        
        current_user = "test_user"
        
        # 1. 포트폴리오 전체 5대 종합 스탯 + 총 자산 불러오기
        summary = db.get_portfolio_summary(current_user)
        
        if summary:
            # DB 값이 비어있을(None) 경우를 대비한 안전망(or 0.0) 처리
            tv = summary.get('total_value') or 0.0
            sh = summary.get('sharp') or 0.0
            bt = summary.get('beta') or 0.0
            md = summary.get('mdd') or 0.0
            std = summary.get('stand_dev') or 0.0
            up_std = summary.get('upside_dev') or 0.0
            
            # 카드 6개 생성 및 화면 부착
            self.summary_cards.controls.extend([
                self._create_summary_card("총 자산 (Total)", f"$ {tv:,.2f}", "blue"),
                self._create_summary_card("샤프 지수", f"{sh:.2f}", "green" if sh >= 1 else "black"),
                self._create_summary_card("베타 (vs S&P500)", f"{bt:.2f}"),
                self._create_summary_card("MDD", f"{md * 100:.2f} %", "red" if md < -0.2 else "black"),
                self._create_summary_card("표준편차 (위험)", f"{std * 100:.2f} %"),
                self._create_summary_card("업사이드 표준편차", f"{up_std * 100:.2f} %", "green")
            ])
        else:
            self.summary_cards.controls.append(
                ft.Text("데이터가 없습니다. 비급 수집 탭에서 종목을 넣고 분석을 실행해 주세요.", color="grey")
            )

        # 2. 하단 개별 종목 데이터 불러오기 및 표(Table) 채우기
        portfolio_data = db.get_user_portfolio_stats(current_user)
        for item in portfolio_data:
            price = item.get('yesterday_price') or 0.0
            sharp = item.get('sharp') or 0.0
            beta = item.get('beta') or 0.0
            mdd = item.get('mdd') or 0.0

            row = ft.DataRow(cells=[
                ft.DataCell(ft.Text(item['ticker'], weight="bold")),
                ft.DataCell(ft.Text(f"{item['quantity']:g}")),
                ft.DataCell(ft.Text(f"{price:,.2f}")),
                # 샤프 지수는 1.0 이상이면 초록색으로 칭찬해줍니다.
                ft.DataCell(ft.Text(f"{sharp:.2f}", color="green" if sharp >= 1.0 else None)),
                ft.DataCell(ft.Text(f"{beta:.2f}")),
                # MDD는 -20% 이하면 빨간색으로 경고해줍니다.
                ft.DataCell(ft.Text(f"{mdd * 100:.2f} %", color="red" if mdd < -0.2 else None)),
            ])
            self.stat_table.rows.append(row)