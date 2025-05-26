# constants.py
from enum import Enum, auto

# --- Application Information ---
APP_NAME_FOR_DISPLAY: str = "Test Automation Environment"
APP_NAME_FOR_DIRS: str = "TestAutomationApp" # Directory name (English/numbers)
APP_VERSION: str = "0.1.0"

# --- Enums ---
class SequenceActionType(Enum):
    # I2C / Delay Actions
    I2C_WRITE_BY_NAME = "I2C_W_NAME"
    I2C_WRITE_BY_ADDRESS = "I2C_W_ADDR"
    I2C_READ_BY_NAME = "I2C_R_NAME"
    I2C_READ_BY_ADDRESS = "I2C_R_ADDR"
    DELAY_SECONDS = "DELAY_S"
    # DMM Actions
    DMM_MEASURE_VOLTAGE = "MM_MEAS_V"
    DMM_MEASURE_CURRENT = "MM_MEAS_I"
    DMM_SET_TERMINAL = "MM_SET_TERM"
    # SMU Actions
    SMU_SET_VOLTAGE = "SM_SET_V"
    SMU_SET_CURRENT = "SM_SET_I"
    SMU_MEASURE_VOLTAGE = "SM_MEAS_V"
    SMU_MEASURE_CURRENT = "SM_MEAS_I"
    SMU_ENABLE_OUTPUT = "SM_EN_OUT"
    SMU_SET_TERMINAL = "SM_SET_TERM"
    SMU_SET_PROTECTION_CURRENT = "SM_SET_PROT_I"
    # Chamber Actions
    CHAMBER_SET_TEMPERATURE = "CH_SET_TEMP"
    CHAMBER_CHECK_TEMPERATURE_STABLE = "CH_CHECK_TEMP"
    # Loop Actions
    LOOP_START = "LOOP_START"
    LOOP_END = "LOOP_END"

class SequenceParameterKey(Enum):
    TARGET_NAME = "NAME"
    ADDRESS = "ADDR"
    VALUE = "VAL"
    VARIABLE_NAME = "VAR"
    TERMINAL = "TERM"
    STATE = "STATE"
    SECONDS = "SEC"
    TIMEOUT_SECONDS = "TIMEOUT_SEC"
    TOLERANCE_DEGREES = "TOLERANCE_DEG"
    CURRENT_LIMIT_AMPS = "I_LIMIT"
    LOOP_ACTION_INDEX = "LP_ACT_IDX"
    LOOP_TARGET_PARAM_KEY = "LP_TGT_KEY"
    LOOP_START_VALUE = "LP_STARTV"
    LOOP_STEP_VALUE = "LP_STEPV"
    LOOP_END_VALUE = "LP_ENDV"

class TerminalType(Enum):
    FRONT = "FRONT"
    REAR = "REAR"

TERMINAL_FRONT: str = TerminalType.FRONT.value
TERMINAL_REAR: str = TerminalType.REAR.value

# UI 표시용 불리언 문자열 상수 (ActionInputPanel에서 사용될 수 있음)
BOOL_TRUE: str = "TRUE" 
BOOL_FALSE: str = "FALSE" 

class ErrorCode(Enum):
    HEX_BITS_ERROR = "0xERR_BITS"
    HEX_CONVERSION_ERROR = "0xERR_CONV"
    FIELD_NOT_FOUND_ERROR = "0xERR_NO_FIELD"

# --- File Path Constants ---
DEFAULT_JSON_REGMAP_FILE_PATH: str = ""
DEFAULT_REGA_FILE_PATH: str = "P24X_rega.txt"
DEFAULT_CONFIG_FILE: str = "config.json"
SAVED_SEQUENCES_DIR_NAME: str = "sequences"
SEQUENCE_FILE_EXTENSION: str = ".seq.json"

# --- Font Constants ---
APP_FONT: str = "맑은 고딕"
APP_FONT_MACOS: str = "Apple SD Gothic Neo"
APP_FONT_LINUX: str = "Noto Sans KR"
APP_FONT_SIZE: int = 10

FONT_MONOSPACE: str = "Consolas"
TABLE_FONT_SIZE: int = 9
LOG_FONT_SIZE: int = 9

# --- Window Size Constants ---
INITIAL_WINDOW_WIDTH: int = 1600
INITIAL_WINDOW_HEIGHT: int = 900

