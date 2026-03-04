import flet as ft
from views.portfolio_view import PortfolioEditor
from views.dashboard_view import DashboardView

def main(page: ft.Page):
    page.title = "포트폴리오 전사: 무림편"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 900
    page.window.height = 800
    page.padding = 20
    
    # 1. 뷰 생성
    view_dashboard = DashboardView()

    # 🚀 [핵심 수정] 에러를 방지한 화면 전환 함수
    def move_to_dashboard():
        # 1. 최신 데이터 불러오기 (DB에서 데이터 꺼내기)
        view_dashboard.load_data() 
        
        # (주의: 화면에 붙기 전이므로 여기서 view_dashboard.update()를 하면 에러가 납니다!)
        
        # 2. 화면을 대시보드로 교체
        content_area.content = view_dashboard
        
        # 3. 탭 버튼 색상 변경
        btn_dash.bgcolor = "blue"
        btn_dash.color = "white"
        btn_input.bgcolor = "transparent"
        btn_input.color = "black"
        
        # 4. 페이지 전체 갱신 (이때 대시보드가 화면에 짠! 하고 나타납니다)
        page.update() 

    # 2. PortfolioEditor 생성 시, 강제 이동 함수 전달
    view_input = PortfolioEditor(on_analysis_complete=move_to_dashboard)

    # 3. 빈 도화지 준비 (처음엔 입력창 띄움)
    content_area = ft.Container(content=view_input, expand=True)

    # 4. 상단 탭 버튼 클릭 시 수동 전환 함수
    def switch_tab(e):
        if e.control.text == "비급 수집 (Input)":
            content_area.content = view_input
            btn_input.bgcolor = "blue"; btn_input.color = "white"
            btn_dash.bgcolor = "transparent"; btn_dash.color = "black"
        else:
            move_to_dashboard() 
        page.update()

    # 5. 커스텀 탭 메뉴 버튼
    btn_input = ft.ElevatedButton(
        "비급 수집 (Input)", 
        on_click=switch_tab, 
        bgcolor="blue", color="white"
    )
    btn_dash = ft.ElevatedButton(
        "내공 상태 (Dashboard)", 
        on_click=switch_tab, 
        bgcolor="transparent", color="black"
    )

    tab_menu = ft.Row([btn_input, btn_dash], alignment=ft.MainAxisAlignment.CENTER)

    # 6. 화면 배치
    page.add(
        tab_menu, 
        ft.Divider(thickness=2),
        content_area
    )

if __name__ == "__main__":
    ft.app(target=main)