# main_app.py
import sys
from PyQt5.QtWidgets import QApplication, QStyleFactory # QApplication은 먼저 임포트
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt 

# core.constants는 스타일 및 폰트 설정에 필요하므로 먼저 임포트 할 수 있습니다.
# 다만, constants 모듈 자체가 다른 core 모듈을 임포트하지 않도록 주의해야 합니다.
# 만약 constants가 hardware_control 등을 임포트한다면 이마저도 늦춰야 합니다.
# 현재 제공된 constants.py는 다른 core 모듈을 직접 임포트하지 않는 것으로 보입니다.
from core import constants

def main():
    """
    애플리케이션의 메인 실행 함수입니다.
    QApplication을 생성하고, 메인 윈도우를 설정 및 표시한 후, 이벤트 루프를 시작합니다.
    """
    
    app = QApplication(sys.argv)

    # --- 애플리케이션 폰트 설정 ---
    default_font_family = getattr(constants, 'APP_FONT', '맑은 고딕') 
    if sys.platform == "darwin": 
        default_font_family = getattr(constants, 'APP_FONT_MACOS', 'Apple SD Gothic Neo')
    elif "linux" in sys.platform: 
        default_font_family = getattr(constants, 'APP_FONT_LINUX', 'Noto Sans KR') 

    default_font_size = getattr(constants, 'APP_FONT_SIZE', 10) 
    app.setFont(QFont(default_font_family, default_font_size))
    print(f"Application Font: {app.font().family()}, {app.font().pointSize()}pt (Platform: {sys.platform})")

    # --- 애플리케이션 스타일 설정 ---
    available_styles = QStyleFactory.keys()
    preferred_styles = ["Fusion", "WindowsVista", "Windows", "GTK+", "macOS"] 
    applied_style_name = None

    for style_key in preferred_styles:
        matched_style = next((s for s in available_styles if s.lower() == style_key.lower()), None)
        if matched_style:
            if style_key.lower() == "windowsvista" and sys.platform != "win32": continue
            if style_key.lower() == "windows" and sys.platform != "win32": continue
            if style_key.lower() == "macos" and sys.platform != "darwin": continue
            if style_key.lower() == "gtk+" and "linux" not in sys.platform: continue

            try:
                app.setStyle(QStyleFactory.create(matched_style))
                applied_style_name = matched_style
                break 
            except Exception as e: 
                print(f"Warning: Could not apply style '{matched_style}'. Error: {e}")
    
    if applied_style_name:
        print(f"Application Style: {app.style().objectName()} (Applied: {applied_style_name})")
    else:
        print(f"Warning: Could not apply any preferred styles. Using default system style: {app.style().objectName()}")

    # --- 메인 윈도우 생성 및 실행 ---
    # RegMapWindow 및 관련 core 모듈 임포트를 이 시점으로 이동
    # 이는 RegMapWindow 생성자 내에서 초기화되는 hardware_control 등이
    # QApplication 생성 이후에 로드되도록 하기 위함입니다.
    try:
        from main_window import RegMapWindow # 임포트 시점 변경
        # from core import ... # 만약 main_window 외 다른 core 모듈이 main()에서 직접 필요하다면 여기서 임포트

        window = RegMapWindow() 
        window.show()
        exit_code = app.exec_()
        sys.exit(exit_code)
    except Exception as e:
        print(f"FATAL ERROR: Could not start the application.")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {e}")
        import traceback
        traceback.print_exc()
        # QMessageBox는 QApplication 루프가 시작된 후에 안정적으로 표시될 수 있으므로,
        # 여기서 직접 사용하기보다는 print로 오류를 남기는 것이 더 안전할 수 있습니다.
        # try-except 블록이 main 함수 전체를 감싸므로, 심각한 오류 시 여기서 종료됩니다.
        sys.exit(1) 

if __name__ == '__main__':
    main()