# --- UI String Constants ---
WINDOW_TITLE: str = f"{APP_NAME_FOR_DISPLAY} v{APP_VERSION}"
LOAD_JSON_BUTTON_TEXT: str = "Load RegMap"
LOAD_JSON_TOOLTIP: str = "Open a JSON format register map file."
NO_FILE_LOADED_LABEL: str = "No register map file loaded"
FILE_LOADED_LABEL_PREFIX: str = "Current File: "
FILE_SELECT_DIALOG_TITLE: str = "Select Register Map File"
JSON_FILES_FILTER: str = "JSON Files (*.json);;All Files (*)"
SAMPLE_NUMBER_LABEL: str = "Sample Number:"
DEFAULT_SAMPLE_NUMBER: str = ""

TAB_SETTINGS_TITLE: str = "Settings"
TAB_REG_VIEWER_TITLE: str = "Register Viewer"
TAB_SEQUENCE_CONTROLLER_TITLE: str = "Test Sequence"
TAB_RESULTS_TITLE: str = "Results Viewer"

SETTINGS_CHIP_ID_LABEL: str = "Chip ID (Hex):"
SETTINGS_EVB_STATUS_GROUP_TITLE: str = "Chip & EVB Settings"
SETTINGS_EVB_STATUS_LABEL_TEXT: str = "EVB Connection Status:"
SETTINGS_EVB_BTN_CHECK_TEXT: str = "Check EVB Connection"
SETTINGS_INSTRUMENT_GROUP_TITLE: str = "Instrument Settings"
SETTINGS_USE_MULTIMETER_LABEL: str = "Use Multimeter (Agilent/Keysight 344xx)"
SETTINGS_MULTIMETER_SERIAL_LABEL: str = "Multimeter Address/Serial:"
SETTINGS_USE_SOURCEMETER_LABEL: str = "Use Sourcemeter (Keithley 24xx)"
SETTINGS_SOURCEMETER_SERIAL_LABEL: str = "Sourcemeter Address/Serial:"
SETTINGS_USE_CHAMBER_LABEL: str = "Use Chamber (SU-241, etc.)"
SETTINGS_CHAMBER_SERIAL_LABEL: str = "Chamber Address/Serial (Optional):"
SETTINGS_EXECUTION_GROUP_TITLE: str = "Execution Options"
SETTINGS_ERROR_HALTS_SEQUENCE_LABEL: str = "Halt sequence on error"
SETTINGS_SAVE_BUTTON_TEXT: str = "Save Settings"

REG_VIEWER_COL_REGISTER_NAME: str = "Register Name"
REG_VIEWER_COL_ACCESS: str = "Access"
REG_VIEWER_COL_LENGTH: str = "Length (bits)"
REG_VIEWER_COL_ADDRESS: str = "Address (Range)"
REG_VIEWER_COL_VALUE_HEX: str = "Value (Hex)"
REG_VIEWER_COL_DESCRIPTION: str = "Description"

SEQ_LIST_LABEL: str = "<b>Test Sequence List:</b>"
SEQ_LOG_LABEL: str = "<b>Execution Log:</b>"
SEQ_ADD_BUTTON_TEXT: str = " Add Action"
SEQ_PLAY_BUTTON_TEXT: str = " Run Sequence"
SEQ_STOP_BUTTON_TEXT: str = " Stop Execution"
SEQ_CLEAR_BUTTON_TEXT: str = " Clear List"
SEQ_REMOVE_BUTTON_TEXT: str = " Delete Selected"
DEFINE_LOOP_BUTTON_TEXT: str = " Define Loop"

SAVED_SEQUENCES_GROUP_TITLE: str = "Saved Sequences"
LOAD_SEQUENCE_BUTTON_TEXT: str = " Load"
SAVE_SEQUENCE_AS_BUTTON_TEXT: str = " Save As..."
RENAME_SEQUENCE_BUTTON_TEXT: str = " Rename"
DELETE_SEQUENCE_BUTTON_TEXT: str = " Delete"
SEQUENCE_NAME_INPUT_DIALOG_TITLE: str = "Enter Sequence Name"
SEQUENCE_NAME_INPUT_DIALOG_LABEL: str = "Sequence Name:"

SEQ_SUB_TAB_I2C_TITLE: str = "I2C / Delay"
SEQ_SUB_TAB_DMM_TITLE: str = "DMM"
SEQ_SUB_TAB_SMU_TITLE: str = "SMU"
SEQ_SUB_TAB_TEMP_TITLE: str = "Chamber"

