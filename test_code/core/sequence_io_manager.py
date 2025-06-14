# sequence_io_manager.py
import json
import os
from typing import List, Dict, Optional, Union
from . import constants
from datetime import datetime
from .data_models import SequenceItem, SimpleActionItem, LoopActionItem

class SequenceIOManager:
    """
    테스트 시퀀스를 파일 시스템에 저장하고 불러오는 기능을 관리하는 클래스입니다.
    """

    def __init__(self, sequences_dir: str):
        self.sequences_dir = sequences_dir
        if not os.path.exists(self.sequences_dir):
            try:
                os.makedirs(self.sequences_dir, exist_ok=True)
                print(f"[SequenceIOManager] Created sequences directory: {self.sequences_dir}")
            except Exception as e:
                # 디렉토리 생성 실패 시, 애플리케이션 레벨에서 처리하거나, 여기서 에러를 발생시켜야 할 수 있습니다.
                # 여기서는 일단 경고만 출력하고, 실제 파일 작업 시 오류가 발생할 수 있음을 인지합니다.
                print(f"[SequenceIOManager] CRITICAL: Failed to create sequences directory '{self.sequences_dir}': {e}")
                # raise OSError(f"Failed to create sequences directory: {self.sequences_dir}") from e # 필요시 예외 발생

    def save_sequence(self, sequence_name_no_ext: str, sequence_items: List[SequenceItem], overwrite: bool = False) -> bool:
        """
        시퀀스 파일을 JSON 형태로 저장합니다.
        JSON 파일에는 시퀀스 이름, 저장 시각, 그리고 계층적인 시퀀스 아이템들이 포함됩니다.
        
        Args:
            sequence_name_no_ext (str): 저장할 시퀀스의 순수 이름 (확장자 제외).
            sequence_items (List[SequenceItem]): 시퀀스 아이템 목록 (계층 구조 지원).
            overwrite (bool): 동일한 이름의 파일이 있을 경우 덮어쓸지 여부.
            
        Returns:
            bool: 저장 성공 여부.
        """
        if not sequence_name_no_ext or not sequence_name_no_ext.strip():
            print(f"[SequenceIOManager] Error: Sequence name cannot be empty.")
            return False
        
        # Ensure the sequences directory exists, try to create it if not (might be redundant if __init__ handles it well)
        if not os.path.exists(self.sequences_dir):
            try:
                os.makedirs(self.sequences_dir, exist_ok=True)
                print(f"[SequenceIOManager] Created directory during save: {self.sequences_dir}")
            except Exception as e:
                print(f"[SequenceIOManager] Error creating directory during save '{self.sequences_dir}': {e}")
                return False
                
        filename_with_ext = sequence_name_no_ext + constants.SEQUENCE_FILE_EXTENSION
        filepath = os.path.join(self.sequences_dir, filename_with_ext)
        
        if os.path.exists(filepath) and not overwrite:
            print(f"[SequenceIOManager] File '{filepath}' already exists and overwrite is False.")
            return False
            
        try:
            sequence_data = {
                "name": sequence_name_no_ext, # Store the pure name inside JSON
                "saved_at": datetime.now().isoformat(),
                "sequence_items": sequence_items # 기존 sequence_lines 대신 sequence_items 사용
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(sequence_data, f, indent=2, ensure_ascii=False)
                
            print(f"[SequenceIOManager] Sequence successfully saved to '{filepath}'")
            return True
            
        except Exception as e:
            print(f"[SequenceIOManager] Error saving sequence '{sequence_name_no_ext}' to '{filepath}': {e}")
            return False

    @staticmethod
    def load_sequence(filepath: str) -> Optional[List[SequenceItem]]:
        """
        JSON 파일에서 계층적인 시퀀스 아이템 리스트("sequence_items")를 로드합니다.
        """
        print(f"[SequenceIOManager] Attempting to load sequence from: {filepath}") # 로드 시도 경로 로깅
        if not os.path.exists(filepath):
            print(f"[SequenceIOManager] Error loading: File not found '{filepath}'")
            return None
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"[SequenceIOManager] Successfully parsed JSON from '{filepath}'. Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")

            # "sequence_items" 키를 우선적으로 확인
            if "sequence_items" in data and isinstance(data["sequence_items"], list):
                # TODO: 여기서 각 아이템이 SimpleActionItem 또는 LoopActionItem 구조를 따르는지
                #       세부적인 유효성 검사를 추가할 수 있습니다 (예: pydantic 사용).
                #       현재는 타입 캐스팅 없이 반환합니다.
                print(f"[SequenceIOManager] Sequence items loaded successfully from '{filepath}' using 'sequence_items' key.")
                return data["sequence_items"]
            elif "sequence_lines" in data and isinstance(data["sequence_lines"], list):
                # 하위 호환성을 위해 기존 "sequence_lines" (List[str]) 처리
                # 이 문자열 리스트를 List[SimpleActionItem]으로 변환해야 함.
                print(f"[SequenceIOManager] Legacy sequence (sequence_lines) loaded from '{filepath}'. Converting...")
                legacy_lines: List[str] = data["sequence_lines"]
                converted_items: List[SequenceItem] = []
                for idx, line_str in enumerate(legacy_lines):
                    try:
                        action_type_str, params_str = line_str.split(":", 1)
                        params_dict_parsed = {}
                        if params_str.strip():
                            param_pairs = params_str.split(';')
                            for pair in param_pairs:
                                if '=' in pair: 
                                    key, value = pair.split('=', 1)
                                    params_dict_parsed[key.strip()] = value.strip()
                        
                        simple_item: SimpleActionItem = {
                            "item_id": f"legacy_item_{idx}_{datetime.now().timestamp()}", # 고유 ID 강화
                            "action_type": action_type_str.strip(),
                            "parameters": params_dict_parsed,
                            "display_name": line_str.strip() # 간단히 전체 라인을 표시명으로
                        }
                        converted_items.append(simple_item)
                    except ValueError as e_parse_line:
                        print(f"[SequenceIOManager] Error converting legacy line: '{line_str}'. Error: {e_parse_line}. Skipping.")
                        # 유효하지 않은 레거시 라인은 무시하거나, 오류 처리
                print(f"[SequenceIOManager] Converted {len(converted_items)} items from legacy 'sequence_lines'.")
                return converted_items
            elif "steps" in data and isinstance(data["steps"], list): # Legacy support for "steps"
                print(f"[SequenceIOManager] Legacy sequence (steps) loaded from '{filepath}'")
                # sequence_lines와 유사하게 SimpleActionItem으로 변환 필요
                # 이 부분은 위 sequence_lines 변환 로직과 거의 동일하게 구현 가능
                legacy_steps: List[str] = data["steps"]
                converted_steps: List[SequenceItem] = []
                # ... (위의 sequence_lines 변환 로직과 유사하게 구현) ...
                print(f"[SequenceIOManager] WARNING: Conversion for 'steps' key not fully implemented yet in this pass.")
                return converted_steps # 임시
            else:
                print(f"[SequenceIOManager] Error: '{filepath}' does not contain 'sequence_items' or 'sequence_lines'.")
                return None
        except json.JSONDecodeError as e:
            print(f"[SequenceIOManager] Error decoding JSON from '{filepath}': {e}")
            return None
        except IOError as e:
            print(f"[SequenceIOManager] IOError loading sequence from '{filepath}': {e}")
            return None
        except Exception as e:
            print(f"[SequenceIOManager] Unexpected error loading sequence from '{filepath}': {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc() # 전체 트레이스백 출력
            return None

    def get_saved_sequences(self) -> List[Dict[str, str]]: # Return type changed
        """
        지정된 디렉토리에서 모든 저장된 시퀀스 파일 정보를 읽어 리스트로 반환합니다.
        각 정보는 {"display_name": "표시용_이름", "path": "전체_파일_경로"} 형태의 딕셔너리입니다.
        표시용 이름은 JSON 내부의 "name" 필드를 우선 사용하고, 없으면 파일명에서 추출합니다.
        """
        saved_sequences_info = []
        if not os.path.isdir(self.sequences_dir):
            print(f"[SequenceIOManager] Saved sequences directory not found: '{self.sequences_dir}'")
            return saved_sequences_info
        
        print(f"[SequenceIOManager] Scanning for sequences in: {self.sequences_dir}")
        for filename in os.listdir(self.sequences_dir):
            if filename.endswith(constants.SEQUENCE_FILE_EXTENSION):
                filepath = os.path.join(self.sequences_dir, filename)
                display_name = filename[:-len(constants.SEQUENCE_FILE_EXTENSION)] # Default to filename
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if isinstance(data, dict) and "name" in data and isinstance(data["name"], str) and data["name"].strip():
                        display_name = data["name"].strip()
                        print(f"  Found sequence '{display_name}' (from JSON name) in '{filename}'")
                    else:
                        print(f"  Found sequence '{display_name}' (from filename) in '{filename}' - no valid 'name' field in JSON.")
                except Exception as e:
                    print(f"  Error reading or parsing JSON for '{filename}' to get display name: {e}. Using filename as display name.")
                
                saved_sequences_info.append({"display_name": display_name, "path": filepath})
        
        saved_sequences_info.sort(key=lambda x: x['display_name'].lower())
        print(f"[SequenceIOManager] Found {len(saved_sequences_info)} sequences.")
        return saved_sequences_info

    @staticmethod
    def delete_sequence(filepath: str) -> bool:
        """
        지정된 경로의 시퀀스 파일을 삭제합니다.

        Args:
            filepath (str): 삭제할 시퀀스 파일의 전체 경로.

        Returns:
            bool: 삭제 성공 시 True, 실패 시 False.
        """
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"Info: 시퀀스 파일 '{filepath}'이(가) 삭제되었습니다.")
                return True
            else:
                print(f"Warning: 삭제할 시퀀스 파일을 찾을 수 없습니다: '{filepath}'")
                return False
        except OSError as e:
            print(f"Error: 시퀀스 파일 삭제 중 OS 오류 발생 '{filepath}': {e}")
            return False
        except Exception as e:
            print(f"Error: 시퀀스 파일 삭제 중 예기치 않은 오류 발생 '{filepath}': {e}")
            return False

    @staticmethod
    def rename_sequence(old_filepath: str, new_name_without_ext: str, directory: str) -> Optional[str]:
        """
        기존 시퀀스 파일의 이름을 변경합니다.
        파일 시스템 상의 파일 이름만 변경합니다.

        Args:
            old_filepath (str): 변경할 기존 시퀀스 파일의 전체 경로.
            new_name_without_ext (str): 새 시퀀스 이름 (확장자 제외).
            directory (str): 시퀀스 파일이 저장된 디렉토리 경로.

        Returns:
            Optional[str]: 성공 시 새로운 전체 파일 경로, 실패 시 None.
        """
        if not os.path.exists(old_filepath):
            print(f"Error: 이름을 변경할 시퀀스 파일을 찾을 수 없습니다: '{old_filepath}'")
            return None
        
        new_filename = new_name_without_ext + constants.SEQUENCE_FILE_EXTENSION
        new_filepath = os.path.join(directory, new_filename)

        if os.path.exists(new_filepath):
            print(f"Error: 이미 동일한 이름의 시퀀스 파일이 존재합니다: '{new_filepath}'")
            return None
        
        try:
            os.rename(old_filepath, new_filepath)
            print(f"Info: 시퀀스 파일 이름이 '{os.path.basename(old_filepath)}'에서 '{new_filename}'(으)로 변경되었습니다.")
            return new_filepath
        except OSError as e:
            print(f"Error: 시퀀스 파일 이름 변경 중 OS 오류 발생: {e}")
            return None
        except Exception as e:
            print(f"Error: 시퀀스 파일 이름 변경 중 예기치 않은 오류 발생: {e}")
            return None

