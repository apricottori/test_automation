# core/settings_manager.py
import json
import os
import sys # sys 모듈 임포트 추가
from typing import Dict, Any, Optional # Optional 임포트 추가
from PyQt5.QtCore import QStandardPaths # QStandardPaths 임포트 추가

# constants 모듈을 core 패키지에서 임포트합니다.
from core import constants

class SettingsManager:
    """
    애플리케이션 설정을 관리하는 클래스입니다.
    설정은 JSON 파일 형태로 저장되고 로드됩니다.
    """
    def __init__(self, config_file_name: str = constants.DEFAULT_CONFIG_FILE, config_file_path: Optional[str] = None):
        """
        SettingsManager를 초기화합니다.

        Args:
            config_file_name (str): 설정 파일의 이름입니다.
                                    config_file_path가 제공되지 않을 경우 경로 결정에 사용됩니다.
            config_file_path (Optional[str]): 사용할 설정 파일의 전체 경로입니다.
                                               제공되면 이 경로를 우선적으로 사용합니다.
        """
        self.config_file_name = config_file_name

        if config_file_path and os.path.isabs(config_file_path):
            # 제공된 config_file_path가 절대 경로이면 그대로 사용
            self.config_file_path = config_file_path
            print(f"INFO_SM: Using provided absolute config file path: {self.config_file_path}")
        elif config_file_path:
            # 제공된 config_file_path가 상대 경로이면, 애플리케이션 루트 기준으로 절대 경로화 시도
            # (main_window.py에서 이미 절대 경로를 만들어 전달하므로, 이 경우는 드물 수 있음)
            if getattr(sys, 'frozen', False): # PyInstaller 등으로 번들된 경우
                application_root_path = os.path.dirname(sys.executable)
            else:
                # 개발 환경: settings_manager.py 파일의 위치(core) -> 상위(test_code) -> 상위(프로젝트 루트)
                current_file_dir = os.path.dirname(os.path.abspath(__file__)) # core 디렉토리
                test_code_dir = os.path.dirname(current_file_dir) # test_code 디렉토리
                application_root_path = os.path.dirname(test_code_dir) # 프로젝트 루트 디렉토리 (가정)
            
            self.config_file_path = os.path.abspath(os.path.join(application_root_path, config_file_path))
            print(f"INFO_SM: Resolved relative config_file_path to: {self.config_file_path}")
        else:
            # config_file_path가 제공되지 않으면 _determine_config_path를 통해 결정
            self.config_file_path = self._determine_config_path()
            print(f"INFO_SM: Determined config file path: {self.config_file_path}")

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
            "error_halts_sequence": False
        }

    def _determine_config_path(self) -> str:
        """
        설정 파일의 기본 저장 경로를 결정합니다.
        1. 사용자 문서 폴더 내 앱별 폴더
        2. 애플리케이션 실행 파일과 같은 위치 (test_code 폴더 내) - 개발 시 주로 사용
        3. 현재 작업 디렉토리 (최후의 수단)
        """
        # 옵션 1: 사용자 문서 폴더 내 앱별 폴더
        try:
            docs_path = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
            if docs_path:
                app_name_for_dirs = getattr(constants, 'APP_NAME_FOR_DIRS', 'TestAutomationApp')
                app_data_path = os.path.join(docs_path, app_name_for_dirs)
                os.makedirs(app_data_path, exist_ok=True) # 폴더가 없으면 생성
                return os.path.join(app_data_path, self.config_file_name)
        except Exception as e:
            print(f"INFO_SM: Could not determine documents path for config: {e}. Trying next option.")

        # 옵션 2: 애플리케이션 실행 파일과 같은 위치 (또는 개발 시 test_code 폴더 내)
        try:
            if getattr(sys, 'frozen', False): # PyInstaller 등으로 번들된 경우
                application_path = os.path.dirname(sys.executable)
            else:
                # 개발 환경: settings_manager.py 파일의 위치(core) -> 상위(test_code)
                current_file_dir = os.path.dirname(os.path.abspath(__file__)) # core 디렉토리
                application_path = os.path.dirname(current_file_dir) # test_code 디렉토리
            return os.path.join(application_path, self.config_file_name)
        except Exception as e:
            print(f"INFO_SM: Could not determine application path for config: {e}. Using current working directory.")

        # 옵션 3: 최후의 수단으로 현재 작업 디렉토리
        return os.path.join(os.getcwd(), self.config_file_name)


    def load_settings(self) -> dict:
        """
        설정 파일에서 설정을 로드합니다.
        파일이 없거나 유효하지 않은 경우 기본 설정을 반환합니다.

        Returns:
            dict: 로드된 설정 또는 기본 설정.
        """
        if not os.path.exists(self.config_file_path):
            print(f"Info: 설정 파일 '{self.config_file_path}'을(를) 찾을 수 없습니다. 기본 설정을 사용하고 저장합니다.")
            # 파일이 없을 경우, 기본 설정을 한번 저장해준다.
            self.save_settings(self.default_settings.copy()) # 기본 설정을 파일로 저장
            return self.default_settings.copy()
        try:
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            # 로드된 설정에 누락된 키가 있는지 확인하고 기본값으로 채움
            # default_settings의 모든 키가 settings에 존재하도록 보장하고, 없으면 추가
            # 또한, settings에만 있는 불필요한 키는 유지될 수 있음 (사용자 정의 설정 가능성)
            updated_settings = self.default_settings.copy() # 기본 설정으로 시작
            updated_settings.update(settings) # 로드된 설정으로 덮어쓰거나 추가
            
            # 만약 로드된 설정과 기본 설정을 병합한 결과가 실제 저장된 내용과 다르면 업데이트 저장
            if updated_settings != settings:
                print(f"INFO_SM: Settings file '{self.config_file_path}' was updated with default values for missing keys.")
                self.save_settings(updated_settings) # 누락된 키가 채워진 설정으로 다시 저장

            return updated_settings
        except json.JSONDecodeError:
            print(f"Error: 설정 파일 '{self.config_file_path}'을(를) 파싱하는 데 실패했습니다. 기본 설정을 사용하고 저장합니다.")
            self.save_settings(self.default_settings.copy()) # 기본 설정을 파일로 저장
            return self.default_settings.copy()
        except Exception as e:
            print(f"Error: 설정 파일 로드 중 예외 발생: {e}. 기본 설정을 사용하고 저장합니다.")
            self.save_settings(self.default_settings.copy()) # 기본 설정을 파일로 저장
            return self.default_settings.copy()

    def save_settings(self, settings_dict: dict) -> bool:
        """
        주어진 설정 딕셔너리를 설정 파일에 저장합니다.
        저장 시, default_settings에 있는 모든 키가 포함되도록 보장합니다.

        Args:
            settings_dict (dict): 저장할 설정 딕셔너리.

        Returns:
            bool: 저장 성공 시 True, 실패 시 False.
        """
        try:
            # 저장할 설정은 항상 default_settings의 모든 키를 포함하도록 함
            # default_settings를 기본으로 하고, settings_dict의 값으로 업데이트
            complete_settings = self.default_settings.copy()
            complete_settings.update(settings_dict)

            # 설정 파일이 위치할 디렉토리가 존재하지 않으면 생성
            config_dir = os.path.dirname(self.config_file_path)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
                print(f"INFO_SM: Created directory for config file: {config_dir}")

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

    # 테스트 파일명을 변경하여 이전 테스트와 충돌 방지
    # __file__은 현재 스크립트(settings_manager.py)의 경로
    # 테스트 시에는 이 파일이 있는 디렉토리의 부모 디렉토리(test_code)에 생성되도록 경로 조정
    current_dir = os.path.dirname(os.path.abspath(__file__))
    test_code_dir = os.path.dirname(current_dir) # core의 부모 -> test_code
    test_config_filename_only = "test_settings_manager_core.json"
    test_config_fullpath = os.path.join(test_code_dir, test_config_filename_only)


    # 1. config_file_path를 명시적으로 전달하는 경우 테스트
    print(f"\n--- 테스트 1: config_file_path 명시적 전달 ({test_config_fullpath}) ---")
    manager_with_path = SettingsManager(config_file_path=test_config_fullpath)
    print(f"Manager_with_path.config_file_path: {manager_with_path.config_file_path}")
    assert manager_with_path.config_file_path == test_config_fullpath
    if os.path.exists(test_config_fullpath):
        os.remove(test_config_fullpath)
    settings1 = manager_with_path.load_settings() # 파일 없으면 기본값 로드 및 생성
    print("초기 로드 (파일 생성됨):", settings1)
    assert os.path.exists(test_config_fullpath) # 파일 생성 확인
    manager_with_path.save_settings({"chip_id": "0xTEST"})
    reloaded1 = manager_with_path.load_settings()
    print("저장 후 로드:", reloaded1)
    assert reloaded1.get("chip_id") == "0xTEST"
    if os.path.exists(test_config_fullpath):
        os.remove(test_config_fullpath)
        print(f"테스트 파일 '{test_config_fullpath}' 삭제 완료.")


    # 2. config_file_path를 전달하지 않고, config_file_name만 사용하는 경우 테스트
    #    (이 경우 _determine_config_path 로직에 따라 경로 결정)
    print(f"\n--- 테스트 2: config_file_name만 사용 (기본 경로 결정) ---")
    manager_default_path = SettingsManager(config_file_name="default_test_config.json")
    print(f"Manager_default_path.config_file_path: {manager_default_path.config_file_path}")
    # _determine_config_path의 첫 번째 옵션(문서 폴더)이 성공하면 해당 경로, 아니면 두 번째 옵션(test_code 폴더)
    # 테스트 환경에 따라 경로가 달라질 수 있으므로, 경로 자체를 assert 하기는 어려움.
    # 파일 생성 및 로드/저장 기능만 확인
    if os.path.exists(manager_default_path.config_file_path):
        os.remove(manager_default_path.config_file_path)
    settings2 = manager_default_path.load_settings()
    print("기본 경로로 로드 (파일 생성됨):", settings2)
    assert os.path.exists(manager_default_path.config_file_path)
    manager_default_path.save_settings({"sourcemeter_use": True})
    reloaded2 = manager_default_path.load_settings()
    print("저장 후 로드:", reloaded2)
    assert reloaded2.get("sourcemeter_use") is True
    if os.path.exists(manager_default_path.config_file_path):
        os.remove(manager_default_path.config_file_path)
        print(f"테스트 파일 '{manager_default_path.config_file_path}' 삭제 완료.")


    # 기존 테스트 코드 (사용자 제공 코드 기반으로 일부 수정)
    print("\n--- 기존 테스트 로직 (사용자 제공 코드 기반) ---")
    manager = SettingsManager(config_file_name=test_config_filename_only) # test_code 폴더에 생성되도록
    # 이제 manager.config_file_path는 _determine_config_path()에 의해 결정된 경로를 가짐
    # (옵션2에 의해 test_code/test_settings_manager_core.json 이 될 것임)
    
    print(f"Manager.config_file_path (기존 테스트용): {manager.config_file_path}")


    print("\n--- 초기 설정 로드 (파일 없을 시) ---")
    if os.path.exists(manager.config_file_path): # manager.config_file_path 사용
        os.remove(manager.config_file_path)
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
    # save_settings에서 default_settings와 병합하므로, error_halts_sequence는 기본값 False가 유지되어야 함
    # (partial_settings에 error_halts_sequence가 없으므로 default_settings의 값이 사용됨)
    assert reloaded_partial.get("error_halts_sequence") == manager.default_settings["error_halts_sequence"]

    print("\n--- 잘못된 JSON 파일 로드 테스트 ---")
    with open(manager.config_file_path, 'w', encoding='utf-8') as f: # manager.config_file_path 사용
        f.write("{corrupted_json: ")
    corrupted_settings = manager.load_settings()
    print("손상된 파일 로드 시 설정:", corrupted_settings)
    assert corrupted_settings == manager.default_settings

    if os.path.exists(manager.config_file_path): # manager.config_file_path 사용
        os.remove(manager.config_file_path)
        print(f"\n테스트용 설정 파일 '{manager.config_file_path}' 삭제 완료.")