SEQ_INPUT_REG_NAME_LABEL: str = "Register Name:"
SEQ_INPUT_REG_NAME_PLACEHOLDER: str = "e.g., SW_RESET (autocomplete supported)"
SEQ_INPUT_I2C_ADDR_LABEL: str = "Address (Hex):"
SEQ_INPUT_I2C_ADDR_PLACEHOLDER: str = "e.g., 0x003A"
SEQ_INPUT_I2C_VALUE_LABEL: str = "Value (Hex):"
SEQ_INPUT_I2C_VALUE_PLACEHOLDER: str = "e.g., 0xFF or FF"
SEQ_INPUT_DELAY_LABEL: str = "Delay (seconds):"
SEQ_INPUT_SAVE_AS_LABEL: str = "<b>Save Result As:</b>"
SEQ_INPUT_SAVE_AS_PLACEHOLDER: str = "e.g., V_out, I_leak (no spaces)"
SEQ_INPUT_TERMINAL_LABEL: str = "<b>Terminal:</b>"
SEQ_INPUT_NUMERIC_VALUE_LABEL: str = "Set Value (Numeric):"
SEQ_INPUT_NUMERIC_VALUE_PLACEHOLDER: str = "e.g., 5.0 or 0.001"
SEQ_INPUT_TEMP_LABEL: str = "Temperature (°C):"
SEQ_INPUT_OUTPUT_STATE_LABEL: str = "Output State:"
SEQ_INPUT_TIMEOUT_LABEL: str = "Timeout (sec, optional):"
SEQ_INPUT_TOLERANCE_LABEL: str = "Tolerance (°C, optional):"
SEQ_INPUT_CURRENT_LIMIT_LABEL: str = "Current Limit (A):"

# ActionInputPanel의 QComboBox에 표시될 문자열 상수들
ACTION_I2C_WRITE_NAME: str = "I2C Write (Name)"
ACTION_I2C_WRITE_ADDR: str = "I2C Write (Address)"
ACTION_I2C_READ_NAME: str = "I2C Read (Name)"
ACTION_I2C_READ_ADDR: str = "I2C Read (Address)"
ACTION_DELAY: str = "Delay (Seconds)"

ACTION_MM_MEAS_V: str = "DMM Measure Voltage"
ACTION_MM_MEAS_I: str = "DMM Measure Current"
ACTION_MM_SET_TERMINAL: str = "DMM Set Terminal"

ACTION_SM_SET_V: str = "SMU Set Voltage"
ACTION_SM_SET_I: str = "SMU Set Current"
ACTION_SM_MEAS_V: str = "SMU Measure Voltage"
ACTION_SM_MEAS_I: str = "SMU Measure Current"
ACTION_SM_ENABLE_OUTPUT: str = "SMU Enable Output"
ACTION_SM_SET_TERMINAL: str = "SMU Set Terminal"
ACTION_SM_SET_PROTECTION_I: str = "SMU Set Protection Current"

ACTION_CHAMBER_SET_TEMP: str = "Chamber Set Temperature"
ACTION_CHAMBER_CHECK_TEMP: str = "Chamber Wait for Temperature"

# ActionInputPanel에서 사용하는 실제 리스트 변수명
I2C_DELAY_ACTIONS_LIST: list[str] = [
    ACTION_I2C_WRITE_NAME, ACTION_I2C_WRITE_ADDR,
    ACTION_I2C_READ_NAME, ACTION_I2C_READ_ADDR,
    ACTION_DELAY
]
DMM_ACTIONS_LIST: list[str] = [
    ACTION_MM_MEAS_V, ACTION_MM_MEAS_I, ACTION_MM_SET_TERMINAL
]
SMU_ACTIONS_LIST: list[str] = [
    ACTION_SM_SET_V, ACTION_SM_SET_I,
    ACTION_SM_MEAS_V, ACTION_SM_MEAS_I,
    ACTION_SM_ENABLE_OUTPUT, ACTION_SM_SET_TERMINAL,
    ACTION_SM_SET_PROTECTION_I
]
TEMP_ACTIONS_LIST: list[str] = [
    ACTION_CHAMBER_SET_TEMP, ACTION_CHAMBER_CHECK_TEMP
]