if __name__ == '__main__':
    # --- 테스트 코드 ---
    # constants.py에 필요한 상수가 정의되어 있다고 가정
    if not hasattr(constants, 'SEQUENCE_FILE_EXTENSION'):
        constants.SEQUENCE_FILE_EXTENSION = ".seq.json" # 테스트용 임시 정의
    if not hasattr(constants, 'SAVED_SEQUENCES_DIR_NAME'):
        constants.SAVED_SEQUENCES_DIR_NAME = "test_sequences_dir" # 테스트용 임시 정의

    test_dir = constants.SAVED_SEQUENCES_DIR_NAME
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)

    io_manager = SequenceIOManager(test_dir)

    # 1. 시퀀스 저장 테스트
    print("\n--- 시퀀스 저장 테스트 ---")
    seq_items1 = ["I2C_W_NAME: NAME=CTRL_REG; VAL=0xFF", "DELAY_S: SEC=0.1"]
    seq_items2 = ["SM_SET_V: VAL=1.2; TERM=FRONT", "SM_MEAS_I: VAR=I_out; TERM=FRONT"]
    
    save_path1 = os.path.join(test_dir, "TestSeq1" + constants.SEQUENCE_FILE_EXTENSION)
    save_path2 = os.path.join(test_dir, "AnotherSeq" + constants.SEQUENCE_FILE_EXTENSION)

    io_manager.save_sequence("TestSeq1", seq_items1)
    io_manager.save_sequence("AnotherSeq", seq_items2)

    # 2. 저장된 시퀀스 목록 조회 테스트
    print("\n--- 저장된 시퀀스 목록 조회 테스트 ---")
    saved_list = io_manager.get_saved_sequences()
    print(f"저장된 시퀀스: {saved_list}")
    assert len(saved_list) >= 2 # 위에서 2개 저장했으므로

    # 3. 시퀀스 로드 테스트
    print("\n--- 시퀀스 로드 테스트 ---")
    loaded_items1 = io_manager.load_sequence(save_path1)
    if loaded_items1:
        print(f"'{save_path1}' 로드 결과: {loaded_items1}")
        assert loaded_items1 == seq_items1
    else:
        print(f"'{save_path1}' 로드 실패")

    non_exist_path = os.path.join(test_dir, "NonExist" + constants.SEQUENCE_FILE_EXTENSION)
    loaded_non_exist = io_manager.load_sequence(non_exist_path)
    assert loaded_non_exist is None

    # 4. 시퀀스 이름 변경 테스트
    print("\n--- 시퀀스 이름 변경 테스트 ---")
    if saved_list:
        path_to_rename = saved_list[0]['path']
        original_name = saved_list[0]['display_name']
        new_name = original_name + "_Renamed"
        
        renamed_path = io_manager.rename_sequence(path_to_rename, new_name, test_dir)
        if renamed_path:
            print(f"'{original_name}' -> '{new_name}' 변경 성공. 새 경로: {renamed_path}")
            assert os.path.exists(renamed_path)
            assert not os.path.exists(path_to_rename) # 이전 파일은 없어야 함
            
            # 변경된 이름으로 목록 다시 조회
            updated_list = io_manager.get_saved_sequences()
            assert any(item['display_name'] == new_name for item in updated_list)
            
            # 테스트 편의를 위해 원래 이름으로 복원 (다음 테스트를 위해)
            # io_manager.rename_sequence(renamed_path, original_name, test_dir)
        else:
            print(f"'{original_name}' 이름 변경 실패.")
    
    # 5. 시퀀스 삭제 테스트
    print("\n--- 시퀀스 삭제 테스트 ---")
    # 삭제할 파일 경로를 다시 가져옴 (이름 변경 테스트에서 경로가 바뀔 수 있으므로)
    current_saved_list = io_manager.get_saved_sequences()
    if current_saved_list:
        path_to_delete = current_saved_list[0]['path']
        name_to_delete = current_saved_list[0]['display_name']
        delete_success = io_manager.delete_sequence(path_to_delete)
        if delete_success:
            print(f"'{name_to_delete}' 삭제 성공.")
            assert not os.path.exists(path_to_delete)
            # 삭제 후 목록 다시 조회
            final_list = io_manager.get_saved_sequences()
            assert not any(item['display_name'] == name_to_delete for item in final_list)
        else:
            print(f"'{name_to_delete}' 삭제 실패.")

    # 테스트 후 생성된 디렉토리 및 파일 정리 (선택 사항)
    try:
        for item in os.listdir(test_dir):
            item_path = os.path.join(test_dir, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
        os.rmdir(test_dir)
        print(f"\n테스트 디렉토리 '{test_dir}' 및 내용 삭제 완료.")
    except Exception as e:
        print(f"테스트 디렉토리 정리 중 오류: {e}")