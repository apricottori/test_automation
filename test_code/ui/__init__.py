# ui/__init__.py
# 이 파일을 통해 'ui' 디렉토리가 Python 패키지로 인식됩니다.

# 예시: ui 패키지 내 주요 서브 모듈/패키지를 쉽게 임포트할 수 있도록 설정 (선택 사항)
from .tabs import SettingsTab, RegisterViewerTab, ResultsViewerTab, SequenceControllerTab
from .dialogs import LoopDefinitionDialog
from .widgets import ActionInputPanel, SavedSequencePanel

print("ui package initialized") # 패키지 로드 확인용 (선택 사항)