RESULTS_CLEAR_BUTTON_TEXT: str = "Clear Results"
RESULTS_EXPORT_BUTTON_TEXT: str = "Export to Excel"
EXPORT_SETTINGS_BUTTON_TEXT: str = "Export Settings..."
EXPORT_CONFIG_DIALOG_TITLE: str = "Excel Export Settings"
ADD_SHEET_BUTTON_TEXT: str = "Add Sheet"
REMOVE_SHEET_BUTTON_TEXT: str = "Remove Sheet"
SHEET_NAME_LABEL: str = "Sheet Name:"
AVAILABLE_COLUMNS_LABEL: str = "Available Columns:"
COLUMNS_IN_SHEET_LABEL: str = "Columns in Current Sheet:"

MSG_TITLE_SUCCESS: str = "Success"
MSG_TITLE_ERROR: str = "Error"
MSG_TITLE_WARNING: str = "Warning"
MSG_TITLE_INFO: str = "Information"
MSG_JSON_LOAD_SUCCESS: str = "Successfully loaded register map '{filename}'."
MSG_JSON_LOAD_FAIL_PARSE: str = "Failed to load or parse register map '{filename}'."
MSG_JSON_LOAD_FAIL_GENERIC: str = "Error loading file: {error}"
MSG_NO_REGMAP_LOADED: str = "Please load a register map file first."
MSG_INPUT_EMPTY_GENERIC: str = "Required input field is empty."
MSG_INVALID_HEX_VALUE: str = "Invalid Hex value: {value}"
MSG_INVALID_NUMERIC_VALUE: str = "Invalid numeric value: {value}"
MSG_FIELD_ID_NOT_FOUND: str = "Register name '{field_id}' not found."
MSG_SETTINGS_SAVED: str = "Settings saved successfully."
MSG_SETTINGS_SAVE_FAILED: str = "Failed to save settings."
MSG_DEVICE_NOT_ENABLED: str = "{device_name} is not enabled or not initialized."
MSG_DEVICE_CONNECTION_FAILED: str = "{device_name} (Address/Serial: {serial_number}) connection failed."
MSG_ACTION_NOT_SUPPORTED: str = "Selected action type is not currently supported."
MSG_SEQUENCE_PLAYBACK_COMPLETE: str = "Test sequence execution completed."
MSG_SEQUENCE_PLAYBACK_ABORTED: str = "Test sequence execution aborted."
MSG_SEQUENCE_EMPTY: str = "Test sequence is empty."
MSG_VALUE_EXCEEDS_WIDTH: str = "Value '{value}' exceeds field '{field_id}' length ({length} bits)."
MSG_CANNOT_PARSE_HEX_FOR_FIELD: str = "Cannot parse value '{value}' as Hex for field."
MSG_CHAMBER_TEMP_STABLE: str = "Chamber temperature stabilized at target {target_temp}°C (Current: {current_temp}°C)."
MSG_CHAMBER_TEMP_TIMEOUT: str = "Chamber temperature stabilization timeout (Target: {target_temp}°C, Current: {current_temp}°C, Timeout: {timeout}s)."


COLOR_BACKGROUND_MAIN: str = "#ECEFF1"
COLOR_BACKGROUND_LIGHT: str = "#FFFFFF"
COLOR_TEXT_DARK: str = "#263238"
COLOR_TEXT_MUTED: str = "#546E7A"
COLOR_ACCENT_PRIMARY: str = "#0288D1"
COLOR_ACCENT_PRIMARY_DARK: str = "#0277BD"
COLOR_ACCENT_PRIMARY_DARKER: str = "#01579B"
COLOR_BORDER_LIGHT: str = "#B0BEC5"
COLOR_BORDER_INPUT: str = "#90A4AE"
COLOR_BUTTON_NORMAL_BG: str = COLOR_ACCENT_PRIMARY
COLOR_BUTTON_NORMAL_BORDER: str = COLOR_ACCENT_PRIMARY_DARK
COLOR_BUTTON_HOVER_BG: str = COLOR_ACCENT_PRIMARY_DARK
COLOR_BUTTON_HOVER_BORDER: str = COLOR_ACCENT_PRIMARY_DARKER
COLOR_BUTTON_PRESSED_BG: str = COLOR_ACCENT_PRIMARY_DARKER
COLOR_BUTTON_TEXT: str = "#FFFFFF"
COLOR_BUTTON_DISABLED_BG: str = "#CFD8DC"
COLOR_BUTTON_DISABLED_BORDER: str = "#BDBDBD"
COLOR_BUTTON_DISABLED_TEXT: str = "#78909C"
COLOR_BUTTON_TEXT_LIGHT: str = "#FFFFFF"
COLOR_BACKGROUND_TAB_INACTIVE: str = "#B0BEC5"
COLOR_BACKGROUND_TAB_HOVER: str = "#CFD8DC"
COLOR_BACKGROUND_INPUT: str = "#FFFFFF"
COLOR_TEXT_INPUT: str = "#000000"
COLOR_SELECTION_BACKGROUND: str = COLOR_ACCENT_PRIMARY
COLOR_SELECTION_TEXT: str = COLOR_BUTTON_TEXT_LIGHT
COLOR_GRIDLINE: str = "#CFD8DC"
COLOR_HEADER_BACKGROUND: str = "#E0E0E0"
COLOR_TEXT_HEADER: str = "#000000"
COLOR_BORDER_HEADER: str = "#9E9E9E"
COLOR_LOAD_JSON_BUTTON_BG: str = "#E0E0E0"
COLOR_LOAD_JSON_BUTTON_TEXT: str = "#333333"
COLOR_LOAD_JSON_BUTTON_BORDER: str = "#BDBDBD"
COLOR_LOAD_JSON_BUTTON_HOVER_BG: str = "#D0D0D0"
COLOR_LOAD_JSON_BUTTON_HOVER_BORDER: str = "#AAAAAA"
COLOR_LOAD_JSON_BUTTON_PRESSED_BG: str = "#C0C0C0"

