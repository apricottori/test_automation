# ui/dialogs/__init__.py
# 이 파일을 통해 'ui/dialogs' 디렉토리가 Python 패키지로 인식됩니다.

from .loop_definition_dialog import LoopDefinitionDialog
from .excel_export_dialog import ExcelExportSettingsDialog # 파일 분리 후

print("ui.dialogs package initialized") # 패키지 로드 확인용 (선택 사항)