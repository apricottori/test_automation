# ui/tabs/__init__.py
# 이 파일을 통해 'ui/tabs' 디렉토리가 Python 패키지로 인식됩니다.

from .settings_tab import SettingsTab
from .reg_viewer_tab import RegisterViewerTab
from .results_viewer_tab import ResultsViewerTab
from .sequence_controller_tab import SequenceControllerTab

print("ui.tabs package initialized") # 패키지 로드 확인용 (선택 사항)