# core/settings_manager.py
import json
import os
# constants 모듈을 core 패키지에서 임포트합니다.
from core import constants 

class SettingsManager:
    """
    애플리케이션 설정을 관리하는 클래스입니다.
    설정은 JSON 파일 형태로 저장되고 로드됩니다.
    """
    def __init__(self, config_file_name: str = constants.DEFAULT_CONFIG_FILE):
        """
        SettingsManager를 초기화합니다.

        Args:
            config_file_name (str): 설정 파일의 이름입니다.
                                    core.constants에 정의된 DEFAULT_CONFIG_FILE을 사용합니다.
        """
        self.config_file_path = config_file_name
        self.default_settings = {
            "chip_id": "0x18",
            "multimeter_use": False,
            "multimeter_serial": "GPIB0::22::INSTR", 
            "sourcemeter_use": False,
            "sourcemeter_serial": "GPIB0::24::INSTR", 
            "chamber_use": False,
            "chamber_serial": "", 
            constants.SETTINGS_LAST_JSON_PATH_KEY: "", 
            constants.SETTINGS_EXCEL_SHEETS_CONFIG_KEY: [ 
                {
                    "sheet_name": "AllData",
                    "columns": [
                        "Timestamp", "Variable Name", "Value", 
                        constants.EXCEL_COL_SAMPLE_NO, 
                    ]
                }
            ],
            # 새로운 설정값 추가: 오류 발생 시 시퀀스 중단 여부
            "error_halts_sequence": False 
        }

    def load_settings(self) -> dict:
        """
        설정 파일에서 설정을 로드합니다.
        파일이 없거나 유효하지 않은 경우 기본 설정을 반환합니다.

        Returns:
            dict: 로드된 설정 또는 기본 설정.
        """
        if not os.path.exists(self.config_file_path):
            print(f"Info: 설정 파일 '{self.config_file_path}'을(를) 찾을 수 없습니다. 기본 설정을 사용합니다.")
            return self.default_settings.copy()
        try:
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            # 로드된 설정에 누락된 키가 있는지 확인하고 기본값으로 채움
            for key, value in self.default_settings.items():
                if key not in settings:
                    settings[key] = value
            return settings
        except json.JSONDecodeError:
            print(f"Error: 설정 파일 '{self.config_file_path}'을(를) 파싱하는 데 실패했습니다. 기본 설정을 사용합니다.")
            return self.default_settings.copy()
        except Exception as e:
            print(f"Error: 설정 파일 로드 중 예외 발생: {e}. 기본 설정을 사용합니다.")
            return self.default_settings.copy()

    def save_settings(self, settings_dict: dict) -> bool:
        """
        주어진 설정 딕셔너리를 설정 파일에 저장합니다.

        Args:
            settings_dict (dict): 저장할 설정 딕셔너리.

        Returns:
            bool: 저장 성공 시 True, 실패 시 False.
        """
        try:
            complete_settings = self.default_settings.copy()
            complete_settings.update(settings_dict) 

            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(complete_settings, f, indent=4, ensure_ascii=False)
            print(f"Info: 설정이 '{self.config_file_path}'에 성공적으로 저장되었습니다.")
            return True
        except Exception as e:
            print(f"Error: 설정을 '{self.config_file_path}'에 저장하는 중 오류 발생: {e}")
            return False