BORDER_RADIUS_WIDGET: int = 4
BORDER_RADIUS_TAB: int = 3
BORDER_RADIUS_BUTTON: int = 4
BORDER_RADIUS_INPUT: int = 3
PADDING_TAB_Y: int = 7
PADDING_TAB_X: int = 12
LOAD_JSON_BUTTON_PADDING_Y: int = 5
LOAD_JSON_BUTTON_PADDING_X: int = 10
LOAD_JSON_BUTTON_MIN_HEIGHT: int = 28
PADDING_BUTTON_Y: int = 6
PADDING_BUTTON_X: int = 12
BUTTON_MIN_HEIGHT: int = 28
PADDING_INPUT: int = 5
PADDING_HEADER: int = 5
TAB_MIN_WIDTH_EX: int = 20

BITS_PER_ADDRESS: int = 8
HEX_ERROR_NO_FIELD: str = ErrorCode.FIELD_NOT_FOUND_ERROR.value
HEX_ERROR_CONVERSION: str = ErrorCode.HEX_CONVERSION_ERROR.value
HEX_ERROR_BITS: str = ErrorCode.HEX_BITS_ERROR.value

DEFAULT_CHAMBER_CHECK_TEMP_TIMEOUT_SEC: float = 300.0
DEFAULT_CHAMBER_CHECK_TEMP_TOLERANCE_DEG: float = 0.5

SETTINGS_CHIP_ID_KEY: str = "chip_id"
SETTINGS_MULTIMETER_USE_KEY: str = "multimeter_use"
SETTINGS_MULTIMETER_SERIAL_KEY: str = "multimeter_serial"
SETTINGS_SOURCEMETER_USE_KEY: str = "sourcemeter_use"
SETTINGS_SOURCEMETER_SERIAL_KEY: str = "sourcemeter_serial"
SETTINGS_CHAMBER_USE_KEY: str = "chamber_use"
SETTINGS_CHAMBER_SERIAL_KEY: str = "chamber_serial"
SETTINGS_LAST_JSON_PATH_KEY: str = "last_json_path"
SETTINGS_EXCEL_SHEETS_CONFIG_KEY: str = "excel_export_sheets_config"
SETTINGS_ERROR_HALTS_SEQUENCE_KEY: str = "error_halts_sequence"

EXCEL_COL_TIMESTAMP: str = "Timestamp"
EXCEL_COL_VARIABLE_NAME: str = "Variable Name"
EXCEL_COL_VALUE: str = "Value"
EXCEL_COL_SAMPLE_NO: str = "Sample Number"
EXCEL_COL_COND_SMU_V: str = "SMU Set Voltage (V)"
EXCEL_COL_COND_SMU_I: str = "SMU Set Current (A)"
EXCEL_COL_COND_CHAMBER_T: str = "Chamber Set Temp (°C)"

class AccessType(Enum):
    READ_ONLY = "RO"
    READ_WRITE = "RW"
    WRITE_ONLY = "WO"
    NOT_APPLICABLE = "N/A"

