# ui/widgets/action_input_panel.py
import sys
import re # 정규표현식 모듈 임포트 추가
from typing import List, Tuple, Dict, Any, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QStackedWidget, QGridLayout, QDoubleSpinBox, QCompleter, QTabWidget,
    QMessageBox, QApplication, QStyle, QCheckBox # QCheckBox 추가
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
        self.active_loop_variables_model = QStringListModel(self) # 루프 변수 모델

        # UI 멤버 변수 초기화 (루프 변수 관련 UI 요소 추가)
        self.action_group_tabs: Optional[QTabWidget] = None

        # I2C/Delay 탭 UI 요소
        self.i2c_tab_widget: Optional[QWidget] = None
        self.i2c_action_combo: Optional[QComboBox] = None
        self.i2c_params_stack: Optional[QStackedWidget] = None
        self.i2c_write_name_target_input: Optional[QLineEdit] = None
        self.i2c_write_name_value_input: Optional[QLineEdit] = None
        self.i2c_write_name_value_use_loop_var_checkbox: Optional[QCheckBox] = None
        self.i2c_write_name_value_loop_var_combo: Optional[QComboBox] = None
        self.i2c_write_addr_target_input: Optional[QLineEdit] = None
        self.i2c_write_addr_value_input: Optional[QLineEdit] = None
        self.i2c_write_addr_value_use_loop_var_checkbox: Optional[QCheckBox] = None
        self.i2c_write_addr_value_loop_var_combo: Optional[QComboBox] = None
        self.i2c_read_name_target_input: Optional[QLineEdit] = None
        self.i2c_read_name_var_name_input: Optional[QLineEdit] = None
        self.i2c_read_addr_target_input: Optional[QLineEdit] = None
        self.i2c_read_addr_var_name_input: Optional[QLineEdit] = None
        self.delay_seconds_input: Optional[QDoubleSpinBox] = None
        self.delay_seconds_use_loop_var_checkbox: Optional[QCheckBox] = None
        self.delay_seconds_loop_var_combo: Optional[QComboBox] = None


        # DMM 탭 UI 요소 (Value를 받는 부분이 명확하지 않아 일단 보류)
        self.dmm_tab_widget: Optional[QWidget] = None
        self.dmm_action_combo: Optional[QComboBox] = None
        self.dmm_params_stack: Optional[QStackedWidget] = None
        self.dmm_measure_var_name_input: Optional[QLineEdit] = None
        self.dmm_terminal_combo: Optional[QComboBox] = None

        # SMU 탭 UI 요소
        self.smu_tab_widget: Optional[QWidget] = None
        self.smu_action_combo: Optional[QComboBox] = None
        self.smu_params_stack: Optional[QStackedWidget] = None
        self.smu_set_value_label: Optional[QLabel] = None
        self.smu_set_value_input: Optional[QLineEdit] = None
        self.smu_set_value_use_loop_var_checkbox: Optional[QCheckBox] = None
        self.smu_set_value_loop_var_combo: Optional[QComboBox] = None
        self.smu_set_terminal_combo: Optional[QComboBox] = None
        self.smu_measure_var_name_input: Optional[QLineEdit] = None
        self.smu_measure_terminal_combo: Optional[QComboBox] = None
        self.smu_output_state_combo: Optional[QComboBox] = None
        self.smu_terminal_combo: Optional[QComboBox] = None
        self.smu_protection_current_input: Optional[QLineEdit] = None
        self.smu_protection_current_use_loop_var_checkbox: Optional[QCheckBox] = None
        self.smu_protection_current_loop_var_combo: Optional[QComboBox] = None
        self.smu_vsource_terminal_label: Optional[QLabel] = None
        self.smu_vsource_terminal_combo: Optional[QComboBox] = None


        # Chamber 탭 UI 요소
        self.temp_tab_widget: Optional[QWidget] = None
        self.temp_action_combo: Optional[QComboBox] = None
        self.temp_params_stack: Optional[QStackedWidget] = None
        self.chamber_set_temp_input: Optional[QLineEdit] = None
        self.chamber_set_temp_use_loop_var_checkbox: Optional[QCheckBox] = None
        self.chamber_set_temp_loop_var_combo: Optional[QComboBox] = None
        self.chamber_check_target_temp_input: Optional[QLineEdit] = None
        self.chamber_check_target_temp_use_loop_var_checkbox: Optional[QCheckBox] = None
        self.chamber_check_target_temp_loop_var_combo: Optional[QComboBox] = None
        self.chamber_check_tolerance_input: Optional[QLineEdit] = None
        self.chamber_check_tolerance_use_loop_var_checkbox: Optional[QCheckBox] = None
        self.chamber_check_tolerance_loop_var_combo: Optional[QComboBox] = None
        self.chamber_check_timeout_input: Optional[QLineEdit] = None
        self.chamber_check_timeout_use_loop_var_checkbox: Optional[QCheckBox] = None
        self.chamber_check_timeout_loop_var_combo: Optional[QComboBox] = None


        self._hex_validator = QRegularExpressionValidator(QRegularExpression("[0-9A-Fa-fXx]*"))
        self._double_validator = QDoubleValidator()
        self._double_validator.setNotation(QDoubleValidator.StandardNotation)
        self._double_validator.setDecimals(6)

        self._setup_ui()
        self.update_settings(self.current_settings)

    def _create_loop_var_widgets(self, base_name: str, parent_layout: QGridLayout, row: int, existing_line_edit: Optional[QLineEdit]) -> Tuple[QCheckBox, QComboBox]: # existing_line_edit을 Optional로 변경
        """Helper to create and layout checkbox and combobox for loop variable usage."""
        checkbox = QCheckBox("Use Loop Var")
        combobox = QComboBox()
        combobox.setModel(self.active_loop_variables_model)
        combobox.setEnabled(False)

        parent_layout.addWidget(checkbox, row, 2)
        parent_layout.addWidget(combobox, row, 3)
        
        # Connect signals
        # existing_line_edit이 None일 수 있으므로, 이를 _toggle_loop_var_ui에 전달
        checkbox.toggled.connect(lambda checked, le=existing_line_edit, cb=combobox: self._toggle_loop_var_ui(checked, le, cb))
        return checkbox, combobox

    def _toggle_loop_var_ui(self, checked: bool, line_edit: Optional[QLineEdit], combobox: Optional[QComboBox], spinbox: Optional[QDoubleSpinBox] = None):
        """Toggles enabled state of line_edit/spinbox and combobox based on checkbox."""
        if line_edit: line_edit.setEnabled(not checked)
        if spinbox: spinbox.setEnabled(not checked)
        if combobox: combobox.setEnabled(checked)
        
        if checked:
            if line_edit and line_edit.text(): 
                pass
            if spinbox and spinbox.value() != spinbox.minimum():
                pass
        else: 
            if line_edit: line_edit.setPlaceholderText(getattr(line_edit, "_original_placeholder", "")) 
            if spinbox: 
                spinbox.setSpecialValueText("")

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
        self.i2c_write_name_value_use_loop_var_checkbox, self.i2c_write_name_value_loop_var_combo = \
            self._create_loop_var_widgets("i2c_write_name_value", layout_i2c_write_name, 1, self.i2c_write_name_value_input)
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
        self.i2c_write_addr_value_use_loop_var_checkbox, self.i2c_write_addr_value_loop_var_combo = \
            self._create_loop_var_widgets("i2c_write_addr_value", layout_i2c_write_addr, 1, self.i2c_write_addr_value_input)
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
        self.delay_seconds_use_loop_var_checkbox, self.delay_seconds_loop_var_combo = \
            self._create_loop_var_widgets("delay_seconds", layout_delay, 0, existing_line_edit=None) # QDoubleSpinBox, special handling below
        # Special handling for QDoubleSpinBox
        self.delay_seconds_use_loop_var_checkbox.toggled.connect(
            lambda checked, sb=self.delay_seconds_input, cb=self.delay_seconds_loop_var_combo: 
            self._toggle_loop_var_ui(checked, None, cb, sb)
        )
        self.i2c_params_stack.addWidget(page_delay)

        # Placeholder 페이지 (아무 액션도 선택되지 않았을 때)
        page_placeholder_i2c = QWidget()
        layout_placeholder_i2c = QVBoxLayout(page_placeholder_i2c)
        layout_placeholder_i2c.addWidget(QLabel("Select an I2C/Delay action above."), alignment=Qt.AlignCenter)
        self.i2c_params_stack.addWidget(page_placeholder_i2c)

        # Hold (Popup/Hold) 액션 추가
        self.hold_name_input = QLineEdit()
        self.hold_name_input.setPlaceholderText("Enter hold name (popup message)")
        hold_layout = QGridLayout()
        hold_layout.addWidget(QLabel("Hold Name:"), 0, 0)
        hold_layout.addWidget(self.hold_name_input, 0, 1)
        hold_widget = QWidget()
        hold_widget.setLayout(hold_layout)
        self.i2c_params_stack.addWidget(hold_widget)

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
        self.smu_action_combo.addItems(constants.SMU_ACTIONS_LIST)
        self.smu_action_combo.currentIndexChanged.connect(self._update_active_sub_tab_fields)
        layout.addWidget(self.smu_action_combo)
        self.smu_params_stack = QStackedWidget()
        self._create_smu_params_widgets()
        layout.addWidget(self.smu_params_stack)
        layout.addStretch()
        self.action_group_tabs.addTab(tab, constants.SEQ_SUB_TAB_SMU_TITLE)
        # --- 위젯 None 방지: 생성 직후 assert ---
        assert self.smu_action_combo is not None, "smu_action_combo is None after creation"
        assert self.smu_params_stack is not None, "smu_params_stack is None after creation"

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
        self.smu_set_value_use_loop_var_checkbox, self.smu_set_value_loop_var_combo = \
            self._create_loop_var_widgets("smu_set_value", layout_smu_set, 0, self.smu_set_value_input)
        self.smu_params_stack.addWidget(page_smu_set)  # 0: SET_VALUE

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
        self.smu_params_stack.addWidget(page_smu_measure)  # 1: MEASURE

        # SMU Output Control 페이지
        page_smu_output_control = QWidget()
        layout_smu_output_control = QGridLayout(page_smu_output_control)
        layout_smu_output_control.setVerticalSpacing(12); layout_smu_output_control.setHorizontalSpacing(8)
        layout_smu_output_control.addWidget(QLabel(constants.SEQ_INPUT_OUTPUT_STATE_LABEL), 0, 0)
        self.smu_output_state_combo = QComboBox()
        self.smu_output_state_combo.addItems([
            constants.SMU_OUTPUT_STATE_ENABLE, 
            constants.SMU_OUTPUT_STATE_DISABLE,
            constants.SMU_OUTPUT_STATE_VSOURCE  # constants에서 정의된 값 사용
        ])
        layout_smu_output_control.addWidget(self.smu_output_state_combo, 0, 1)
        self.smu_params_stack.addWidget(page_smu_output_control)  # 2: ENABLE_OUTPUT

        # SMU Set Terminal 페이지
        page_smu_set_terminal = QWidget()
        layout_smu_set_terminal = QGridLayout(page_smu_set_terminal)
        layout_smu_set_terminal.setVerticalSpacing(12); layout_smu_set_terminal.setHorizontalSpacing(8)
        layout_smu_set_terminal.addWidget(QLabel(constants.SEQ_INPUT_TERMINAL_LABEL), 0, 0)
        self.smu_terminal_combo = QComboBox()
        self.smu_terminal_combo.addItems([constants.TERMINAL_FRONT, constants.TERMINAL_REAR])
        layout_smu_set_terminal.addWidget(self.smu_terminal_combo, 0, 1)
        self.smu_params_stack.addWidget(page_smu_set_terminal)  # 3: SET_TERMINAL

        # SMU Set Protection Current 페이지
        page_smu_set_protection_i = QWidget()
        layout_smu_set_protection_i = QGridLayout(page_smu_set_protection_i)
        layout_smu_set_protection_i.setVerticalSpacing(12); layout_smu_set_protection_i.setHorizontalSpacing(8)
        layout_smu_set_protection_i.addWidget(QLabel(constants.SEQ_INPUT_CURRENT_LIMIT_LABEL), 0, 0)
        self.smu_protection_current_input = QLineEdit()
        self.smu_protection_current_input.setValidator(self._double_validator)
        self.smu_protection_current_input.setPlaceholderText("e.g., 0.1 (for 100mA)")
        layout_smu_set_protection_i.addWidget(self.smu_protection_current_input, 0, 1)
        self.smu_protection_current_use_loop_var_checkbox, self.smu_protection_current_loop_var_combo = \
            self._create_loop_var_widgets("smu_protection_current", layout_smu_set_protection_i, 0, self.smu_protection_current_input)
        self.smu_params_stack.addWidget(page_smu_set_protection_i)  # 4: SET_PROTECTION_I

        # Placeholder 페이지
        page_placeholder_smu = QWidget()
        layout_placeholder_smu = QVBoxLayout(page_placeholder_smu)
        layout_placeholder_smu.addWidget(QLabel("Select an SMU action above."), alignment=Qt.AlignCenter)
        self.smu_params_stack.addWidget(page_placeholder_smu)  # 5: PLACEHOLDER

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

        # Set Temp 페이지
        page_set_temp = QWidget()
        layout_set_temp = QGridLayout(page_set_temp)
        layout_set_temp.setVerticalSpacing(12); layout_set_temp.setHorizontalSpacing(8)
        self.chamber_set_temp_input = QLineEdit() # Moved and ensured assignment
        self.chamber_set_temp_input.setPlaceholderText("예: 25 (도씨)")
        self.chamber_set_temp_input.setValidator(double_validator_temp)
        layout_set_temp.addWidget(QLabel(constants.SEQ_INPUT_TEMP_LABEL), 0, 0) # Corrected label usage
        layout_set_temp.addWidget(self.chamber_set_temp_input, 0, 1)
        self.chamber_set_temp_use_loop_var_checkbox, self.chamber_set_temp_loop_var_combo = self._create_loop_var_widgets(
            "CHAMBER_SET_TEMP_VAL", layout_set_temp, 0, self.chamber_set_temp_input) # Ensure correct row and pass input
        page_set_temp.setLayout(layout_set_temp) # Ensure layout is set on page
        self.temp_params_stack.addWidget(page_set_temp)

        # Check Temp 페이지
        page_check_temp = QWidget()
        layout_check_temp = QGridLayout(page_check_temp)
        layout_check_temp.setVerticalSpacing(12); layout_check_temp.setHorizontalSpacing(8)
        self.chamber_check_target_temp_input = QLineEdit() # Moved and ensured assignment
        self.chamber_check_target_temp_input.setPlaceholderText("예: 25 (도씨)")
        self.chamber_check_target_temp_input.setValidator(double_validator_temp)
        layout_check_temp.addWidget(QLabel(constants.SEQ_INPUT_TEMP_LABEL), 0, 0) # Corrected label usage
        layout_check_temp.addWidget(self.chamber_check_target_temp_input, 0, 1)
        self.chamber_check_target_temp_use_loop_var_checkbox, self.chamber_check_target_temp_loop_var_combo = self._create_loop_var_widgets(
            "CHAMBER_CHECK_TEMP_VAL", layout_check_temp, 0, self.chamber_check_target_temp_input)

        self.chamber_check_tolerance_input = QLineEdit() # Moved and ensured assignment
        self.chamber_check_tolerance_input.setPlaceholderText(f"기본값: {constants.DEFAULT_CHAMBER_CHECK_TEMP_TOLERANCE_DEG}")
        self.chamber_check_tolerance_input.setValidator(self._double_validator) # General double validator for tolerance
        layout_check_temp.addWidget(QLabel(constants.SEQ_INPUT_TOLERANCE_LABEL), 1, 0)
        layout_check_temp.addWidget(self.chamber_check_tolerance_input, 1, 1)
        # Remove loop variable widgets for tolerance
        # self.chamber_check_tolerance_use_loop_var_checkbox, self.chamber_check_tolerance_loop_var_combo = self._create_loop_var_widgets(
        #     "CHAMBER_CHECK_TEMP_TOL", layout_check_temp, 1, self.chamber_check_tolerance_input)

        self.chamber_check_timeout_input = QLineEdit() # Moved and ensured assignment
        self.chamber_check_timeout_input.setPlaceholderText(f"기본값: {constants.DEFAULT_CHAMBER_CHECK_TEMP_TIMEOUT_SEC}")
        self.chamber_check_timeout_input.setValidator(self._double_validator) # General double validator for timeout
        layout_check_temp.addWidget(QLabel(constants.SEQ_INPUT_TIMEOUT_LABEL), 2, 0)
        layout_check_temp.addWidget(self.chamber_check_timeout_input, 2, 1)
        # Remove loop variable widgets for timeout
        # self.chamber_check_timeout_use_loop_var_checkbox, self.chamber_check_timeout_loop_var_combo = self._create_loop_var_widgets(
        #     "CHAMBER_CHECK_TEMP_TIMEOUT", layout_check_temp, 2, self.chamber_check_timeout_input)
        page_check_temp.setLayout(layout_check_temp) # Ensure layout is set on page
        self.temp_params_stack.addWidget(page_check_temp)

        # Placeholder 페이지
        page_placeholder_temp = QWidget()
        layout_placeholder_temp = QVBoxLayout(page_placeholder_temp)
        layout_placeholder_temp.addWidget(QLabel("Select a Chamber action above."), alignment=Qt.AlignCenter)
        self.temp_params_stack.addWidget(page_placeholder_temp)

    def _update_active_sub_tab_fields(self, index: Optional[int] = None):
        """
        현재 활성화된 서브 탭의 입력 필드 상태를 업데이트합니다.
        (예: 필드명, 단위, 기본값 등)
        """
        if not self.action_group_tabs: return
        current_tab_index = self.action_group_tabs.currentIndex()

        # I2C/Delay 탭 UI 업데이트
        if current_tab_index == 0:
            if self.i2c_action_combo and self.i2c_params_stack:
                action_text = self.i2c_action_combo.currentText()
                if action_text == constants.ACTION_I2C_WRITE_NAME: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.WRITE_NAME)
                elif action_text == constants.ACTION_I2C_WRITE_ADDR: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.WRITE_ADDR)
                elif action_text == constants.ACTION_I2C_READ_NAME: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.READ_NAME)
                elif action_text == constants.ACTION_I2C_READ_ADDR: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.READ_ADDR)
                elif action_text == constants.ACTION_DELAY: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.DELAY)
                elif action_text == constants.ACTION_HOLD: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.PLACEHOLDER + 1) # Hold 위젯 인덱스
                else: self.i2c_params_stack.setCurrentIndex(self.I2CParamPages.PLACEHOLDER)

        # DMM 탭 UI 업데이트
        elif current_tab_index == 1:
            if self.dmm_action_combo and self.dmm_params_stack:
                action_text = self.dmm_action_combo.currentText()
                if action_text in [constants.ACTION_MM_MEAS_V, constants.ACTION_MM_MEAS_I]: self.dmm_params_stack.setCurrentIndex(self.DMMParamPages.MEASURE)
                elif action_text == constants.ACTION_MM_SET_TERMINAL: self.dmm_params_stack.setCurrentIndex(self.DMMParamPages.SET_TERMINAL)
                else: self.dmm_params_stack.setCurrentIndex(self.DMMParamPages.PLACEHOLDER)
            
        # SMU 탭 UI 업데이트
        elif current_tab_index == 2:
            if not self.smu_action_combo or not self.smu_params_stack: return
            action_text = self.smu_action_combo.currentText()
            if action_text == constants.ACTION_SM_SET_V or action_text == constants.ACTION_SM_SET_I:
                self.smu_params_stack.setCurrentIndex(self.SMUParamPages.SET_VALUE)
            elif action_text == constants.ACTION_SM_MEAS_V or action_text == constants.ACTION_SM_MEAS_I:
                self.smu_params_stack.setCurrentIndex(self.SMUParamPages.MEASURE)
            elif action_text == constants.ACTION_SM_OUTPUT_CONTROL:
                self.smu_params_stack.setCurrentIndex(self.SMUParamPages.ENABLE_OUTPUT)
            elif action_text == constants.ACTION_SM_SET_TERMINAL:
                self.smu_params_stack.setCurrentIndex(self.SMUParamPages.SET_TERMINAL)
            elif action_text == constants.ACTION_SM_SET_PROTECTION_I:
                self.smu_params_stack.setCurrentIndex(self.SMUParamPages.SET_PROTECTION_I)
            else:
                self.smu_params_stack.setCurrentIndex(self.SMUParamPages.PLACEHOLDER)
        
        # Chamber 탭 UI 업데이트
        elif current_tab_index == 3:
            if self.temp_action_combo and self.temp_params_stack:
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
        """
        현재 입력된 액션의 문자열, 시퀀스 프리픽스, 파라미터 dict를 반환합니다.
        (액션 추가/수정 시 호출)
        """
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
                
                item_str_prefix = constants.SEQ_PREFIX_I2C_WRITE_NAME
                name = self.i2c_write_name_target_input.text().strip()
                
                value_str = ""
                if self.i2c_write_name_value_use_loop_var_checkbox and self.i2c_write_name_value_use_loop_var_checkbox.isChecked():
                    cb = self.i2c_write_name_value_loop_var_combo
                    print(f"DEBUG_LOOP_VAR: I2C_WRITE_NAME - Checkbox checked. ComboBox text: '{cb.currentText()}', index: {cb.currentIndex()}, model count: {cb.model().rowCount()}")
                    selected_loop_var_text = cb.currentText()
                    selected_loop_var_index = cb.currentIndex()
                    if selected_loop_var_text and selected_loop_var_index > 0: 
                        value_str = f"{{{selected_loop_var_text}}}"
                    else:
                        QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "A loop variable must be selected for I2C Write Name Value when 'Use Loop Var' is checked."); return None
                else:
                    value_hex_raw = self.i2c_write_name_value_input.text().strip()
                    value_hex_normalized = normalize_hex_input(value_hex_raw, add_prefix=True)
                    if not value_hex_normalized and value_hex_raw:
                        QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INVALID_HEX_VALUE.format(value=value_hex_raw)); return None
                    value_str = value_hex_normalized
                
                if not name or not value_str:
                    QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INPUT_EMPTY_GENERIC); return None
                if self.register_map and name not in self.register_map.logical_fields_map: # register_map None 체크 추가
                    QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_FIELD_ID_NOT_FOUND.format(field_id=name)); return None
                
                params_list_for_str.extend([f"{constants.SEQ_PARAM_KEY_TARGET_NAME}={name}", f"{constants.SEQ_PARAM_KEY_VALUE}={value_str}"])
                params_dict_for_data[constants.SEQ_PARAM_KEY_TARGET_NAME] = name
                params_dict_for_data[constants.SEQ_PARAM_KEY_VALUE] = value_str
            
            # ... (ACTION_I2C_WRITE_ADDR, READ_NAME, READ_ADDR, DELAY에 대한 로직도 유사하게 constants 사용) ...
            elif action_text == constants.ACTION_I2C_WRITE_ADDR:
                item_str_prefix = constants.SEQ_PREFIX_I2C_WRITE_ADDR
                addr_hex_raw = self.i2c_write_addr_target_input.text().strip()
                addr_hex_normalized = normalize_hex_input(addr_hex_raw, 4, add_prefix=True)
                if not addr_hex_normalized and addr_hex_raw: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, f"잘못된 주소 형식: {addr_hex_raw}"); return None
                if not addr_hex_normalized : QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INPUT_EMPTY_GENERIC); return None

                value_str = ""
                if self.i2c_write_addr_value_use_loop_var_checkbox and self.i2c_write_addr_value_use_loop_var_checkbox.isChecked():
                    cb = self.i2c_write_addr_value_loop_var_combo
                    print(f"DEBUG_LOOP_VAR: I2C_WRITE_ADDR - Checkbox checked. ComboBox text: '{cb.currentText()}', index: {cb.currentIndex()}, model count: {cb.model().rowCount()}")
                    selected_loop_var_text = cb.currentText()
                    selected_loop_var_index = cb.currentIndex()
                    if selected_loop_var_text and selected_loop_var_index > 0:
                        value_str = f"{{{selected_loop_var_text}}}"
                    else:
                        QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "A loop variable must be selected for I2C Write Address Value when 'Use Loop Var' is checked."); return None
                else:
                    value_hex_raw = self.i2c_write_addr_value_input.text().strip()
                    value_hex_normalized = normalize_hex_input(value_hex_raw, 2, add_prefix=True)
                    if not value_hex_normalized and value_hex_raw: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INVALID_HEX_VALUE.format(value=value_hex_raw)); return None
                    value_str = value_hex_normalized

                if not value_str: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, constants.MSG_INPUT_EMPTY_GENERIC); return None
                
                params_list_for_str.extend([f"{constants.SEQ_PARAM_KEY_ADDRESS}={addr_hex_normalized}", f"{constants.SEQ_PARAM_KEY_VALUE}={value_str}"])
                params_dict_for_data[constants.SEQ_PARAM_KEY_ADDRESS] = addr_hex_normalized; params_dict_for_data[constants.SEQ_PARAM_KEY_VALUE] = value_str

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
                delay_val_str = ""
                if self.delay_seconds_use_loop_var_checkbox and self.delay_seconds_use_loop_var_checkbox.isChecked():
                    cb = self.delay_seconds_loop_var_combo
                    print(f"DEBUG_LOOP_VAR: DELAY - Checkbox checked. ComboBox text: '{cb.currentText()}', index: {cb.currentIndex()}, model count: {cb.model().rowCount()}")
                    selected_loop_var_text = cb.currentText()
                    selected_loop_var_index = cb.currentIndex()
                    if selected_loop_var_text and selected_loop_var_index > 0:
                        delay_val_str = f"{{{selected_loop_var_text}}}"
                    else:
                        QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "A loop variable must be selected for Delay Seconds when 'Use Loop Var' is checked."); return None
                else:
                    delay_val = self.delay_seconds_input.value()
                    if delay_val <= 0: QMessageBox.warning(self, constants.MSG_TITLE_WARNING, "지연 시간은 0보다 커야 합니다."); return None
                    delay_val_str = str(delay_val)
                
                params_list_for_str.append(f"{constants.SEQ_PARAM_KEY_SECONDS}={delay_val_str}")
                params_dict_for_data[constants.SEQ_PARAM_KEY_SECONDS] = delay_val_str
            elif action_text == constants.ACTION_HOLD:
                hold_name = self.hold_name_input.text().strip()
                if not hold_name:
                    QMessageBox.warning(self, "입력 오류", "Hold 이름을 입력하세요.")
                    return None
                return (constants.ACTION_HOLD, constants.SequenceActionType.HOLD.value, {"HOLD_NAME": hold_name})
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
            if not self._is_device_enabled(constants.SETTINGS_SOURCEMETER_USE_KEY, "Sourcemeter"): return None
            action_text = self.smu_action_combo.currentText()
            item_str_prefix = ""
            params_list_for_str = [] # Ensure this list is used to build the display string
            params_dict_for_data = {}

            # Helper to add param to both list and dict if value exists
            def add_smu_param(key_const: str, value: Optional[str], value_for_str: Optional[str] = None):
                if value is not None and value.strip():
                    params_dict_for_data[key_const] = value.strip()
                    # Use value_for_str if provided (e.g. for loop var placeholders), else use actual value
                    params_list_for_str.append(f"{key_const}={value_for_str if value_for_str is not None else value.strip()}")

            if action_text == constants.ACTION_SM_SET_V:
                if self.smu_set_value_input is None: QMessageBox.critical(self, "내부 UI 오류", "SMU 전압 입력란이 준비되지 않았습니다."); return None
                item_str_prefix = constants.SEQ_PREFIX_SM_SET_V
                val_str, val_for_display_str = self._get_value_or_loop_var_text(self.smu_set_value_input, self.smu_set_value_use_loop_var_checkbox, self.smu_set_value_loop_var_combo)
                if not val_str: QMessageBox.warning(self, "값 입력 필요", "전압 값을 입력하세요."); return None
                add_smu_param(constants.SEQ_PARAM_KEY_VALUE, val_str, val_for_display_str)

            elif action_text == constants.ACTION_SM_SET_I:
                if self.smu_set_value_input is None: QMessageBox.critical(self, "내부 UI 오류", "SMU 전류 입력란이 준비되지 않았습니다."); return None
                item_str_prefix = constants.SEQ_PREFIX_SM_SET_I
                val_str, val_for_display_str = self._get_value_or_loop_var_text(self.smu_set_value_input, self.smu_set_value_use_loop_var_checkbox, self.smu_set_value_loop_var_combo)
                if not val_str: QMessageBox.warning(self, "값 입력 필요", "전류 값을 입력하세요."); return None
                add_smu_param(constants.SEQ_PARAM_KEY_VALUE, val_str, val_for_display_str)

            elif action_text == constants.ACTION_SM_MEAS_V:
                if self.smu_measure_var_name_input is None or self.smu_measure_terminal_combo is None: QMessageBox.critical(self, "내부 UI 오류", "SMU 측정 UI 요소 누락."); return None
                item_str_prefix = constants.SEQ_PREFIX_SM_MEAS_V
                var_name = self.smu_measure_var_name_input.text().strip()
                term = self.smu_measure_terminal_combo.currentText()
                if not var_name: QMessageBox.warning(self, "값 입력 필요", "결과 변수명을 입력하세요."); return None
                add_smu_param(constants.SEQ_PARAM_KEY_VARIABLE, var_name)
                add_smu_param(constants.SEQ_PARAM_KEY_TERMINAL, term)
            
            elif action_text == constants.ACTION_SM_MEAS_I:
                if self.smu_measure_var_name_input is None or self.smu_measure_terminal_combo is None: QMessageBox.critical(self, "내부 UI 오류", "SMU 측정 UI 요소 누락."); return None
                item_str_prefix = constants.SEQ_PREFIX_SM_MEAS_I
                var_name = self.smu_measure_var_name_input.text().strip()
                term = self.smu_measure_terminal_combo.currentText()
                if not var_name: QMessageBox.warning(self, "값 입력 필요", "결과 변수명을 입력하세요."); return None
                add_smu_param(constants.SEQ_PARAM_KEY_VARIABLE, var_name)
                add_smu_param(constants.SEQ_PARAM_KEY_TERMINAL, term)

            elif action_text == constants.ACTION_SM_OUTPUT_CONTROL:
                if self.smu_output_state_combo is None: QMessageBox.critical(self, "내부 UI 오류", "SMU Output Control 콤보박스가 준비되지 않았습니다."); return None
                selected_state = self.smu_output_state_combo.currentText().strip().upper()
                if selected_state == constants.SMU_OUTPUT_STATE_VSOURCE:
                    item_str_prefix = constants.SEQ_PREFIX_SM_CONFIGURE_VSOURCE_AND_ENABLE
                    # No specific parameters for this one usually, relies on prior Set V
                else:
                    item_str_prefix = constants.SEQ_PREFIX_SM_ENABLE_OUTPUT # Changed from SM_OUTPUT_CONTROL to specific enable/disable
                    state_bool_val = "TRUE" if selected_state == constants.SMU_OUTPUT_STATE_ENABLE else "FALSE"
                    add_smu_param(constants.SEQ_PARAM_KEY_STATE, state_bool_val)
            
            elif action_text == constants.ACTION_SM_SET_TERMINAL:
                if self.smu_terminal_combo is None: QMessageBox.critical(self, "내부 UI 오류", "SMU 터미널 콤보박스가 준비되지 않았습니다."); return None
                item_str_prefix = constants.SEQ_PREFIX_SM_SET_TERMINAL
                term = self.smu_terminal_combo.currentText().strip()
                if not term: QMessageBox.warning(self, "값 입력 필요", "터미널을 선택하세요."); return None
                add_smu_param(constants.SEQ_PARAM_KEY_TERMINAL, term)

            elif action_text == constants.ACTION_SM_SET_PROTECTION_I:
                if self.smu_protection_current_input is None: QMessageBox.critical(self, "내부 UI 오류", "SMU 보호 전류 입력란이 준비되지 않았습니다."); return None
                item_str_prefix = constants.SEQ_PREFIX_SM_SET_PROTECTION_I
                val_str, val_for_display_str = self._get_value_or_loop_var_text(self.smu_protection_current_input, self.smu_protection_current_use_loop_var_checkbox, self.smu_protection_current_loop_var_combo)
                if not val_str: QMessageBox.warning(self, "값 입력 필요", "보호 전류 값을 입력하세요."); return None
                add_smu_param(constants.SEQ_PARAM_KEY_CURRENT_LIMIT, val_str, val_for_display_str)
            else:
                QMessageBox.warning(self, constants.MSG_TITLE_WARNING, f"Unsupported SMU action: {action_text}"); return None
            
            full_action_string_smu = f"{item_str_prefix}: {'; '.join(params_list_for_str) if params_list_for_str else ''}"
            return item_str_prefix, full_action_string_smu, params_dict_for_data
        
        # Chamber 탭
        elif current_tab_index == 3:
            if not self._is_device_enabled(constants.SETTINGS_CHAMBER_USE_KEY, "Chamber"): return None
            action_text = self.temp_action_combo.currentText()
            item_str_prefix = ""
            params_list_for_str = [] # Ensure this list is used
            params_dict_for_data = {}

            # Helper to add param to both list and dict if value exists
            def add_chamber_param(key_const: str, value: Optional[str], value_for_str: Optional[str] = None):
                if value is not None and value.strip(): # Ensure value is not None and not just whitespace
                    params_dict_for_data[key_const] = value.strip()
                    params_list_for_str.append(f"{key_const}={value_for_str if value_for_str is not None else value.strip()}")

            if action_text == constants.ACTION_CHAMBER_SET_TEMP:
                if self.chamber_set_temp_input is None: QMessageBox.critical(self, "내부 UI 오류", "Chamber 온도 설정 입력란 누락."); return None
                item_str_prefix = constants.SEQ_PREFIX_CHAMBER_SET_TEMP
                val_str, val_for_display_str = self._get_value_or_loop_var_text(self.chamber_set_temp_input, self.chamber_set_temp_use_loop_var_checkbox, self.chamber_set_temp_loop_var_combo)
                if not val_str: QMessageBox.warning(self, "값 입력 필요", "온도 값을 입력하세요."); return None
                add_chamber_param(constants.SEQ_PARAM_KEY_VALUE, val_str, val_for_display_str)

            elif action_text == constants.ACTION_CHAMBER_CHECK_TEMP:
                if self.chamber_check_target_temp_input is None or self.chamber_check_tolerance_input is None or self.chamber_check_timeout_input is None: 
                     QMessageBox.critical(self, "내부 UI 오류", "Chamber 온도 확인 UI 요소 누락."); return None
                item_str_prefix = constants.SEQ_PREFIX_CHAMBER_CHECK_TEMP
                
                val_str, val_for_display_str = self._get_value_or_loop_var_text(self.chamber_check_target_temp_input, self.chamber_check_target_temp_use_loop_var_checkbox, self.chamber_check_target_temp_loop_var_combo)
                if not val_str: QMessageBox.warning(self, "값 입력 필요", "목표 온도 값을 입력하세요."); return None
                add_chamber_param(constants.SEQ_PARAM_KEY_VALUE, val_str, val_for_display_str)

                tol_str, tol_for_display_str = self._get_value_or_loop_var_text(self.chamber_check_tolerance_input, self.chamber_check_tolerance_use_loop_var_checkbox, self.chamber_check_tolerance_loop_var_combo)
                if tol_str: add_chamber_param(constants.SEQ_PARAM_KEY_TOLERANCE, tol_str, tol_for_display_str)
                
                timeout_str, timeout_for_display_str = self._get_value_or_loop_var_text(self.chamber_check_timeout_input, self.chamber_check_timeout_use_loop_var_checkbox, self.chamber_check_timeout_loop_var_combo)
                if timeout_str: add_chamber_param(constants.SEQ_PARAM_KEY_TIMEOUT, timeout_str, timeout_for_display_str)
            else:
                QMessageBox.warning(self, constants.MSG_TITLE_WARNING, f"Unsupported Chamber action: {action_text}"); return None
            
            full_action_string_temp = f"{item_str_prefix}: {'; '.join(params_list_for_str) if params_list_for_str else ''}"
            return item_str_prefix, full_action_string_temp, params_dict_for_data
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
                if self.i2c_write_name_value_use_loop_var_checkbox: self.i2c_write_name_value_use_loop_var_checkbox.setChecked(False)
            elif action_text == constants.ACTION_I2C_WRITE_ADDR:
                if self.i2c_write_addr_target_input: self.i2c_write_addr_target_input.clear(); self.i2c_write_addr_target_input.setStyleSheet(""); self.i2c_write_addr_target_input.setToolTip("")
                if self.i2c_write_addr_value_input: self.i2c_write_addr_value_input.clear(); self.i2c_write_addr_value_input.setStyleSheet(""); self.i2c_write_addr_value_input.setToolTip("")
                if self.i2c_write_addr_value_use_loop_var_checkbox: self.i2c_write_addr_value_use_loop_var_checkbox.setChecked(False)
            elif action_text == constants.ACTION_I2C_READ_NAME:
                if self.i2c_read_name_target_input: self.i2c_read_name_target_input.clear()
                if self.i2c_read_name_var_name_input: self.i2c_read_name_var_name_input.clear()
            elif action_text == constants.ACTION_I2C_READ_ADDR:
                if self.i2c_read_addr_target_input: self.i2c_read_addr_target_input.clear(); self.i2c_read_addr_target_input.setStyleSheet(""); self.i2c_read_addr_target_input.setToolTip("")
                if self.i2c_read_addr_var_name_input: self.i2c_read_addr_var_name_input.clear()
            elif action_text == constants.ACTION_DELAY:
                if self.delay_seconds_input: self.delay_seconds_input.setValue(0.01) # 기본값으로 리셋
                if self.delay_seconds_use_loop_var_checkbox: self.delay_seconds_use_loop_var_checkbox.setChecked(False)
        
        elif current_tab_index == 1 and self.dmm_action_combo: # DMM
            action_text = self.dmm_action_combo.currentText()
            if action_text in [constants.ACTION_MM_MEAS_V, constants.ACTION_MM_MEAS_I]:
                if self.dmm_measure_var_name_input: self.dmm_measure_var_name_input.clear()
            # Set Terminal은 콤보박스이므로 별도 clear 불필요 (기본값으로 유지)
        
        elif current_tab_index == 2 and self.smu_action_combo: # SMU
            action_text = self.smu_action_combo.currentText()
            if action_text in [constants.ACTION_SM_SET_V, constants.ACTION_SM_SET_I]:
                if self.smu_set_value_input: self.smu_set_value_input.clear()
                if self.smu_set_value_use_loop_var_checkbox: self.smu_set_value_use_loop_var_checkbox.setChecked(False)
            elif action_text in [constants.ACTION_SM_MEAS_V, constants.ACTION_SM_MEAS_I]:
                if self.smu_measure_var_name_input: self.smu_measure_var_name_input.clear()
            elif action_text == constants.ACTION_SM_SET_PROTECTION_I:
                if self.smu_protection_current_input: self.smu_protection_current_input.clear()
                if self.smu_protection_current_use_loop_var_checkbox: self.smu_protection_current_use_loop_var_checkbox.setChecked(False)
            # 콤보박스들은 선택 유지
            
        elif current_tab_index == 3 and self.temp_action_combo: # Chamber
            action_text = self.temp_action_combo.currentText()
            if action_text == constants.ACTION_CHAMBER_SET_TEMP:
                if self.chamber_set_temp_input: self.chamber_set_temp_input.clear()
                if self.chamber_set_temp_use_loop_var_checkbox: self.chamber_set_temp_use_loop_var_checkbox.setChecked(False)
            elif action_text == constants.ACTION_CHAMBER_CHECK_TEMP:
                if self.chamber_check_target_temp_input: self.chamber_check_target_temp_input.clear()
                if self.chamber_check_target_temp_use_loop_var_checkbox: self.chamber_check_target_temp_use_loop_var_checkbox.setChecked(False)
                if self.chamber_check_tolerance_input: self.chamber_check_tolerance_input.clear()
                if self.chamber_check_tolerance_use_loop_var_checkbox: self.chamber_check_tolerance_use_loop_var_checkbox.setChecked(False)
                if self.chamber_check_timeout_input: self.chamber_check_timeout_input.clear()
                if self.chamber_check_timeout_use_loop_var_checkbox: self.chamber_check_timeout_use_loop_var_checkbox.setChecked(False)

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
        """
        self.current_settings = new_settings if new_settings is not None else {}
        print(f"DEBUG_AIP_UpdateSettings: Settings updated in ActionInputPanel. DMM_use: {self.current_settings.get(constants.SETTINGS_MULTIMETER_USE_KEY)}, SMU_use: {self.current_settings.get(constants.SETTINGS_SOURCEMETER_USE_KEY)}, Chamber_use: {self.current_settings.get(constants.SETTINGS_CHAMBER_USE_KEY)}")
        
        # The actual tab enabling/disabling is handled by enable_instrument_sub_tab, 
        # which is called from SequenceControllerTab, which in turn gets it from MainWindow.
        # However, _update_active_sub_tab_fields might be needed if the current action combo selection
        # becomes invalid due to a tab becoming disabled.
        self._update_active_sub_tab_fields() 

    def enable_instrument_sub_tab(self, instrument_type: str, enabled: bool):
        """Enables or disables a specific instrument sub-tab (DMM, SMU, Chamber)."""
        print(f"DEBUG_AIP: enable_instrument_sub_tab called for '{instrument_type}', enabled: {enabled}")
        target_tab_widget: Optional[QWidget] = None
        tab_title_for_lookup: Optional[str] = None

        if instrument_type == "DMM":
            # target_tab_widget = self.dmm_tab_widget # Direct widget reference might be more robust
            tab_title_for_lookup = constants.SEQ_SUB_TAB_DMM_TITLE
        elif instrument_type == "SMU":
            # target_tab_widget = self.smu_tab_widget
            tab_title_for_lookup = constants.SEQ_SUB_TAB_SMU_TITLE
        elif instrument_type == "CHAMBER": 
            # target_tab_widget = self.temp_tab_widget
            tab_title_for_lookup = constants.SEQ_SUB_TAB_TEMP_TITLE
        else:
            print(f"ERROR_AIP: Unknown instrument_type '{instrument_type}' in enable_instrument_sub_tab.")
            return

        if self.action_group_tabs and tab_title_for_lookup:
            tab_idx = -1
            for i in range(self.action_group_tabs.count()):
                if self.action_group_tabs.tabText(i) == tab_title_for_lookup:
                    tab_idx = i
                    break
            
            if tab_idx != -1:
                current_visual_state = self.action_group_tabs.isTabEnabled(tab_idx)
                print(f"DEBUG_AIP: {instrument_type} sub-tab (idx {tab_idx}, title '{tab_title_for_lookup}') current visual enabled: {current_visual_state}, attempting to set to: {enabled}")
                self.action_group_tabs.setTabEnabled(tab_idx, enabled)
                QApplication.processEvents() 
                final_visual_state = self.action_group_tabs.isTabEnabled(tab_idx)
                print(f"VERIFY_AIP_{instrument_type}_TAB: {instrument_type} tab index {tab_idx} is NOW actually enabled: {final_visual_state} (desired: {enabled})")

                if not enabled and self.action_group_tabs.widget(tab_idx) == self.action_group_tabs.currentWidget():
                    # Switch to the I2C tab (index 0) if the currently active tab is being disabled
                    self.action_group_tabs.setCurrentIndex(0) 
                    print(f"DEBUG_AIP: {instrument_type} tab was current and disabled, switched to I2C tab (index 0).")
            else:
                print(f"ERROR_AIP: {instrument_type} sub-tab with title '{tab_title_for_lookup}' not found in action_group_tabs for enable/disable.")
        elif not self.action_group_tabs:
            print("ERROR_AIP: self.action_group_tabs is None in enable_instrument_sub_tab.")
        elif not tab_title_for_lookup:
             print(f"ERROR_AIP: tab_title_for_lookup is None for {instrument_type} in enable_instrument_sub_tab.")

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
                self._load_value_or_loop_var(params.get(constants.SEQ_PARAM_KEY_VALUE, ''), self.i2c_write_name_value_input, self.i2c_write_name_value_use_loop_var_checkbox, self.i2c_write_name_value_loop_var_combo)
            elif action_type_prefix == constants.SEQ_PREFIX_I2C_WRITE_ADDR and self.i2c_write_addr_target_input and self.i2c_write_addr_value_input:
                self.i2c_write_addr_target_input.setText(params.get(constants.SEQ_PARAM_KEY_ADDRESS, ''))
                self._load_value_or_loop_var(params.get(constants.SEQ_PARAM_KEY_VALUE, ''), self.i2c_write_addr_value_input, self.i2c_write_addr_value_use_loop_var_checkbox, self.i2c_write_addr_value_loop_var_combo)
            elif action_type_prefix == constants.SEQ_PREFIX_I2C_READ_NAME and self.i2c_read_name_target_input and self.i2c_read_name_var_name_input:
                self.i2c_read_name_target_input.setText(params.get(constants.SEQ_PARAM_KEY_TARGET_NAME, ''))
                self.i2c_read_name_var_name_input.setText(params.get(constants.SEQ_PARAM_KEY_VARIABLE, '')) # Loop var for var_name not typical
            elif action_type_prefix == constants.SEQ_PREFIX_I2C_READ_ADDR and self.i2c_read_addr_target_input and self.i2c_read_addr_var_name_input:
                self.i2c_read_addr_target_input.setText(params.get(constants.SEQ_PARAM_KEY_ADDRESS, ''))
                self.i2c_read_addr_var_name_input.setText(params.get(constants.SEQ_PARAM_KEY_VARIABLE, '')) # Loop var for var_name not typical
            elif action_type_prefix == constants.SEQ_PREFIX_DELAY and self.delay_seconds_input:
                self._load_value_or_loop_var(params.get(constants.SEQ_PARAM_KEY_SECONDS, '0.01'), None, self.delay_seconds_use_loop_var_checkbox, self.delay_seconds_loop_var_combo, self.delay_seconds_input)
        # DMM (값 필드 없으므로 루프 변수 로드 로직은 현재 불필요)
        elif target_tab_widget == self.dmm_tab_widget:
            if action_type_prefix in [constants.SEQ_PREFIX_MM_MEAS_V, constants.SEQ_PREFIX_MM_MEAS_I] and self.dmm_measure_var_name_input:
                self.dmm_measure_var_name_input.setText(params.get(constants.SEQ_PARAM_KEY_VARIABLE, ''))
            elif action_type_prefix == constants.SEQ_PREFIX_MM_SET_TERMINAL and self.dmm_terminal_combo:
                self.dmm_terminal_combo.setCurrentText(params.get(constants.SEQ_PARAM_KEY_TERMINAL, constants.TERMINAL_FRONT))
        # SMU
        elif target_tab_widget == self.smu_tab_widget:
            if action_type_prefix in [constants.SEQ_PREFIX_SM_SET_V, constants.SEQ_PREFIX_SM_SET_I] and self.smu_set_value_input and self.smu_set_terminal_combo:
                self._load_value_or_loop_var(params.get(constants.SEQ_PARAM_KEY_VALUE, ''), self.smu_set_value_input, self.smu_set_value_use_loop_var_checkbox, self.smu_set_value_loop_var_combo)
                self.smu_set_terminal_combo.setCurrentText(params.get(constants.SEQ_PARAM_KEY_TERMINAL, constants.TERMINAL_FRONT))
            elif action_type_prefix in [constants.SEQ_PREFIX_SM_MEAS_V, constants.SEQ_PREFIX_SM_MEAS_I] and self.smu_measure_var_name_input and self.smu_measure_terminal_combo:
                self.smu_measure_var_name_input.setText(params.get(constants.SEQ_PARAM_KEY_VARIABLE, ''))
                self.smu_measure_terminal_combo.setCurrentText(params.get(constants.SEQ_PARAM_KEY_TERMINAL, constants.TERMINAL_FRONT))
            elif action_type_prefix == constants.SEQ_PREFIX_SM_ENABLE_OUTPUT and self.smu_output_state_combo:
                self.smu_output_state_combo.setCurrentText(params.get(constants.SEQ_PARAM_KEY_STATE, constants.BOOL_TRUE))
            elif action_type_prefix == constants.SEQ_PREFIX_SM_SET_TERMINAL and self.smu_terminal_combo:
                self.smu_terminal_combo.setCurrentText(params.get(constants.SEQ_PARAM_KEY_TERMINAL, constants.TERMINAL_FRONT))
            elif action_type_prefix == constants.SEQ_PREFIX_SM_SET_PROTECTION_I and self.smu_protection_current_input:
                 self._load_value_or_loop_var(params.get(constants.SEQ_PARAM_KEY_CURRENT_LIMIT, ''), self.smu_protection_current_input, self.smu_protection_current_use_loop_var_checkbox, self.smu_protection_current_loop_var_combo)
        # Temp
        elif target_tab_widget == self.temp_tab_widget:
            if action_type_prefix == constants.SEQ_PREFIX_CHAMBER_SET_TEMP and self.chamber_set_temp_input:
                self._load_value_or_loop_var(params.get(constants.SEQ_PARAM_KEY_VALUE, ''), self.chamber_set_temp_input, self.chamber_set_temp_use_loop_var_checkbox, self.chamber_set_temp_loop_var_combo)
            elif action_type_prefix == constants.SEQ_PREFIX_CHAMBER_CHECK_TEMP and self.chamber_check_target_temp_input and self.chamber_check_tolerance_input and self.chamber_check_timeout_input:
                self._load_value_or_loop_var(params.get(constants.SEQ_PARAM_KEY_VALUE, ''), self.chamber_check_target_temp_input, self.chamber_check_target_temp_use_loop_var_checkbox, self.chamber_check_target_temp_loop_var_combo)
                self._load_value_or_loop_var(params.get(constants.SEQ_PARAM_KEY_TOLERANCE, str(constants.DEFAULT_CHAMBER_CHECK_TEMP_TOLERANCE_DEG)), self.chamber_check_tolerance_input, self.chamber_check_tolerance_use_loop_var_checkbox, self.chamber_check_tolerance_loop_var_combo)
                self._load_value_or_loop_var(params.get(constants.SEQ_PARAM_KEY_TIMEOUT, str(constants.DEFAULT_CHAMBER_CHECK_TEMP_TIMEOUT_SEC)), self.chamber_check_timeout_input, self.chamber_check_timeout_use_loop_var_checkbox, self.chamber_check_timeout_loop_var_combo)

        self._update_active_sub_tab_fields() # StackedWidget 페이지 업데이트 강제

    def _load_value_or_loop_var(self, value_str: str, 
                                line_edit: Optional[QLineEdit], 
                                checkbox: Optional[QCheckBox], 
                                combobox: Optional[QComboBox],
                                spinbox: Optional[QDoubleSpinBox] = None):
        """Helper to load a value into either a line_edit/spinbox or set loop var UI."""
        if not checkbox or not combobox: return

        is_loop_var_format = isinstance(value_str, str) and value_str.startswith('{') and value_str.endswith('}')
        
        if is_loop_var_format:
            loop_var_name_match = re.match(r"\{(.*?)\}", value_str)
            if loop_var_name_match:
                loop_var_name = loop_var_name_match.group(1)
                checkbox.setChecked(True)
                idx = combobox.findText(loop_var_name)
                if idx != -1: combobox.setCurrentIndex(idx)
                else: combobox.setCurrentIndex(0)
                if line_edit: line_edit.setText("")
                if spinbox: spinbox.setValue(spinbox.minimum()) 
            else: 
                checkbox.setChecked(False)
                if line_edit: line_edit.setText(value_str)
                if spinbox:
                    try: spinbox.setValue(float(value_str))
                    except ValueError: spinbox.setValue(spinbox.minimum())
        else: 
            checkbox.setChecked(False)
            if line_edit: line_edit.setText(value_str)
            if spinbox:
                try: spinbox.setValue(float(value_str))
                except ValueError: spinbox.setValue(spinbox.minimum())
        
        self._toggle_loop_var_ui(checkbox.isChecked(), line_edit, combobox, spinbox)
        
    # === 루프 변수 목록 업데이트 함수 추가 ===
    def update_loop_variables(self, loop_vars: List[str]):
        """현재 활성화된 루프 변수 목록으로 내부 모델을 업데이트합니다."""
        if self.active_loop_variables_model is None:
            self.active_loop_variables_model = QStringListModel(self) # self를 parent로 전달
        
        current_list = [""] # 항상 "선택 안함" 옵션으로 시작
        if loop_vars:
            current_list.extend(loop_vars)
        
        self.active_loop_variables_model.setStringList(current_list)
        print(f"ActionInputPanel: Loop variables updated in model: {current_list}")

        combos_to_update = [
            self.i2c_write_name_value_loop_var_combo,
            self.i2c_write_addr_value_loop_var_combo,
            self.delay_seconds_loop_var_combo,
            self.smu_set_value_loop_var_combo,
            self.smu_protection_current_loop_var_combo,
            self.chamber_set_temp_loop_var_combo,
            self.chamber_check_target_temp_loop_var_combo,
            self.chamber_check_tolerance_loop_var_combo,
            self.chamber_check_timeout_loop_var_combo
        ]
        for combo in combos_to_update:
            if combo:
                # 모델이 이미 설정되어 있어야 하므로, setModel은 __init__에서 한번만 호출하도록 변경 고려
                # 여기서는 목록 변경 시 현재 인덱스를 초기화하거나 유효한 값으로 설정
                if combo.model() != self.active_loop_variables_model: # 모델이 다르면 설정
                    combo.setModel(self.active_loop_variables_model)
                combo.setCurrentIndex(0) 
    # === 루프 변수 목록 업데이트 함수 끝 ===

    def _toggle_smu_vsource_terminal_visibility(self, selected_state_text: str):
        """SMU Output Control 상태에 따라 V-Source용 터미널 콤보박스 가시성 조절"""
        is_vsource = (selected_state_text == constants.SMU_OUTPUT_STATE_VSOURCE)
        if self.smu_vsource_terminal_label: self.smu_vsource_terminal_label.setVisible(is_vsource)
        if self.smu_vsource_terminal_combo: self.smu_vsource_terminal_combo.setVisible(is_vsource)

    # _get_value_or_loop_var_text method was incorrectly placed inside load_action_data_for_editing
    # Moving it here to be a proper method of ActionInputPanel class.
    def _get_value_or_loop_var_text(self, line_edit: Optional[QLineEdit], checkbox: Optional[QCheckBox], combobox: Optional[QComboBox], spinbox: Optional[QDoubleSpinBox] = None) -> Tuple[Optional[str], Optional[str]]:
        """Helper to get value for parameters, either direct input or loop variable placeholder."""
        value_for_data: Optional[str] = None
        value_for_display: Optional[str] = None

        if checkbox and checkbox.isChecked() and combobox:
            selected_loop_var_text = combobox.currentText()
            selected_loop_var_index = combobox.currentIndex()
            if selected_loop_var_text and selected_loop_var_index > 0: # Index 0 is usually "Select..."
                placeholder = f"{{{selected_loop_var_text}}}"
                value_for_data = placeholder
                value_for_display = placeholder
            else:
                # This case should ideally be caught by validation before calling this helper
                return None, None 
        elif line_edit:
            raw_text = line_edit.text().strip()
            value_for_data = raw_text
            value_for_display = raw_text
        elif spinbox: # For QDoubleSpinBox like Delay
            raw_val = spinbox.value()
            value_for_data = str(raw_val)
            value_for_display = str(raw_val)
        
        return value_for_data, value_for_display