if __name__ == '__main__':
    # 테스트를 위해 core.constants를 직접 참조하도록 수정
    # 이 테스트는 core 디렉토리 외부에서 실행될 경우 core.constants를 찾지 못할 수 있습니다.
    # 일반적으로 패키지 내 모듈의 __main__ 테스트는 해당 패키지 구조를 인지하고 실행해야 합니다.
    # 예: python -m core.settings_manager 로 실행
    
    # 임시로 constants 모듈 객체를 만들어 테스트 (실제 실행 환경에서는 불필요)
    class MockConstants:
        DEFAULT_CONFIG_FILE = "test_config_core.json"
        SETTINGS_LAST_JSON_PATH_KEY = "last_json_path_core"
        SETTINGS_EXCEL_SHEETS_CONFIG_KEY = "excel_export_sheets_config_core"
        EXCEL_COL_SAMPLE_NO = "Sample Number Core"

    # 실제 core.constants를 사용하려면, 이 파일이 core 패키지의 일부로 실행되어야 합니다.
    # 여기서는 MockConstants를 사용하거나, 실행 환경에 맞게 core.constants를 임포트해야 합니다.
    # 아래는 core.constants가 올바르게 임포트되었다고 가정하고 진행합니다.
    # from core import constants # 이미 위에서 임포트됨

    # 테스트 파일명을 변경하여 이전 테스트와 충돌 방지
    test_config_filename = "test_settings_manager_core.json"
    # constants 객체의 속성을 직접 수정하는 대신, 테스트용 constants 객체를 사용하거나
    # 테스트 시에만 파일명을 직접 지정합니다.
    # setattr(constants, 'DEFAULT_CONFIG_FILE', test_config_filename) # 권장하지 않음

    manager = SettingsManager(config_file_name=test_config_filename)

    print("\n--- 초기 설정 로드 (파일 없을 시) ---")
    if os.path.exists(test_config_filename):
        os.remove(test_config_filename) 
    settings = manager.load_settings()
    print("로드된 설정:", settings)
    assert constants.SETTINGS_LAST_JSON_PATH_KEY in settings
    assert settings[constants.SETTINGS_LAST_JSON_PATH_KEY] == ""
    assert constants.SETTINGS_EXCEL_SHEETS_CONFIG_KEY in settings
    assert isinstance(settings[constants.SETTINGS_EXCEL_SHEETS_CONFIG_KEY], list)
    assert "error_halts_sequence" in settings
    assert settings["error_halts_sequence"] is False

    if settings[constants.SETTINGS_EXCEL_SHEETS_CONFIG_KEY]:
         assert "sheet_name" in settings[constants.SETTINGS_EXCEL_SHEETS_CONFIG_KEY][0]
         assert "columns" in settings[constants.SETTINGS_EXCEL_SHEETS_CONFIG_KEY][0]

    print("\n--- 설정 변경 및 저장 ---")
    settings['chip_id'] = "0x2A"
    settings[constants.SETTINGS_LAST_JSON_PATH_KEY] = "/path/to/last/regmap_core.json"
    settings["error_halts_sequence"] = True 
    manager.save_settings(settings)

    print("\n--- 변경된 설정 다시 로드 ---")
    reloaded_settings = manager.load_settings()
    print("다시 로드된 설정:", reloaded_settings)
    assert reloaded_settings.get('chip_id') == "0x2A"
    assert reloaded_settings.get(constants.SETTINGS_LAST_JSON_PATH_KEY) == "/path/to/last/regmap_core.json"
    assert reloaded_settings.get("error_halts_sequence") is True

    print("\n--- 일부 키 누락된 설정 저장 및 로드 ---")
    partial_settings = {"chip_id": "0x3B", "sourcemeter_use": True} 
    manager.save_settings(partial_settings)
    reloaded_partial = manager.load_settings()
    print("부분 설정 저장 후 로드:", reloaded_partial)
    assert reloaded_partial.get("error_halts_sequence") == manager.default_settings["error_halts_sequence"]

    print("\n--- 잘못된 JSON 파일 로드 테스트 ---")
    with open(test_config_filename, 'w', encoding='utf-8') as f:
        f.write("{corrupted_json: ") 
    corrupted_settings = manager.load_settings()
    print("손상된 파일 로드 시 설정:", corrupted_settings)
    assert corrupted_settings == manager.default_settings

    if os.path.exists(test_config_filename):
        os.remove(test_config_filename)
        print(f"\n테스트용 설정 파일 '{test_config_filename}' 삭제 완료.")