# SequenceActionType과 SequenceParameterKey를 ActionInputPanel 등에서 직접 사용하기 위한
# 문자열 값 상수들 (Enum을 직접 참조하는 것이 더 좋을 수 있으나, 기존 코드 구조 유지)
SEQ_PREFIX_I2C_WRITE_NAME: str = SequenceActionType.I2C_WRITE_BY_NAME.value
SEQ_PREFIX_I2C_WRITE_ADDR: str = SequenceActionType.I2C_WRITE_BY_ADDRESS.value
SEQ_PREFIX_I2C_READ_NAME: str = SequenceActionType.I2C_READ_BY_NAME.value
SEQ_PREFIX_I2C_READ_ADDR: str = SequenceActionType.I2C_READ_BY_ADDRESS.value
SEQ_PREFIX_DELAY: str = SequenceActionType.DELAY_SECONDS.value
SEQ_PREFIX_MM_MEAS_V: str = SequenceActionType.DMM_MEASURE_VOLTAGE.value
SEQ_PREFIX_MM_MEAS_I: str = SequenceActionType.DMM_MEASURE_CURRENT.value
SEQ_PREFIX_MM_SET_TERMINAL: str = SequenceActionType.DMM_SET_TERMINAL.value
SEQ_PREFIX_SM_SET_V: str = SequenceActionType.SMU_SET_VOLTAGE.value
SEQ_PREFIX_SM_SET_I: str = SequenceActionType.SMU_SET_CURRENT.value
SEQ_PREFIX_SM_MEAS_V: str = SequenceActionType.SMU_MEASURE_VOLTAGE.value
SEQ_PREFIX_SM_MEAS_I: str = SequenceActionType.SMU_MEASURE_CURRENT.value
SEQ_PREFIX_SM_ENABLE_OUTPUT: str = SequenceActionType.SMU_ENABLE_OUTPUT.value
SEQ_PREFIX_SM_SET_TERMINAL: str = SequenceActionType.SMU_SET_TERMINAL.value
SEQ_PREFIX_SM_SET_PROTECTION_I: str = SequenceActionType.SMU_SET_PROTECTION_CURRENT.value
SEQ_PREFIX_CHAMBER_SET_TEMP: str = SequenceActionType.CHAMBER_SET_TEMPERATURE.value
SEQ_PREFIX_CHAMBER_CHECK_TEMP: str = SequenceActionType.CHAMBER_CHECK_TEMPERATURE_STABLE.value
SEQ_PREFIX_LOOP_START: str = SequenceActionType.LOOP_START.value
SEQ_PREFIX_LOOP_END: str = SequenceActionType.LOOP_END.value

SEQ_PARAM_KEY_TARGET_NAME: str = SequenceParameterKey.TARGET_NAME.value
SEQ_PARAM_KEY_ADDRESS: str = SequenceParameterKey.ADDRESS.value
SEQ_PARAM_KEY_VALUE: str = SequenceParameterKey.VALUE.value
SEQ_PARAM_KEY_VARIABLE: str = SequenceParameterKey.VARIABLE_NAME.value
SEQ_PARAM_KEY_TERMINAL: str = SequenceParameterKey.TERMINAL.value
SEQ_PARAM_KEY_STATE: str = SequenceParameterKey.STATE.value
SEQ_PARAM_KEY_SECONDS: str = SequenceParameterKey.SECONDS.value
SEQ_PARAM_KEY_TIMEOUT: str = SequenceParameterKey.TIMEOUT_SECONDS.value
SEQ_PARAM_KEY_TOLERANCE: str = SequenceParameterKey.TOLERANCE_DEGREES.value
SEQ_PARAM_KEY_CURRENT_LIMIT: str = SequenceParameterKey.CURRENT_LIMIT_AMPS.value
SEQ_PARAM_KEY_LOOP_ACTION_INDEX: str = SequenceParameterKey.LOOP_ACTION_INDEX.value
SEQ_PARAM_KEY_LOOP_TARGET_PARAM_KEY: str = SequenceParameterKey.LOOP_TARGET_PARAM_KEY.value
SEQ_PARAM_KEY_LOOP_START_VALUE: str = SequenceParameterKey.LOOP_START_VALUE.value
SEQ_PARAM_KEY_LOOP_STEP_VALUE: str = SequenceParameterKey.LOOP_STEP_VALUE.value
SEQ_PARAM_KEY_LOOP_END_VALUE: str = SequenceParameterKey.LOOP_END_VALUE.value