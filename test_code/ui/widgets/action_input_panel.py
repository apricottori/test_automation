# ui/widgets/action_input_panel.py
import sys
from typing import List, Tuple, Dict, Any, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QStackedWidget, QGridLayout, QDoubleSpinBox, QCompleter, QTabWidget,
    QMessageBox, QApplication, QStyle
)
from PyQt5.QtCore import Qt, QRegularExpression, QStringListModel, pyqtSignal
from PyQt5.QtGui import QRegularExpressionValidator, QFont, QDoubleValidator

from core import constants # constants 모듈 임포트
from core.helpers import normalize_hex_input
from core.register_map_backend import RegisterMap
from core.data_models import SimpleActionItem, LoopActionItem, SequenceItem


class ActionInputPanel(QWidget):
    """
    SequenceControllerTab의 좌측 상단, 액션 그룹 탭 및
    각 액션의 파라미터 입력을 담당하는 위젯입니다.
    """

    # 각 액션 그룹별 파라미터 UI 페이지 인덱스를 위한 내부 클래스
    class I2CParamPages:
        WRITE_NAME = 0
        WRITE_ADDR = 1
        READ_NAME = 2
        READ_ADDR = 3
        DELAY = 4
        PLACEHOLDER = 5 # 선택된 액션이 없을 때 표시될 페이지

    class DMMParamPages:
        MEASURE = 0
        SET_TERMINAL = 1
        PLACEHOLDER = 2

    class SMUParamPages:
        SET_VALUE = 0
        MEASURE = 1
        ENABLE_OUTPUT = 2
        SET_TERMINAL = 3
        SET_PROTECTION_I = 4
        PLACEHOLDER = 5

    class TempParamPages:
        SET_TEMP = 0
        CHECK_TEMP = 1
        PLACEHOLDER = 2


    def __init__(self,
                 completer_model: QStringListModel,
                 current_settings: Dict[str, Any],
                 register_map_instance: Optional[RegisterMap],
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.completer_model = completer_model
        self.current_settings = current_settings if current_settings is not None else {}
        self.register_map = register_map_instance

        # UI 멤버 변수 초기화 (타입 힌트 포함)
        self.action_group_tabs: Optional[QTabWidget] = None

        # I2C/Delay 탭 UI 요소
        self.i2c_tab_widget: Optional[QWidget] = None
        self.i2c_action_combo: Optional[QComboBox] = None
        self.i2c_params_stack: Optional[QStackedWidget] = None
        self.i2c_write_name_target_input: Optional[QLineEdit] = None
        self.i2c_write_name_value_input: Optional[QLineEdit] = None
        self.i2c_write_addr_target_input: Optional[QLineEdit] = None
        self.i2c_write_addr_value_input: Optional[QLineEdit] = None
        self.i2c_read_name_target_input: Optional[QLineEdit] = None
        self.i2c_read_name_var_name_input: Optional[QLineEdit] = None
        self.i2c_read_addr_target_input: Optional[QLineEdit] = None
        self.i2c_read_addr_var_name_input: Optional[QLineEdit] = None
        self.delay_seconds_input: Optional[QDoubleSpinBox] = None

        # DMM 탭 UI 요소
        self.dmm_tab_widget: Optional[QWidget] = None
        self.dmm_action_combo: Optional[QComboBox] = None
        self.dmm_params_stack: Optional[QStackedWidget] = None
        self.dmm_measure_var_name_input: Optional[QLineEdit] = None
        self.dmm_terminal_combo: Optional[QComboBox] = None # DMM 터미널 설정용

        # SMU 탭 UI 요소
        self.smu_tab_widget: Optional[QWidget] = None
        self.smu_action_combo: Optional[QComboBox] = None
        self.smu_params_stack: Optional[QStackedWidget] = None
        self.smu_set_value_label: Optional[QLabel] = None # 전압/전류 설정 시 라벨 텍스트 변경용
        self.smu_set_value_input: Optional[QLineEdit] = None
        self.smu_set_terminal_combo: Optional[QComboBox] = None # SMU 값 설정 시 터미널 선택
        self.smu_measure_var_name_input: Optional[QLineEdit] = None
        self.smu_measure_terminal_combo: Optional[QComboBox] = None # SMU 측정 시 터미널 선택
        self.smu_output_state_combo: Optional[QComboBox] = None
        self.smu_terminal_combo: Optional[QComboBox] = None # SMU 터미널 '설정' 액션용
        self.smu_protection_current_input: Optional[QLineEdit] = None

        # Chamber 탭 UI 요소
        self.temp_tab_widget: Optional[QWidget] = None
        self.temp_action_combo: Optional[QComboBox] = None
        self.temp_params_stack: Optional[QStackedWidget] = None
        self.chamber_set_temp_input: Optional[QLineEdit] = None
        self.chamber_check_target_temp_input: Optional[QLineEdit] = None
        self.chamber_check_tolerance_input: Optional[QLineEdit] = None
        self.chamber_check_timeout_input: Optional[QLineEdit] = None

        # 유효성 검사기
        self._hex_validator = QRegularExpressionValidator(QRegularExpression("[0-9A-Fa-fXx]*"))
        self._double_validator = QDoubleValidator()
        self._double_validator.setNotation(QDoubleValidator.StandardNotation)
        self._double_validator.setDecimals(6) # 소수점 6자리까지 허용

        self._setup_ui()
        self.update_settings(self.current_settings) # 초기 설정값으로 UI 업데이트

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0) # 패널 자체의 여백 제거

        self.action_group_tabs = QTabWidget()
        self.action_group_tabs.currentChanged.connect(self._update_active_sub_tab_fields) # 탭 변경 시 UI 업데이트

        # 각 액션 그룹별 서브 탭 생성
        self._create_i2c_delay_sub_tab()
        self._create_dmm_sub_tab()
        self._create_smu_sub_tab()
        self._create_temp_sub_tab()

        main_layout.addWidget(self.action_group_tabs)
        self._update_active_sub_tab_fields() # 초기 활성 탭 UI 업데이트

    def _normalize_hex_field(self, line_edit: QLineEdit, num_chars: Optional[int] = None, add_prefix: bool = True):
        """QLineEdit의 16진수 입력을 정규화하고 유효성을 검사합니다."""
        if not line_edit: return
        current_text = line_edit.text()
        original_tooltip = line_edit.toolTip() # 기존 툴팁 저장

        normalized_text = normalize_hex_input(current_text, num_chars, add_prefix=add_prefix)

        if normalized_text is None and current_text.strip(): # 정규화 실패했고, 입력값이 있었던 경우
            line_edit.setToolTip(f"Invalid hex value: '{current_text}'. Please enter a valid hex string (e.g., 0xAB or FF).")
            line_edit.setStyleSheet("border: 1px solid red;") # 오류 표시
        elif normalized_text is not None: # 정규화 성공
            line_edit.setText(normalized_text)
            line_edit.setToolTip(original_tooltip if original_tooltip else "") # 기존 툴팁 복원 또는 기본값
            line_edit.setStyleSheet("") # 오류 스타일 제거
        else: # 정규화 결과도 None이고, 원래 입력도 비어있던 경우 (또는 normalize_hex_input 로직 변경 시)
            line_edit.setToolTip(original_tooltip if original_tooltip else "")
            line_edit.setStyleSheet("")
            if not current_text.strip() and normalized_text: # 원래 비었는데 정규화 결과가 있는 경우 (예: "0x0")
                 line_edit.setText(normalized_text)


    def _create_i2c_delay_sub_tab(self):
        """I2C 및 Delay 액션 입력을 위한 UI를 생성합니다."""
        tab = QWidget()
        self.i2c_tab_widget = tab # 멤버 변수에 할당
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8,12,8,8); layout.setSpacing(10) # 내부 여백 및 간격

        layout.addWidget(QLabel("<b>I2C/Delay Action:</b>"))
        self.i2c_action_combo = QComboBox()
        # constants.py에서 정의된 리스트 사용 (이름 변경됨)
        self.i2c_action_combo.addItems(constants.I2C_DELAY_ACTIONS_LIST)
        self.i2c_action_combo.currentIndexChanged.connect(self._update_active_sub_tab_fields)
        layout.addWidget(self.i2c_action_combo)

        self.i2c_params_stack = QStackedWidget()
        self._create_i2c_delay_params_widgets() # 파라미터 입력 위젯들 생성
        layout.addWidget(self.i2c_params_stack)
        layout.addStretch() # 위젯들을 위로 밀착
        self.action_group_tabs.addTab(tab, constants.SEQ_SUB_TAB_I2C_TITLE)

    def _create_i2c_delay_params_widgets(self):
        """I2C/Delay 액션별 파라미터 입력 위젯들을 생성하고 QStackedWidget에 추가합니다."""
        completer = QCompleter(self.completer_model, self) # 자동완성 모델 설정
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)

        # I2C Write (Name) 페이지
        page_i2c_write_name = QWidget()
        layout_i2c_write_name = QGridLayout(page_i2c_write_name)
        layout_i2c_write_name.setVerticalSpacing(12); layout_i2c_write_name.setHorizontalSpacing(8)
        layout_i2c_write_name.addWidget(QLabel(constants.SEQ_INPUT_REG_NAME_LABEL), 0, 0)
        self.i2c_write_name_target_input = QLineEdit()
        self.i2c_write_name_target_input.setPlaceholderText(constants.SEQ_INPUT_REG_NAME_PLACEHOLDER)
        self.i2c_write_name_target_input.setCompleter(completer)
        layout_i2c_write_name.addWidget(self.i2c_write_name_target_input, 0, 1)
        layout_i2c_write_name.addWidget(QLabel(constants.SEQ_INPUT_I2C_VALUE_LABEL), 1, 0)
        self.i2c_write_name_value_input = QLineEdit()
        self.i2c_write_name_value_input.setPlaceholderText(constants.SEQ_INPUT_I2C_VALUE_PLACEHOLDER)
        self.i2c_write_name_value_input.setValidator(self._hex_validator)
        self.i2c_write_name_value_input.editingFinished.connect(lambda le=self.i2c_write_name_value_input: self._normalize_hex_field(le, add_prefix=True))
        layout_i2c_write_name.addWidget(self.i2c_write_name_value_input, 1, 1)
        self.i2c_params_stack.addWidget(page_i2c_write_name)

        # I2C Write (Address) 페이지
        page_i2c_write_addr = QWidget()
        layout_i2c_write_addr = QGridLayout(page_i2c_write_addr)
        layout_i2c_write_addr.setVerticalSpacing(12); layout_i2c_write_addr.setHorizontalSpacing(8)
        layout_i2c_write_addr.addWidget(QLabel(constants.SEQ_INPUT_I2C_ADDR_LABEL), 0, 0)
        self.i2c_write_addr_target_input = QLineEdit()
        self.i2c_write_addr_target_input.setPlaceholderText(constants.SEQ_INPUT_I2C_ADDR_PLACEHOLDER)
        self.i2c_write_addr_target_input.setValidator(self._hex_validator)
        self.i2c_write_addr_target_input.editingFinished.connect(lambda le=self.i2c_write_addr_target_input, nc=4: self._normalize_hex_field(le, nc, add_prefix=True)) # 주소는 4자리로 정규화
        layout_i2c_write_addr.addWidget(self.i2c_write_addr_target_input, 0, 1)
        layout_i2c_write_addr.addWidget(QLabel(constants.SEQ_INPUT_I2C_VALUE_LABEL), 1, 0)
        self.i2c_write_addr_value_input = QLineEdit()
        self.i2c_write_addr_value_input.setPlaceholderText(constants.SEQ_INPUT_I2C_VALUE_PLACEHOLDER)
        self.i2c_write_addr_value_input.setValidator(self._hex_validator)
        self.i2c_write_addr_value_input.editingFinished.connect(lambda le=self.i2c_write_addr_value_input, nc=2: self._normalize_hex_field(le, nc, add_prefix=True)) # 값은 2자리(1바이트)로 정규화
        layout_i2c_write_addr.addWidget(self.i2c_write_addr_value_input, 1, 1)
        self.i2c_params_stack.addWidget(page_i2c_write_addr)

        # I2C Read (Name) 페이지
        page_i2c_read_name = QWidget()
        layout_i2c_read_name = QGridLayout(page_i2c_read_name)
        layout_i2c_read_name.setVerticalSpacing(12); layout_i2c_read_name.setHorizontalSpacing(8)
        layout_i2c_read_name.addWidget(QLabel(constants.SEQ_INPUT_REG_NAME_LABEL), 0, 0)
        self.i2c_read_name_target_input = QLineEdit()
        self.i2c_read_name_target_input.setPlaceholderText(constants.SEQ_INPUT_REG_NAME_PLACEHOLDER)
        self.i2c_read_name_target_input.setCompleter(completer)
        layout_i2c_read_name.addWidget(self.i2c_read_name_target_input, 0, 1)
        layout_i2c_read_name.addWidget(QLabel(constants.SEQ_INPUT_SAVE_AS_LABEL), 1, 0)
        self.i2c_read_name_var_name_input = QLineEdit()
        self.i2c_read_name_var_name_input.setPlaceholderText(constants.SEQ_INPUT_SAVE_AS_PLACEHOLDER)
        layout_i2c_read_name.addWidget(self.i2c_read_name_var_name_input, 1, 1)
        self.i2c_params_stack.addWidget(page_i2c_read_name)

        # I2C Read (Address) 페이지
        page_i2c_read_addr = QWidget()
        layout_i2c_read_addr = QGridLayout(page_i2c_read_addr)
        layout_i2c_read_addr.setVerticalSpacing(12); layout_i2c_read_addr.setHorizontalSpacing(8)
        layout_i2c_read_addr.addWidget(QLabel(constants.SEQ_INPUT_I2C_ADDR_LABEL), 0, 0)
        self.i2c_read_addr_target_input = QLineEdit()
        self.i2c_read_addr_target_input.setPlaceholderText(constants.SEQ_INPUT_I2C_ADDR_PLACEHOLDER)
        self.i2c_read_addr_target_input.setValidator(self._hex_validator)
        self.i2c_read_addr_target_input.editingFinished.connect(lambda le=self.i2c_read_addr_target_input, nc=4: self._normalize_hex_field(le, nc, add_prefix=True))
        layout_i2c_read_addr.addWidget(self.i2c_read_addr_target_input, 0, 1)
        layout_i2c_read_addr.addWidget(QLabel(constants.SEQ_INPUT_SAVE_AS_LABEL), 1, 0)
        self.i2c_read_addr_var_name_input = QLineEdit()
        self.i2c_read_addr_var_name_input.setPlaceholderText(constants.SEQ_INPUT_SAVE_AS_PLACEHOLDER)
        layout_i2c_read_addr.addWidget(self.i2c_read_addr_var_name_input, 1, 1)
        self.i2c_params_stack.addWidget(page_i2c_read_addr)

        # Delay 페이지
        page_delay = QWidget()
        layout_delay = QGridLayout(page_delay)
        layout_delay.setVerticalSpacing(12); layout_delay.setHorizontalSpacing(8)
        layout_delay.addWidget(QLabel(constants.SEQ_INPUT_DELAY_LABEL), 0, 0)
        self.delay_seconds_input = QDoubleSpinBox()
        self.delay_seconds_input.setMinimum(0.001); self.delay_seconds_input.setMaximum(3600.0 * 24) # 최대 24시간
        self.delay_seconds_input.setDecimals(3); self.delay_seconds_input.setValue(0.01) # 기본값 10ms
        layout_delay.addWidget(self.delay_seconds_input, 0, 1)
        self.i2c_params_stack.addWidget(page_delay)

        # Placeholder 페이지 (아무 액션도 선택되지 않았을 때)
        page_placeholder_i2c = QWidget()
        layout_placeholder_i2c = QVBoxLayout(page_placeholder_i2c)
        layout_placeholder_i2c.addWidget(QLabel("Select an I2C/Delay action above."), alignment=Qt.AlignCenter)
        self.i2c_params_stack.addWidget(page_placeholder_i2c)

    def _create_dmm_sub_tab(self):
        """DMM 액션 입력을 위한 UI를 생성합니다."""
        tab = QWidget(); self.dmm_tab_widget = tab
        layout = QVBoxLayout(tab); layout.setContentsMargins(8,12,8,8); layout.setSpacing(10)
        layout.addWidget(QLabel("<b>DMM Action:</b>"))
        self.dmm_action_combo = QComboBox()
        self.dmm_action_combo.addItems(constants.DMM_ACTIONS_LIST) # 수정된 상수명 사용
        self.dmm_action_combo.currentIndexChanged.connect(self._update_active_sub_tab_fields)
        layout.addWidget(self.dmm_action_combo)
        self.dmm_params_stack = QStackedWidget()
        self._create_dmm_params_widgets()
        layout.addWidget(self.dmm_params_stack)
        layout.addStretch()
        self.action_group_tabs.addTab(tab, constants.SEQ_SUB_TAB_DMM_TITLE)

    def _create_dmm_params_widgets(self):
        """DMM 액션별 파라미터 입력 위젯들을 생성합니다."""
        # DMM Measure (Voltage/Current) 페이지
        page_dmm_measure = QWidget()
        layout_dmm_measure = QGridLayout(page_dmm_measure)
        layout_dmm_measure.setVerticalSpacing(12); layout_dmm_measure.setHorizontalSpacing(8)
        layout_dmm_measure.addWidget(QLabel(constants.SEQ_INPUT_SAVE_AS_LABEL), 0, 0)
        self.dmm_measure_var_name_input = QLineEdit()
        self.dmm_measure_var_name_input.setPlaceholderText(constants.SEQ_INPUT_SAVE_AS_PLACEHOLDER)
        layout_dmm_measure.addWidget(self.dmm_measure_var_name_input, 0, 1)
        self.dmm_params_stack.addWidget(page_dmm_measure)

        # DMM Set Terminal 페이지
        page_dmm_set_terminal = QWidget()
        layout_dmm_set_terminal = QGridLayout(page_dmm_set_terminal)
        layout_dmm_set_terminal.setVerticalSpacing(12); layout_dmm_set_terminal.setHorizontalSpacing(8)
        layout_dmm_set_terminal.addWidget(QLabel(constants.SEQ_INPUT_TERMINAL_LABEL), 0, 0)
        self.dmm_terminal_combo = QComboBox()
        self.dmm_terminal_combo.addItems([constants.TERMINAL_FRONT, constants.TERMINAL_REAR])
        layout_dmm_set_terminal.addWidget(self.dmm_terminal_combo, 0, 1)
        self.dmm_params_stack.addWidget(page_dmm_set_terminal)

        # Placeholder 페이지
        page_placeholder_dmm = QWidget()
        layout_placeholder_dmm = QVBoxLayout(page_placeholder_dmm)
        layout_placeholder_dmm.addWidget(QLabel("Select a DMM action above."), alignment=Qt.AlignCenter)
        self.dmm_params_stack.addWidget(page_placeholder_dmm)

    def _create_smu_sub_tab(self):
        """SMU 액션 입력을 위한 UI를 생성합니다."""
        tab = QWidget(); self.smu_tab_widget = tab
        layout = QVBoxLayout(tab); layout.setContentsMargins(8,12,8,8); layout.setSpacing(10)
        layout.addWidget(QLabel("<b>SMU Action:</b>"))
        self.smu_action_combo = QComboBox()
        self.smu_action_combo.addItems(constants.SMU_ACTIONS_LIST) # 수정된 상수명 사용
        self.smu_action_combo.currentIndexChanged.connect(self._update_active_sub_tab_fields)
        layout.addWidget(self.smu_action_combo)
        self.smu_params_stack = QStackedWidget()
        self._create_smu_params_widgets()
        layout.addWidget(self.smu_params_stack)
        layout.addStretch()
        self.action_group_tabs.addTab(tab, constants.SEQ_SUB_TAB_SMU_TITLE)

    def _create_smu_params_widgets(self):
        """SMU 액션별 파라미터 입력 위젯들을 생성합니다."""
        # SMU Set Value (Voltage/Current) 페이지
        page_smu_set = QWidget()
        layout_smu_set = QGridLayout(page_smu_set)
        layout_smu_set.setVerticalSpacing(12); layout_smu_set.setHorizontalSpacing(8)
        self.smu_set_value_label = QLabel(constants.SEQ_INPUT_NUMERIC_VALUE_LABEL) # 라벨 텍스트는 동적으로 변경됨
        layout_smu_set.addWidget(self.smu_set_value_label, 0, 0)
        self.smu_set_value_input = QLineEdit()
        self.smu_set_value_input.setValidator(self._double_validator)
        self.smu_set_value_input.setPlaceholderText(constants.SEQ_INPUT_NUMERIC_VALUE_PLACEHOLDER)
        layout_smu_set.addWidget(self.smu_set_value_input, 0, 1)
        layout_smu_set.addWidget(QLabel(constants.SEQ_INPUT_TERMINAL_LABEL), 1, 0)
        self.smu_set_terminal_combo = QComboBox()
        self.smu_set_terminal_combo.addItems([constants.TERMINAL_FRONT, constants.TERMINAL_REAR])
        layout_smu_set.addWidget(self.smu_set_terminal_combo, 1, 1)
        self.smu_params_stack.addWidget(page_smu_set)

        # SMU Measure (Voltage/Current) 페이지
        page_smu_measure = QWidget()
        layout_smu_measure = QGridLayout(page_smu_measure)
        layout_smu_measure.setVerticalSpacing(12); layout_smu_measure.setHorizontalSpacing(8)
        layout_smu_measure.addWidget(QLabel(constants.SEQ_INPUT_SAVE_AS_LABEL), 0, 0)
        self.smu_measure_var_name_input = QLineEdit()
        self.smu_measure_var_name_input.setPlaceholderText(constants.SEQ_INPUT_SAVE_AS_PLACEHOLDER)
        layout_smu_measure.addWidget(self.smu_measure_var_name_input, 0, 1)
        layout_smu_measure.addWidget(QLabel(constants.SEQ_INPUT_TERMINAL_LABEL), 1, 0)
        self.smu_measure_terminal_combo = QComboBox()
        self.smu_measure_terminal_combo.addItems([constants.TERMINAL_FRONT, constants.TERMINAL_REAR])
        layout_smu_measure.addWidget(self.smu_measure_terminal_combo, 1, 1)
        self.smu_params_stack.addWidget(page_smu_measure)

        # SMU Enable Output 페이지
        page_smu_enable_output = QWidget()
        layout_smu_enable_output = QGridLayout(page_smu_enable_output)
        layout_smu_enable_output.setVerticalSpacing(12); layout_smu_enable_output.setHorizontalSpacing(8)
        layout_smu_enable_output.addWidget(QLabel(constants.SEQ_INPUT_OUTPUT_STATE_LABEL), 0, 0)
        self.smu_output_state_combo = QComboBox()
        self.smu_output_state_combo.addItems([constants.BOOL_TRUE, constants.BOOL_FALSE]) # 수정된 상수명 사용
        layout_smu_enable_output.addWidget(self.smu_output_state_combo, 0, 1)
        self.smu_params_stack.addWidget(page_smu_enable_output)

        # SMU Set Terminal 페이지
        page_smu_set_terminal = QWidget()
        layout_smu_set_terminal = QGridLayout(page_smu_set_terminal)
        layout_smu_set_terminal.setVerticalSpacing(12); layout_smu_set_terminal.setHorizontalSpacing(8)
        layout_smu_set_terminal.addWidget(QLabel(constants.SEQ_INPUT_TERMINAL_LABEL), 0, 0)
        self.smu_terminal_combo = QComboBox()
        self.smu_terminal_combo.addItems([constants.TERMINAL_FRONT, constants.TERMINAL_REAR])
        layout_smu_set_terminal.addWidget(self.smu_terminal_combo, 0, 1)
        self.smu_params_stack.addWidget(page_smu_set_terminal)

        # SMU Set Protection Current 페이지
        page_smu_set_protection_i = QWidget()
        layout_smu_set_protection_i = QGridLayout(page_smu_set_protection_i)
        layout_smu_set_protection_i.setVerticalSpacing(12); layout_smu_set_protection_i.setHorizontalSpacing(8)
        layout_smu_set_protection_i.addWidget(QLabel(constants.SEQ_INPUT_CURRENT_LIMIT_LABEL), 0, 0)
        self.smu_protection_current_input = QLineEdit()
        self.smu_protection_current_input.setValidator(self._double_validator)
        self.smu_protection_current_input.setPlaceholderText("e.g., 0.1 (for 100mA)")
        layout_smu_set_protection_i.addWidget(self.smu_protection_current_input, 0, 1)
        self.smu_params_stack.addWidget(page_smu_set_protection_i)

        # Placeholder 페이지
        page_placeholder_smu = QWidget()
        layout_placeholder_smu = QVBoxLayout(page_placeholder_smu)
        layout_placeholder_smu.addWidget(QLabel("Select an SMU action above."), alignment=Qt.AlignCenter)
        self.smu_params_stack.addWidget(page_placeholder_smu)

    def _create_temp_sub_tab(self):
        """Chamber(온도) 액션 입력을 위한 UI를 생성합니다."""
        tab = QWidget(); self.temp_tab_widget = tab
        layout = QVBoxLayout(tab); layout.setContentsMargins(8,12,8,8); layout.setSpacing(10)
        layout.addWidget(QLabel("<b>Chamber Action:</b>"))
        self.temp_action_combo = QComboBox()
        self.temp_action_combo.addItems(constants.TEMP_ACTIONS_LIST) # 수정된 상수명 사용
        self.temp_action_combo.currentIndexChanged.connect(self._update_active_sub_tab_fields)
        layout.addWidget(self.temp_action_combo)
        self.temp_params_stack = QStackedWidget()
        self._create_temp_params_widgets()
        layout.addWidget(self.temp_params_stack)
        layout.addStretch()
        self.action_group_tabs.addTab(tab, constants.SEQ_SUB_TAB_TEMP_TITLE)

    def _create_temp_params_widgets(self):
        """Chamber 액션별 파라미터 입력 위젯들을 생성합니다."""
        double_validator_temp = QDoubleValidator() # 온도용 유효성 검사기
        double_validator_temp.setNotation(QDoubleValidator.StandardNotation)
        double_validator_temp.setDecimals(2) # 소수점 2자리

        # Chamber Set Temperature 페이지
        page_chamber_set_temp = QWidget()
        layout_chamber_set_temp = QGridLayout(page_chamber_set_temp)
        layout_chamber_set_temp.setVerticalSpacing(12); layout_chamber_set_temp.setHorizontalSpacing(8)
        layout_chamber_set_temp.addWidget(QLabel(constants.SEQ_INPUT_TEMP_LABEL), 0, 0)
        self.chamber_set_temp_input = QLineEdit()
        self.chamber_set_temp_input.setValidator(double_validator_temp)
        self.chamber_set_temp_input.setPlaceholderText("e.g., 25.0")
        layout_chamber_set_temp.addWidget(self.chamber_set_temp_input, 0, 1)
        self.temp_params_stack.addWidget(page_chamber_set_temp)

        # Chamber Check Temperature 페이지
        page_chamber_check_temp = QWidget()
        layout_chamber_check_temp = QGridLayout(page_chamber_check_temp)
        layout_chamber_check_temp.setVerticalSpacing(12); layout_chamber_check_temp.setHorizontalSpacing(8)
        layout_chamber_check_temp.addWidget(QLabel(constants.SEQ_INPUT_TEMP_LABEL), 0, 0) # 목표 온도
        self.chamber_check_target_temp_input = QLineEdit()
        self.chamber_check_target_temp_input.setValidator(double_validator_temp)
        self.chamber_check_target_temp_input.setPlaceholderText("e.g., 25.0")
        layout_chamber_check_temp.addWidget(self.chamber_check_target_temp_input, 0, 1)
        
        layout_chamber_check_temp.addWidget(QLabel(constants.SEQ_INPUT_TOLERANCE_LABEL), 1, 0) # 허용 오차
        self.chamber_check_tolerance_input = QLineEdit()
        self.chamber_check_tolerance_input.setValidator(QDoubleValidator(0.01, 10.0, 2)) # 0.01 ~ 10.0, 소수점 2자리
        self.chamber_check_tolerance_input.setPlaceholderText(f"e.g., {constants.DEFAULT_CHAMBER_CHECK_TEMP_TOLERANCE_DEG}")
        layout_chamber_check_temp.addWidget(self.chamber_check_tolerance_input, 1, 1)
        
        layout_chamber_check_temp.addWidget(QLabel(constants.SEQ_INPUT_TIMEOUT_LABEL), 2, 0) # 시간 초과
        self.chamber_check_timeout_input = QLineEdit()
        self.chamber_check_timeout_input.setValidator(QDoubleValidator(1.0, 3600.0 * 3, 1)) # 1초 ~ 3시간, 소수점 1자리
        self.chamber_check_timeout_input.setPlaceholderText(f"e.g., {constants.DEFAULT_CHAMBER_CHECK_TEMP_TIMEOUT_SEC}")
        layout_chamber_check_temp.addWidget(self.chamber_check_timeout_input, 2, 1)
        self.temp_params_stack.addWidget(page_chamber_check_temp)

        # Placeholder 페이지
        page_placeholder_temp = QWidget()
        layout_placeholder_temp = QVBoxLayout(page_placeholder_temp)
        layout_placeholder_temp.addWidget(QLabel("Select a Chamber action above."), alignment=Qt.AlignCenter)
        self.temp_params_stack.addWidget(page_placeholder_temp)

    def _update_active_sub_tab_fields(self, index: Optional[int] = None):
        """현재 선택된 메인 탭 및 하위 액션 콤보박스에 따라 표시될 파라미터 UI를 업데이트합니다."""
        if not self.action_group_tabs: return
        current_tab_index = self.action_group_tabs.currentIndex()

        if current_tab_index == 0: # I2C/Delay 탭
            if not self.i2c_action_combo or not self.i2c_params_stack: return
            action_text = self.i2c_action_combo.currentText()
            # constants.py에서 정의된 액션 문자열 상수 사용
            if action_text == constants.ACTION_I2C_WRITE_NAME: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.WRITE_NAME)
            elif action_text == constants.ACTION_I2C_WRITE_ADDR: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.WRITE_ADDR)
            elif action_text == constants.ACTION_I2C_READ_NAME: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.READ_NAME)
            elif action_text == constants.ACTION_I2C_READ_ADDR: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.READ_ADDR)
            elif action_text == constants.ACTION_DELAY: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.DELAY)
            else: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.PLACEHOLDER)
        
        elif current_tab_index == 1: # DMM 탭
            if not self.dmm_action_combo or not self.dmm_params_stack: return
            action_text = self.dmm_action_combo.currentText()
            if action_text in [constants.ACTION_MM_MEAS_V, constants.ACTION_MM_MEAS_I]: self.dmm_params_stack.setCurrentIndex(self.DMMParamPages.MEASURE)
            elif action_text == constants.ACTION_MM_SET_TERMINAL: self.dmm_params_stack.setCurrentIndex(self.DMMParamPages.SET_TERMINAL)
            else: self.dmm_params_stack.setCurrentIndex(self.DMMParamPages.PLACEHOLDER)
            
        elif current_tab_index == 2: # SMU 탭
            if not self.smu_action_combo or not self.smu_params_stack or not self.smu_set_value_label: return
            action_text = self.smu_action_combo.currentText()
            if action_text in [constants.ACTION_SM_SET_V, constants.ACTION_SM_SET_I]:
                self.smu_params_stack.setCurrentIndex(self.SMUParamPages.SET_VALUE)
                self.smu_set_value_label.setText(f"{'Voltage' if action_text == constants.ACTION_SM_SET_V else 'Current'} (Numeric):")
            elif action_text in [constants.ACTION_SM_MEAS_V, constants.ACTION_SM_MEAS_I]: self.smu_params_stack.setCurrentIndex(self.SMUParamPages.MEASURE)
            elif action_text == constants.ACTION_SM_ENABLE_OUTPUT: self.smu_params_stack.setCurrentIndex(self.SMUParamPages.ENABLE_OUTPUT)
            elif action_text == constants.ACTION_SM_SET_TERMINAL: self.smu_params_stack.setCurrentIndex(self.SMUParamPages.SET_TERMINAL)
            elif action_text == constants.ACTION_SM_SET_PROTECTION_I: self.smu_params_stack.setCurrentIndex(self.SMUParamPages.SET_PROTECTION_I)
            else: self.smu_params_stack.setCurrentIndex(self.SMUParamPages.PLACEHOLDER)
            
        elif current_tab_index == 3: # Chamber 탭
            if not self.temp_action_combo or not self.temp_params_stack: return
            action_text = self.temp_action_combo.currentText()
            if action_text == constants.ACTION_CHAMBER_SET_TEMP: self.temp_params_stack.setCurrentIndex(self.TempParamPages.SET_TEMP)
            elif action_text == constants.ACTION_CHAMBER_CHECK_TEMP: self.temp_params_stack.setCurrentIndex(self.TempParamPages.CHECK_TEMP)
            else: self.temp_params_stack.setCurrentIndex(self.TempParamPages.PLACEHOLDER)

    def _is_i2c_ready(self) -> bool:
        """I2C 사용을 위한 준비(Chip ID 설정)가 되었는지 확인하고, 아니면 경고 메시지를 표시합니다."""
        chip_id_value = self.current_settings.get(constants.SETTINGS_CHIP_ID_KEY, "") # chip_id -> SETTINGS_CHIP_ID_KEY
        if not chip_id_value or not chip_id_value.strip():
            print("DEBUG_AIP: _is_i2c_ready - Chip ID is not set or empty.")
            QMessageBox.warning(self, constants.MSG_TITLE_WARNING,
                                "Chip ID가 설정되지 않았습니다. Settings 탭에서 Chip ID를 설정해주세요.")
            return False
        print(f"DEBUG_AIP: _is_i2c_ready - Chip ID is '{chip_id_value}'. Returning True.")
        return True

    def _is_device_enabled(self, device_setting_key: str, device_name_for_msg: str) -> bool:
        """설정에서 해당 장비가 활성화되었는지 확인하고, 아니면 경고 메시지를 표시합니다."""
        # device_setting_key는 constants.SETTINGS_..._USE_KEY 형태의 문자열이어야 함
        if not self.current_settings.get(device_setting_key, False):
            print(f"DEBUG_AIP: _is_device_enabled - Device '{device_name_for_msg}' (key: {device_setting_key}) is not enabled in settings.")
            QMessageBox.warning(self, constants.MSG_TITLE_WARNING,
                                constants.MSG_DEVICE_NOT_ENABLED.format(device_name=device_name_for_msg))
            return False
        
        # 멀티미터 또는 소스미터 사용 시 시리얼 번호(주소)도 확인
        if device_setting_key in [constants.SETTINGS_MULTIMETER_USE_KEY, constants.SETTINGS_SOURCEMETER_USE_KEY]:
            serial_key = device_setting_key.replace("_use", "_serial") # 예: "multimeter_use" -> "multimeter_serial"
            # 실제 키 이름은 constants.SETTINGS_MULTIMETER_SERIAL_KEY 등을 사용해야 함
            if device_setting_key == constants.SETTINGS_MULTIMETER_USE_KEY:
                serial_key_actual = constants.SETTINGS_MULTIMETER_SERIAL_KEY
            elif device_setting_key == constants.SETTINGS_SOURCEMETER_USE_KEY:
                serial_key_actual = constants.SETTINGS_SOURCEMETER_SERIAL_KEY
            else: # 이 경우는 발생하지 않아야 함
                serial_key_actual = ""

            if serial_key_actual:
                serial_value = self.current_settings.get(serial_key_actual, "")
                if not serial_value or not serial_value.strip():
                    print(f"DEBUG_AIP: _is_device_enabled - Serial number for '{device_name_for_msg}' (key: {serial_key_actual}) is not set.")
                    QMessageBox.warning(self, constants.MSG_TITLE_WARNING,
                                        f"{device_name_for_msg}의 시리얼 번호/주소가 설정되지 않았습니다.")
                    return False
        print(f"DEBUG_AIP: _is_device_enabled - Device '{device_name_for_msg}' is enabled.")
        return True


    def get_current_action_string_and_prefix(self) -> Optional[Tuple[str, str, Dict[str,str]]]:
        """현재 UI에서 선택/입력된 액션 정보를 파싱하여 문자열과 파라미터 딕셔너리로 반환합니다."""
        print("DEBUG_AIP: get_current_action_string_and_prefix called")
        if not self.action_group_tabs:
            print("DEBUG_AIP: self.action_group_tabs is None, returning None")
            return None
        current_tab_index = self.action_group_tabs.currentIndex()
        print(f"DEBUG_AIP: current_tab_index = {current_tab_index}")

        item_str_prefix = "" # 예: "I2C_W_NAME"
        params_list_for_str = [] # 예: ["NAME=CTRL_REG", "VAL=0xFF"]
        params_dict_for_data = {} # 예: {"NAME": "CTRL_REG", "VAL": "0xFF"}

        # I2C/Delay 탭
        if current_tab_index == 0:
            print("DEBUG_AIP: I2C/Delay Tab selected")
            if not all([ # 필수 UI 요소 None 체크
                self.i2c_action_combo, self.i2c_params_stack,
                self.i2c_write_name_target_input, self.i2c_write_name_value_input,
                self.i2c_write_addr_target_input, self.i2c_write_addr_value_input,
                self.i2c_read_name_target_input, self.i2c_read_name_var_name_input,
                self.i2c_read_addr_target_input, self.i2c_read_addr_var_name_input,
                self.delay_seconds_input
            ]):
                print("DEBUG_AIP: CRITICAL - One or more I2C tab UI elements are None.")
                QMessageBox.critical(self, "내부 UI 오류", "I2C 액션 처리에 필요한 UI 요소가 준비되지 않았습니다.")
                return None
            
            action_text = self.i2c_action_combo.currentText() # 예: "I2C Write (Name)"
            print(f"DEBUG_AIP: I2C action_text = '{action_text}'")

            if action_text != constants.ACTION_DELAY: # Delay 액션은 Chip ID 불필요
                if not self._is_i2c_ready():
                    print("DEBUG_AIP: _is_i2c_ready() returned False, returning None from get_current_action")
                    return None
                print("DEBUG_AIP: _is_i2c_ready() returned True")

            if action_text == constants.ACTION_I2C_WRITE_NAME:
                print("DEBUG_AIP: Processing ACTION_I2C_WRITE_NAME")
                if not self.register_map or not self.register_map.logical_fields_map:
                    QMessageBox.warning(self, constants.MSG_TITLE_ERROR, constants.MSG_NO_REGMAP_LOADED); return None
                
                item_str_prefix = constants.SEQ_PREFIX_I2C_WRITE_NAME # Enum 값 사용
                name = self.i2c_write_name_target_input.text().strip()
                value_hex_raw = self.i2c_write_name_value_input.text().strip()
                
                value_hex_normalized = normalize_hex_input(value_hex_raw, add_prefix=True)

                if not value_hex_normalized and value_hex_raw: 
                    QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INVALID_HEX_VALUE.format(value=value_hex_raw)); return None
                if not name or not value_hex_normalized : # 이름 또는 정규화된 값이 비었으면
                    QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INPUT_EMPTY_GENERIC); return None
                if name not in self.register_map.logical_fields_map:
                    QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_FIELD_ID_NOT_FOUND.format(field_id=name)); return None
                
                value_hex = value_hex_normalized
                params_list_for_str.extend([f"{constants.SEQ_PARAM_KEY_TARGET_NAME}={name}", f"{constants.SEQ_PARAM_KEY_VALUE}={value_hex}"])
                params_dict_for_data[constants.SEQ_PARAM_KEY_TARGET_NAME] = name
                params_dict_for_data[constants.SEQ_PARAM_KEY_VALUE] = value_hex
            
            # ... (ACTION_I2C_WRITE_ADDR, READ_NAME, READ_ADDR, DELAY에 대한 로직도 유사하게 constants 사용) ...
            elif action_text == constants.ACTION_I2C_WRITE_ADDR:
                item_str_prefix = constants.SEQ_PREFIX_I2C_WRITE_ADDR
                addr_hex_raw = self.i2c_write_addr_target_input.text().strip()
                value_hex_raw = self.i2c_write_addr_value_input.text().strip()
                addr_hex_normalized = normalize_hex_input(addr_hex_raw, 4, add_prefix=True)
                value_hex_normalized = normalize_hex_input(value_hex_raw, 2, add_prefix=True)
                if not addr_hex_normalized and addr_hex_raw: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, f"잘못된 주소 형식: {addr_hex_raw}"); return None
                if not value_hex_normalized and value_hex_raw: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INVALID_HEX_VALUE.format(value=value_hex_raw)); return None
                if not addr_hex_normalized or not value_hex_normalized: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INPUT_EMPTY_GENERIC); return None
                params_list_for_str.extend([f"{constants.SEQ_PARAM_KEY_ADDRESS}={addr_hex_normalized}", f"{constants.SEQ_PARAM_KEY_VALUE}={value_hex_normalized}"])
                params_dict_for_data[constants.SEQ_PARAM_KEY_ADDRESS] = addr_hex_normalized; params_dict_for_data[constants.SEQ_PARAM_KEY_VALUE] = value_hex_normalized

            elif action_text == constants.ACTION_I2C_READ_NAME:
                if not self.register_map or not self.register_map.logical_fields_map: QMessageBox.warning(self, constants.MSG_TITLE_ERROR, constants.MSG_NO_REGMAP_LOADED); return None
                item_str_prefix = constants.SEQ_PREFIX_I2C_READ_NAME
                name = self.i2c_read_name_target_input.text().strip()
                var_name = self.i2c_read_name_var_name_input.text().strip()
                if not name or not var_name: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "레지스터명과 저장 변수명 모두 입력 필요"); return None
                if name not in self.register_map.logical_fields_map: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_FIELD_ID_NOT_FOUND.format(field_id=name)); return None
                params_list_for_str.extend([f"{constants.SEQ_PARAM_KEY_TARGET_NAME}={name}", f"{constants.SEQ_PARAM_KEY_VARIABLE}={var_name}"])
                params_dict_for_data[constants.SEQ_PARAM_KEY_TARGET_NAME] = name; params_dict_for_data[constants.SEQ_PARAM_KEY_VARIABLE] = var_name

            elif action_text == constants.ACTION_I2C_READ_ADDR:
                item_str_prefix = constants.SEQ_PREFIX_I2C_READ_ADDR
                addr_hex_raw = self.i2c_read_addr_target_input.text().strip()
                var_name = self.i2c_read_addr_var_name_input.text().strip()
                addr_hex_normalized = normalize_hex_input(addr_hex_raw, 4, add_prefix=True)
                if not addr_hex_normalized and addr_hex_raw: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, f"잘못된 주소 형식: {addr_hex_raw}"); return None
                if not addr_hex_normalized or not var_name: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "주소와 저장 변수명 모두 입력 필요"); return None
                params_list_for_str.extend([f"{constants.SEQ_PARAM_KEY_ADDRESS}={addr_hex_normalized}", f"{constants.SEQ_PARAM_KEY_VARIABLE}={var_name}"])
                params_dict_for_data[constants.SEQ_PARAM_KEY_ADDRESS] = addr_hex_normalized; params_dict_for_data[constants.SEQ_PARAM_KEY_VARIABLE] = var_name
            
            elif action_text == constants.ACTION_DELAY:
                item_str_prefix = constants.SEQ_PREFIX_DELAY
                delay_val = self.delay_seconds_input.value()
                if delay_val <= 0: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "지연 시간은 0보다 커야 합니다."); return None
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_SECONDS}={delay_val}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_SECONDS] = str(delay_val)
            else:
                QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_ACTION_NOT_SUPPORTED); return None
        
        # DMM 탭
        elif current_tab_index == 1:
            if not (self.dmm_action_combo and self.dmm_params_stack and self.dmm_measure_var_name_input and self.dmm_terminal_combo): # Reverted check
                QMessageBox.critical(self, "내부 UI 오류", "DMM 액션 UI 요소 준비 안됨."); return None
            if not self._is_device_enabled(constants.SETTINGS_MULTIMETER_USE_KEY, "Multimeter"): return None
            
            action_text = self.dmm_action_combo.currentText()
            if action_text == constants.ACTION_MM_MEAS_V: item_str_prefix = constants.SEQ_PREFIX_MM_MEAS_V
            elif action_text == constants.ACTION_MM_MEAS_I: item_str_prefix = constants.SEQ_PREFIX_MM_MEAS_I
            elif action_text == constants.ACTION_MM_SET_TERMINAL: item_str_prefix = constants.SEQ_PREFIX_MM_SET_TERMINAL
            else: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_ACTION_NOT_SUPPORTED); return None

            if item_str_prefix in [constants.SEQ_PREFIX_MM_MEAS_V, constants.SEQ_PREFIX_MM_MEAS_I]:
                var_name = self.dmm_measure_var_name_input.text().strip()
                if not var_name: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "결과 변수명 입력 필요"); return None
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_VARIABLE}={var_name}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_VARIABLE] = var_name
            elif item_str_prefix == constants.SEQ_PREFIX_MM_SET_TERMINAL:
                term_val = self.dmm_terminal_combo.currentText()
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_TERMINAL}={term_val}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_TERMINAL] = term_val
        
        # SMU 탭
        elif current_tab_index == 2:
            if not (self.smu_action_combo and self.smu_params_stack and self.smu_set_value_label and # Reverted check
                    self.smu_set_value_input and self.smu_set_terminal_combo and 
                    self.smu_measure_var_name_input and self.smu_measure_terminal_combo and
                    self.smu_output_state_combo and self.smu_terminal_combo and 
                    self.smu_protection_current_input):
                QMessageBox.critical(self, "내부 UI 오류", "SMU 액션 UI 요소 준비 안됨."); return None
            if not self._is_device_enabled(constants.SETTINGS_SOURCEMETER_USE_KEY, "Sourcemeter"): return None
            
            action_text = self.smu_action_combo.currentText()
            if action_text == constants.ACTION_SM_SET_V: item_str_prefix = constants.SEQ_PREFIX_SM_SET_V
            elif action_text == constants.ACTION_SM_SET_I: item_str_prefix = constants.SEQ_PREFIX_SM_SET_I
            elif action_text == constants.ACTION_SM_MEAS_V: item_str_prefix = constants.SEQ_PREFIX_SM_MEAS_V
            elif action_text == constants.ACTION_SM_MEAS_I: item_str_prefix = constants.SEQ_PREFIX_SM_MEAS_I
            elif action_text == constants.ACTION_SM_ENABLE_OUTPUT: item_str_prefix = constants.SEQ_PREFIX_SM_ENABLE_OUTPUT
            elif action_text == constants.ACTION_SM_SET_TERMINAL: item_str_prefix = constants.SEQ_PREFIX_SM_SET_TERMINAL
            elif action_text == constants.ACTION_SM_SET_PROTECTION_I: item_str_prefix = constants.SEQ_PREFIX_SM_SET_PROTECTION_I
            else: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_ACTION_NOT_SUPPORTED); return None

            if item_str_prefix in [constants.SEQ_PREFIX_SM_SET_V, constants.SEQ_PREFIX_SM_SET_I]:
                val_str = self.smu_set_value_input.text().strip()
                if not val_str: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "값 입력 필요"); return None
                try: float(val_str)
                except ValueError: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INVALID_NUMERIC_VALUE.format(value=val_str)); return None
                term_val = self.smu_set_terminal_combo.currentText()
                params_list_for_str.extend([f"{constants.SEQ_PARAM_KEY_VALUE}={val_str}", f"{constants.SEQ_PARAM_KEY_TERMINAL}={term_val}"])
                params_dict_for_data[constants.SEQ_PARAM_KEY_VALUE] = val_str; params_dict_for_data[constants.SEQ_PARAM_KEY_TERMINAL] = term_val
            elif item_str_prefix in [constants.SEQ_PREFIX_SM_MEAS_V, constants.SEQ_PREFIX_SM_MEAS_I]:
                var_name = self.smu_measure_var_name_input.text().strip()
                if not var_name: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "결과 변수명 입력 필요"); return None
                term_val = self.smu_measure_terminal_combo.currentText()
                params_list_for_str.extend([f"{constants.SEQ_PARAM_KEY_VARIABLE}={var_name}", f"{constants.SEQ_PARAM_KEY_TERMINAL}={term_val}"])
                params_dict_for_data[constants.SEQ_PARAM_KEY_VARIABLE] = var_name; params_dict_for_data[constants.SEQ_PARAM_KEY_TERMINAL] = term_val
            elif item_str_prefix == constants.SEQ_PREFIX_SM_ENABLE_OUTPUT:
                state_val = self.smu_output_state_combo.currentText() # constants.BOOL_TRUE 또는 BOOL_FALSE
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_STATE}={state_val}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_STATE] = state_val
            elif item_str_prefix == constants.SEQ_PREFIX_SM_SET_TERMINAL:
                term_val = self.smu_terminal_combo.currentText()
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_TERMINAL}={term_val}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_TERMINAL] = term_val
            elif item_str_prefix == constants.SEQ_PREFIX_SM_SET_PROTECTION_I:
                val_str = self.smu_protection_current_input.text().strip()
                if not val_str: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "보호 전류 값 입력 필요"); return None
                try: float(val_str)
                except ValueError: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INVALID_NUMERIC_VALUE.format(value=val_str)); return None
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_CURRENT_LIMIT}={val_str}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_CURRENT_LIMIT] = val_str
        
        # Chamber 탭
        elif current_tab_index == 3:
            if not (self.temp_action_combo and self.temp_params_stack and # Reverted check
                    self.chamber_set_temp_input and 
                    self.chamber_check_target_temp_input and 
                    self.chamber_check_tolerance_input and
                    self.chamber_check_timeout_input):
                QMessageBox.critical(self, "내부 UI 오류", "Chamber 액션 UI 요소 준비 안됨."); return None
            if not self._is_device_enabled(constants.SETTINGS_CHAMBER_USE_KEY, "Chamber"): return None
            
            action_text = self.temp_action_combo.currentText()
            if action_text == constants.ACTION_CHAMBER_SET_TEMP: item_str_prefix = constants.SEQ_PREFIX_CHAMBER_SET_TEMP
            elif action_text == constants.ACTION_CHAMBER_CHECK_TEMP: item_str_prefix = constants.SEQ_PREFIX_CHAMBER_CHECK_TEMP
            else: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_ACTION_NOT_SUPPORTED); return None

            if item_str_prefix == constants.SEQ_PREFIX_CHAMBER_SET_TEMP:
                val_str = self.chamber_set_temp_input.text().strip()
                if not val_str: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "목표 온도 값 입력 필요"); return None
                try: float(val_str)
                except ValueError: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INVALID_NUMERIC_VALUE.format(value=val_str)); return None
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_VALUE}={val_str}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_VALUE] = val_str
            elif item_str_prefix == constants.SEQ_PREFIX_CHAMBER_CHECK_TEMP:
                target_temp_str = self.chamber_check_target_temp_input.text().strip()
                tolerance_str = self.chamber_check_tolerance_input.text().strip() # 기본값은 SequencePlayer에서 처리
                timeout_str = self.chamber_check_timeout_input.text().strip() # 기본값은 SequencePlayer에서 처리
                if not target_temp_str: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "목표 온도 값 입력 필요"); return None
                try:
                    float(target_temp_str)
                    if tolerance_str: float(tolerance_str) # 입력 시에만 유효성 검사
                    if timeout_str: float(timeout_str)   # 입력 시에만 유효성 검사
                except ValueError: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "온도/오차/시간 초과 값 형식 오류"); return None
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_VALUE}={target_temp_str}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_VALUE] = target_temp_str
                if tolerance_str: # 값이 입력된 경우에만 파라미터 추가
                    params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_TOLERANCE}={tolerance_str}")
                    params_dict_for_data[constants.SEQ_PARAM_KEY_TOLERANCE] = tolerance_str
                if timeout_str: # 값이 입력된 경우에만 파라미터 추가
                    params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_TIMEOUT}={timeout_str}")
                    params_dict_for_data[constants.SEQ_PARAM_KEY_TIMEOUT] = timeout_str
        else:
            print(f"DEBUG_AIP: Unknown tab index: {current_tab_index}, returning None")
            return None

        if item_str_prefix:
            full_action_string = f"{item_str_prefix}: {'; '.join(params_list_for_str)}"
            print(f"DEBUG_AIP: Successfully generated action string: {full_action_string}")
            return item_str_prefix, full_action_string, params_dict_for_data
        
        print("DEBUG_AIP: item_str_prefix is empty, returning None at the end of method")
        return None

    def clear_input_fields(self):
        """현재 활성화된 탭의 액션 입력 필드를 초기화합니다."""
        if not self.action_group_tabs: return
        current_tab_index = self.action_group_tabs.currentIndex()

        if current_tab_index == 0 and self.i2c_action_combo: # I2C/Delay
            action_text = self.i2c_action_combo.currentText()
            if action_text == constants.ACTION_I2C_WRITE_NAME:
                if self.i2c_write_name_target_input: self.i2c_write_name_target_input.clear()
                if self.i2c_write_name_value_input: self.i2c_write_name_value_input.clear(); self.i2c_write_name_value_input.setStyleSheet(""); self.i2c_write_name_value_input.setToolTip("")
            elif action_text == constants.ACTION_I2C_WRITE_ADDR:
                if self.i2c_write_addr_target_input: self.i2c_write_addr_target_input.clear(); self.i2c_write_addr_target_input.setStyleSheet(""); self.i2c_write_addr_target_input.setToolTip("")
                if self.i2c_write_addr_value_input: self.i2c_write_addr_value_input.clear(); self.i2c_write_addr_value_input.setStyleSheet(""); self.i2c_write_addr_value_input.setToolTip("")
            elif action_text == constants.ACTION_I2C_READ_NAME:
                if self.i2c_read_name_target_input: self.i2c_read_name_target_input.clear()
                if self.i2c_read_name_var_name_input: self.i2c_read_name_var_name_input.clear()
            elif action_text == constants.ACTION_I2C_READ_ADDR:
                if self.i2c_read_addr_target_input: self.i2c_read_addr_target_input.clear(); self.i2c_read_addr_target_input.setStyleSheet(""); self.i2c_read_addr_target_input.setToolTip("")
                if self.i2c_read_addr_var_name_input: self.i2c_read_addr_var_name_input.clear()
            elif action_text == constants.ACTION_DELAY:
                if self.delay_seconds_input: self.delay_seconds_input.setValue(0.01) # 기본값으로 리셋
        
        elif current_tab_index == 1 and self.dmm_action_combo: # DMM
            action_text = self.dmm_action_combo.currentText()
            if action_text in [constants.ACTION_MM_MEAS_V, constants.ACTION_MM_MEAS_I]:
                if self.dmm_measure_var_name_input: self.dmm_measure_var_name_input.clear()
            # Set Terminal은 콤보박스이므로 별도 clear 불필요 (기본값으로 유지)
        
        elif current_tab_index == 2 and self.smu_action_combo: # SMU
            action_text = self.smu_action_combo.currentText()
            if action_text in [constants.ACTION_SM_SET_V, constants.ACTION_SM_SET_I]:
                if self.smu_set_value_input: self.smu_set_value_input.clear()
            elif action_text in [constants.ACTION_SM_MEAS_V, constants.ACTION_SM_MEAS_I]:
                if self.smu_measure_var_name_input: self.smu_measure_var_name_input.clear()
            elif action_text == constants.ACTION_SM_SET_PROTECTION_I:
                if self.smu_protection_current_input: self.smu_protection_current_input.clear()
            # 콤보박스들은 선택 유지
            
        elif current_tab_index == 3 and self.temp_action_combo: # Chamber
            action_text = self.temp_action_combo.currentText()
            if action_text == constants.ACTION_CHAMBER_SET_TEMP:
                if self.chamber_set_temp_input: self.chamber_set_temp_input.clear()
            elif action_text == constants.ACTION_CHAMBER_CHECK_TEMP:
                if self.chamber_check_target_temp_input: self.chamber_check_target_temp_input.clear()
                if self.chamber_check_tolerance_input: self.chamber_check_tolerance_input.clear()
                if self.chamber_check_timeout_input: self.chamber_check_timeout_input.clear()

    def update_completer_model(self, new_model: Optional[QStringListModel]):
        """자동완성 모델을 업데이트합니다."""
        self.completer_model = new_model
        if self.completer_model is not None:
            # I2C 이름 입력 필드에 자동완성기 설정/업데이트
            if self.i2c_write_name_target_input:
                if not self.i2c_write_name_target_input.completer(): # 자동완성기가 없으면 새로 생성
                    completer_write_name = QCompleter(self.completer_model, self)
                    completer_write_name.setCaseSensitivity(Qt.CaseInsensitive)
                    completer_write_name.setFilterMode(Qt.MatchContains)
                    self.i2c_write_name_target_input.setCompleter(completer_write_name)
                else: # 이미 있으면 모델만 업데이트
                    self.i2c_write_name_target_input.completer().setModel(self.completer_model)
            
            if self.i2c_read_name_target_input:
                if not self.i2c_read_name_target_input.completer():
                    completer_read_name = QCompleter(self.completer_model, self)
                    completer_read_name.setCaseSensitivity(Qt.CaseInsensitive)
                    completer_read_name.setFilterMode(Qt.MatchContains)
                    self.i2c_read_name_target_input.setCompleter(completer_read_name)
                else:
                    self.i2c_read_name_target_input.completer().setModel(self.completer_model)
        else: # 모델이 None이면 자동완성기 제거
            if self.i2c_write_name_target_input: self.i2c_write_name_target_input.setCompleter(None)
            if self.i2c_read_name_target_input: self.i2c_read_name_target_input.setCompleter(None)

    def update_settings(self, new_settings: Dict[str, Any]):
        """외부(메인 윈도우)로부터 받은 새 설정으로 내부 상태 및 UI를 업데이트합니다.
           NOTE: Instrument sub-tab enablement is now handled by enable_instrument_sub_tab().
        """
        self.current_settings = new_settings if new_settings is not None else {}
        # Tab enablement logic is removed from here and moved to enable_instrument_sub_tab
        print(f"DEBUG_AIP_UpdateSettings: Settings updated. DMM_use: {self.current_settings.get(constants.SETTINGS_MULTIMETER_USE_KEY)}, SMU_use: {self.current_settings.get(constants.SETTINGS_SOURCEMETER_USE_KEY)}, Chamber_use: {self.current_settings.get(constants.SETTINGS_CHAMBER_USE_KEY)}")
        self._update_active_sub_tab_fields() # Still needed to refresh stacked widget if current tab changes

    def enable_instrument_sub_tab(self, instrument_type: str, enabled: bool):
        """Enables or disables a specific instrument sub-tab (DMM, SMU, Chamber)."""
        print(f"DEBUG_AIP: enable_instrument_sub_tab called for '{instrument_type}', enabled: {enabled}")
        target_tab_widget: Optional[QWidget] = None
        tab_key_for_log = "Unknown"

        if instrument_type == "DMM":
            target_tab_widget = self.dmm_tab_widget
            tab_key_for_log = "DMM"
        elif instrument_type == "SMU":
            target_tab_widget = self.smu_tab_widget
            tab_key_for_log = "SMU"
        elif instrument_type == "CHAMBER": # Matches signal emission
            target_tab_widget = self.temp_tab_widget
            tab_key_for_log = "Chamber"
        else:
            print(f"ERROR_AIP: Unknown instrument_type '{instrument_type}' in enable_instrument_sub_tab.")
            return

        if self.action_group_tabs and target_tab_widget is not None:
            tab_idx = self.action_group_tabs.indexOf(target_tab_widget)
            if tab_idx != -1:
                current_visual_state = self.action_group_tabs.isTabEnabled(tab_idx)
                print(f"DEBUG_AIP: {tab_key_for_log} sub-tab (idx {tab_idx}) current visual enabled: {current_visual_state}, attempting to set to: {enabled}")
                self.action_group_tabs.setTabEnabled(tab_idx, enabled)
                QApplication.processEvents() # Try to force UI update
                final_visual_state = self.action_group_tabs.isTabEnabled(tab_idx)
                print(f"VERIFY_AIP_{tab_key_for_log}_TAB_NEW: {tab_key_for_log} tab index {tab_idx} is NOW actually enabled: {final_visual_state} (desired: {enabled})")

                if not enabled and self.action_group_tabs.widget(tab_idx) == self.action_group_tabs.currentWidget():
                    self.action_group_tabs.setCurrentIndex(0) # Switch to I2C tab
                    print(f"DEBUG_AIP: {tab_key_for_log} tab was current and disabled, switched to I2C tab.")
            else:
                print(f"ERROR_AIP: {tab_key_for_log} tab widget not found in action_group_tabs for enable/disable.")
        elif not self.action_group_tabs:
            print("ERROR_AIP: self.action_group_tabs is None in enable_instrument_sub_tab.")
        elif target_tab_widget is None:
             print(f"ERROR_AIP: target_tab_widget for {instrument_type} is None in enable_instrument_sub_tab.")

    def update_register_map(self, new_register_map: Optional[RegisterMap]):
        """외부(메인 윈도우)로부터 받은 새 레지스터 맵으로 내부 상태를 업데이트합니다."""
        self.register_map = new_register_map
        # 자동완성 모델도 레지스터 맵 변경에 따라 업데이트 필요
        if self.register_map and self.completer_model:
            self.completer_model.setStringList(self.register_map.get_all_field_ids())
        elif self.completer_model: # 레지스터 맵이 None으로 되면 자동완성 목록 비우기
            self.completer_model.setStringList([])
            
        print("ActionInputPanel: RegisterMap updated.")

    def load_action_data_for_editing(self, action_data: SimpleActionItem):
        """주어진 SimpleActionItem 데이터로 입력 패널 필드를 채웁니다."""
        action_type_prefix = action_data.get("action_type")
        params = action_data.get("parameters", {})

        # 1. 적절한 메인 탭 선택 (I2C, DMM, SMU, Temp)
        target_tab_widget: Optional[QWidget] = None
        target_action_combo: Optional[QComboBox] = None
        action_text_to_select: Optional[str] = None

        # I2C/Delay 액션에 대한 매핑 (상수 값 기준)
        i2c_action_map = {
            constants.SEQ_PREFIX_I2C_WRITE_NAME: (self.i2c_tab_widget, self.i2c_action_combo, constants.ACTION_I2C_WRITE_NAME),
            constants.SEQ_PREFIX_I2C_WRITE_ADDR: (self.i2c_tab_widget, self.i2c_action_combo, constants.ACTION_I2C_WRITE_ADDR),
            constants.SEQ_PREFIX_I2C_READ_NAME: (self.i2c_tab_widget, self.i2c_action_combo, constants.ACTION_I2C_READ_NAME),
            constants.SEQ_PREFIX_I2C_READ_ADDR: (self.i2c_tab_widget, self.i2c_action_combo, constants.ACTION_I2C_READ_ADDR),
            constants.SEQ_PREFIX_DELAY: (self.i2c_tab_widget, self.i2c_action_combo, constants.ACTION_DELAY),
        }
        dmm_action_map = {
            constants.SEQ_PREFIX_MM_MEAS_V: (self.dmm_tab_widget, self.dmm_action_combo, constants.ACTION_MM_MEAS_V),
            constants.SEQ_PREFIX_MM_MEAS_I: (self.dmm_tab_widget, self.dmm_action_combo, constants.ACTION_MM_MEAS_I),
            constants.SEQ_PREFIX_MM_SET_TERMINAL: (self.dmm_tab_widget, self.dmm_action_combo, constants.ACTION_MM_SET_TERMINAL),
        }
        smu_action_map = {
            constants.SEQ_PREFIX_SM_SET_V: (self.smu_tab_widget, self.smu_action_combo, constants.ACTION_SM_SET_V),
            constants.SEQ_PREFIX_SM_SET_I: (self.smu_tab_widget, self.smu_action_combo, constants.ACTION_SM_SET_I),
            constants.SEQ_PREFIX_SM_MEAS_V: (self.smu_tab_widget, self.smu_action_combo, constants.ACTION_SM_MEAS_V),
            constants.SEQ_PREFIX_SM_MEAS_I: (self.smu_tab_widget, self.smu_action_combo, constants.ACTION_SM_MEAS_I),
            constants.SEQ_PREFIX_SM_ENABLE_OUTPUT: (self.smu_tab_widget, self.smu_action_combo, constants.ACTION_SM_ENABLE_OUTPUT),
            constants.SEQ_PREFIX_SM_SET_TERMINAL: (self.smu_tab_widget, self.smu_action_combo, constants.ACTION_SM_SET_TERMINAL),
            constants.SEQ_PREFIX_SM_SET_PROTECTION_I: (self.smu_tab_widget, self.smu_action_combo, constants.ACTION_SM_SET_PROTECTION_I),
        }
        temp_action_map = {
            constants.SEQ_PREFIX_CHAMBER_SET_TEMP: (self.temp_tab_widget, self.temp_action_combo, constants.ACTION_CHAMBER_SET_TEMP),
            constants.SEQ_PREFIX_CHAMBER_CHECK_TEMP: (self.temp_tab_widget, self.temp_action_combo, constants.ACTION_CHAMBER_CHECK_TEMP),
        }

        found_map_entry = None
        if action_type_prefix in i2c_action_map: found_map_entry = i2c_action_map[action_type_prefix]
        elif action_type_prefix in dmm_action_map: found_map_entry = dmm_action_map[action_type_prefix]
        elif action_type_prefix in smu_action_map: found_map_entry = smu_action_map[action_type_prefix]
        elif action_type_prefix in temp_action_map: found_map_entry = temp_action_map[action_type_prefix]

        if found_map_entry and self.action_group_tabs:
            target_tab_widget, target_action_combo, action_text_to_select = found_map_entry
            if target_tab_widget and target_action_combo:
                tab_index = self.action_group_tabs.indexOf(target_tab_widget)
                if tab_index != -1:
                    self.action_group_tabs.setCurrentIndex(tab_index)
                    combo_idx = target_action_combo.findText(action_text_to_select)
                    if combo_idx != -1: target_action_combo.setCurrentIndex(combo_idx)
        else:
            QMessageBox.warning(self, "Error", f"Cannot load action type '{action_type_prefix}' into input panel.")
            return

        # 2. 파라미터 값 채우기 (선택된 탭과 액션에 따라)
        # I2C/Delay
        if target_tab_widget == self.i2c_tab_widget:
            if action_type_prefix == constants.SEQ_PREFIX_I2C_WRITE_NAME and self.i2c_write_name_target_input and self.i2c_write_name_value_input:
                self.i2c_write_name_target_input.setText(params.get(constants.SEQ_PARAM_KEY_TARGET_NAME, ''))
                self.i2c_write_name_value_input.setText(params.get(constants.SEQ_PARAM_KEY_VALUE, ''))
            elif action_type_prefix == constants.SEQ_PREFIX_I2C_WRITE_ADDR and self.i2c_write_addr_target_input and self.i2c_write_addr_value_input:
                self.i2c_write_addr_target_input.setText(params.get(constants.SEQ_PARAM_KEY_ADDRESS, ''))
                self.i2c_write_addr_value_input.setText(params.get(constants.SEQ_PARAM_KEY_VALUE, ''))
            elif action_type_prefix == constants.SEQ_PREFIX_I2C_READ_NAME and self.i2c_read_name_target_input and self.i2c_read_name_var_name_input:
                self.i2c_read_name_target_input.setText(params.get(constants.SEQ_PARAM_KEY_TARGET_NAME, ''))
                self.i2c_read_name_var_name_input.setText(params.get(constants.SEQ_PARAM_KEY_VARIABLE, ''))
            elif action_type_prefix == constants.SEQ_PREFIX_I2C_READ_ADDR and self.i2c_read_addr_target_input and self.i2c_read_addr_var_name_input:
                self.i2c_read_addr_target_input.setText(params.get(constants.SEQ_PARAM_KEY_ADDRESS, ''))
                self.i2c_read_addr_var_name_input.setText(params.get(constants.SEQ_PARAM_KEY_VARIABLE, ''))
            elif action_type_prefix == constants.SEQ_PREFIX_DELAY and self.delay_seconds_input:
                self.delay_seconds_input.setValue(float(params.get(constants.SEQ_PARAM_KEY_SECONDS, 0.01)))
        # DMM
        elif target_tab_widget == self.dmm_tab_widget:
            if action_type_prefix in [constants.SEQ_PREFIX_MM_MEAS_V, constants.SEQ_PREFIX_MM_MEAS_I] and self.dmm_measure_var_name_input:
                self.dmm_measure_var_name_input.setText(params.get(constants.SEQ_PARAM_KEY_VARIABLE, ''))
            elif action_type_prefix == constants.SEQ_PREFIX_MM_SET_TERMINAL and self.dmm_terminal_combo:
                self.dmm_terminal_combo.setCurrentText(params.get(constants.SEQ_PARAM_KEY_TERMINAL, constants.TERMINAL_FRONT))
        # SMU
        elif target_tab_widget == self.smu_tab_widget:
            if action_type_prefix in [constants.SEQ_PREFIX_SM_SET_V, constants.SEQ_PREFIX_SM_SET_I] and self.smu_set_value_input and self.smu_set_terminal_combo:
                self.smu_set_value_input.setText(str(params.get(constants.SEQ_PARAM_KEY_VALUE, '')))
                self.smu_set_terminal_combo.setCurrentText(params.get(constants.SEQ_PARAM_KEY_TERMINAL, constants.TERMINAL_FRONT))
            elif action_type_prefix in [constants.SEQ_PREFIX_SM_MEAS_V, constants.SEQ_PREFIX_SM_MEAS_I] and self.smu_measure_var_name_input and self.smu_measure_terminal_combo:
                self.smu_measure_var_name_input.setText(params.get(constants.SEQ_PARAM_KEY_VARIABLE, ''))
                self.smu_measure_terminal_combo.setCurrentText(params.get(constants.SEQ_PARAM_KEY_TERMINAL, constants.TERMINAL_FRONT))
            elif action_type_prefix == constants.SEQ_PREFIX_SM_ENABLE_OUTPUT and self.smu_output_state_combo:
                self.smu_output_state_combo.setCurrentText(params.get(constants.SEQ_PARAM_KEY_STATE, constants.BOOL_TRUE))
            elif action_type_prefix == constants.SEQ_PREFIX_SM_SET_TERMINAL and self.smu_terminal_combo:
                self.smu_terminal_combo.setCurrentText(params.get(constants.SEQ_PARAM_KEY_TERMINAL, constants.TERMINAL_FRONT))
            elif action_type_prefix == constants.SEQ_PREFIX_SM_SET_PROTECTION_I and self.smu_protection_current_input:
                 self.smu_protection_current_input.setText(str(params.get(constants.SEQ_PARAM_KEY_CURRENT_LIMIT, '')))
        # Temp
        elif target_tab_widget == self.temp_tab_widget:
            if action_type_prefix == constants.SEQ_PREFIX_CHAMBER_SET_TEMP and self.chamber_set_temp_input:
                self.chamber_set_temp_input.setText(str(params.get(constants.SEQ_PARAM_KEY_VALUE, '')))
            elif action_type_prefix == constants.SEQ_PREFIX_CHAMBER_CHECK_TEMP and self.chamber_check_target_temp_input and self.chamber_check_tolerance_input and self.chamber_check_timeout_input:
                self.chamber_check_target_temp_input.setText(str(params.get(constants.SEQ_PARAM_KEY_VALUE, '')))
                self.chamber_check_tolerance_input.setText(str(params.get(constants.SEQ_PARAM_KEY_TOLERANCE, constants.DEFAULT_CHAMBER_CHECK_TEMP_TOLERANCE_DEG)))
                self.chamber_check_timeout_input.setText(str(params.get(constants.SEQ_PARAM_KEY_TIMEOUT, constants.DEFAULT_CHAMBER_CHECK_TEMP_TIMEOUT_SEC)))

        self._update_active_sub_tab_fields() # StackedWidget 페이지 업데이트 강제