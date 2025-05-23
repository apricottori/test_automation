# core/register_map_backend.py
import json
import re
import os
from typing import List, Tuple, Dict, Any, Optional

# --- 수정된 임포트 경로 ---
# core 패키지 내의 다른 모듈들을 임포트합니다.
from .data_models import LogicalFieldInfo, AddressBitMapping
from .helpers import normalize_hex_input, map_access_to_type
from . import constants # constants도 core 패키지에서 가져옴

class RegisterMap:
    def __init__(self):
        self.metadata: Dict[str, Any] = {}
        self.logical_fields_map: Dict[str, LogicalFieldInfo] = {}
        # address_layout: 각 8비트 주소(str, "0xFFFF")에 어떤 필드의 어떤 부분이 매핑되는지 리스트로 저장
        self.address_layout: Dict[str, List[AddressBitMapping]] = {}
        # initial_address_values: 각 8비트 주소의 초기값 (int)
        self.initial_address_values: Dict[str, int] = {}
        # current_address_values: 각 8비트 주소의 현재값 (int), UI나 REGA 파일에 의해 변경될 수 있음
        self.current_address_values: Dict[str, int] = {}

        self._bits_per_address: int = constants.BITS_PER_ADDRESS
        self._min_addr_int: int = 0
        self._max_addr_int: int = 0xFFFF # Default max address
        self._json_big_endian_flag: bool = False # JSON 파일의 "bigEndian" 필드 값

    def load_from_json_file(self, json_path: str) -> Tuple[bool, Optional[List[str]]]:
        """
        JSON 레지스터 맵 파일을 로드하고 파싱하여 내부 데이터 구조를 채웁니다.
        성공 시 (True, None)을 반환하고, 실패 시 (False, 오류_메시지_목록)을 반환합니다.
        """
        parsing_errors: List[str] = [] # 파싱 오류 메시지 저장

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            return False, [f"JSON file '{json_path}' not found."]
        except json.JSONDecodeError as e:
            return False, [f"Could not decode JSON from '{json_path}'. Details: {e}"]
        except Exception as e:
            return False, [f"An unexpected error occurred while opening/reading JSON file '{json_path}': {e}"]

        # Reset internal state
        self.metadata.clear()
        self.logical_fields_map.clear()
        self.address_layout.clear()
        self.initial_address_values.clear()
        self.current_address_values.clear()

        self.metadata = {k: v for k, v in data.items() if k != "registerBlocks"}
        self._json_big_endian_flag = self.metadata.get("bigEndian", False)

        try:
            min_addr_str = str(self.metadata.get("minAddress", "0x0"))
            max_addr_str = str(self.metadata.get("maxAddress", f"0x{self._max_addr_int:04X}"))
            norm_min_addr = normalize_hex_input(min_addr_str, add_prefix=True)
            norm_max_addr = normalize_hex_input(max_addr_str, add_prefix=True)

            if norm_min_addr is None or norm_max_addr is None:
                # 이 경우는 normalize_hex_input에서 None을 반환한 경우로, helpers.py의 로직에 따라
                # 입력이 None이거나, 빈 문자열이거나, 유효하지 않은 hex 문자를 포함한 경우임.
                raise ValueError(f"minAddress ('{min_addr_str}') or maxAddress ('{max_addr_str}') has invalid hex format.")

            self._min_addr_int = int(norm_min_addr, 16)
            self._max_addr_int = int(norm_max_addr, 16)

            if self._min_addr_int > self._max_addr_int:
                parsing_errors.append(f"Warning: minAddress ({min_addr_str}) is greater than maxAddress ({max_addr_str}). Swapping them.")
                self._min_addr_int, self._max_addr_int = self._max_addr_int, self._min_addr_int
        except ValueError as e:
            parsing_errors.append(f"Error: Could not parse minAddress or maxAddress from JSON metadata. Using defaults. Error: {e}")
            self._min_addr_int = 0
            self._max_addr_int = 0xFFFF
        
        if "registerBlocks" not in data or not isinstance(data["registerBlocks"], list):
            parsing_errors.append("Warning: 'registerBlocks' not found or not a list in JSON. No registers will be loaded.")
            if parsing_errors: return False, parsing_errors # 다른 오류가 이미 있거나, 이것이 치명적이라면 실패로 간주

        for block in data.get("registerBlocks", []):
            if not isinstance(block.get("registers"), list):
                parsing_errors.append(f"Warning: 'registers' in block '{block.get('id', 'Unknown Block')}' is not a list. Skipping.")
                continue

            for reg_data in block.get("registers", []):
                if not isinstance(reg_data, dict) or "id" not in reg_data:
                    parsing_errors.append(f"Warning: Invalid register data format or missing 'id' in block. Skipping register: {reg_data}")
                    continue

                field_id = str(reg_data["id"])
                try:
                    total_length = int(reg_data.get("length", 0))
                except (ValueError, TypeError):
                    parsing_errors.append(f"Warning: Field '{field_id}': Invalid 'length' value '{reg_data.get('length')}'. Defaulting to 0, field may be skipped.")
                    total_length = 0 # 오류 처리 후 계속 진행하거나, 여기서 continue로 필드 스킵 가능

                if total_length <= 0:
                    continue # 0 또는 음수 길이 필드는 처리하지 않음

                initial_val_int = 0
                reset_val_str = reg_data.get("resetValue")
                if reset_val_str is not None and str(reset_val_str).strip():
                    norm_reset_val = normalize_hex_input(str(reset_val_str))
                    if norm_reset_val:
                        try:
                            initial_val_int = int(norm_reset_val, 16)
                        except ValueError:
                            parsing_errors.append(f"Warning: Field '{field_id}': Could not parse resetValue '{reset_val_str}' as hex. Defaulting to 0.")
                            initial_val_int = 0
                    else:
                        parsing_errors.append(f"Warning: Field '{field_id}': Invalid format for resetValue '{reset_val_str}'. Defaulting to 0.")
                        initial_val_int = 0
                
                # description 필드 파싱
                description_str = reg_data.get("description", None) # None 또는 문자열

                regions_mapping_list: List[Tuple[str, int, int, int, int]] = []
                raw_regions = reg_data.get("regions", [])
                if not isinstance(raw_regions, list) or not raw_regions:
                    parsing_errors.append(f"Warning: Field '{field_id}' has no regions defined or regions is not a list. Skipping field.")
                    continue
                
                try:
                    sorted_regions_for_field_assembly = sorted(
                        raw_regions,
                        key=lambda r: (int(normalize_hex_input(str(r["address"]), add_prefix=True) or "0", 16), int(r.get("bitOffset",0)))
                    )
                except (KeyError, ValueError, TypeError) as e:
                    parsing_errors.append(f"Error: Field '{field_id}': Invalid region data for sorting. Error: {e}. Skipping field.")
                    continue

                field_bit_cursor_from_msb = total_length
                accumulated_region_width = 0

                for region in sorted_regions_for_field_assembly:
                    try:
                        addr_val_str = str(region["address"])
                        addr_hex_norm = normalize_hex_input(addr_val_str, 4, add_prefix=True)
                        if not addr_hex_norm:
                            parsing_errors.append(f"Warning: Field '{field_id}', Region Address '{addr_val_str}': Invalid format. Skipping region.")
                            continue
                        addr_hex = addr_hex_norm.upper()

                        local_offset = int(region["bitOffset"])
                        local_width = int(region["bitWidth"])
                        
                        if not (0 <= local_offset < self._bits_per_address and local_width > 0 and (local_offset + local_width) <= self._bits_per_address):
                            parsing_errors.append(f"Warning: Field '{field_id}', Address {addr_hex}: Invalid bitOffset/bitWidth ({local_offset}/{local_width}) for an {self._bits_per_address}-bit address. Skipping region.")
                            continue
                        
                        accumulated_region_width += local_width
                        
                        part_msb_in_field = field_bit_cursor_from_msb - 1
                        part_lsb_in_field = field_bit_cursor_from_msb - local_width

                        if part_lsb_in_field < 0:
                            parsing_errors.append(f"Error: Field '{field_id}' bit calculation error. Part LSB {part_lsb_in_field} < 0. Region: {region}.")
                            regions_mapping_list.clear() 
                            break 

                        regions_mapping_list.append(
                            (addr_hex, local_offset, local_width, part_lsb_in_field, part_msb_in_field)
                        )
                        field_bit_cursor_from_msb -= local_width
                    except (KeyError, ValueError, TypeError) as e:
                        parsing_errors.append(f"Error: Field '{field_id}', while processing Region {region}: Invalid data. Error: {e}. Skipping region.")
                        continue
                
                if not regions_mapping_list:
                    # parsing_errors에 이미 관련 메시지가 추가되었을 것이므로, 중복 추가 방지 가능
                    # parsing_errors.append(f"Warning: Field '{field_id}': No valid regions were mapped. Skipping field.")
                    continue

                if field_bit_cursor_from_msb != 0:
                    parsing_errors.append(f"Warning: Field '{field_id}' length mismatch. Declared: {total_length}, Processed from regions: {total_length - field_bit_cursor_from_msb}.")
                
                if accumulated_region_width != total_length:
                     parsing_errors.append(f"Warning: Field '{field_id}' total length ({total_length}) does not match sum of region bitWidths ({accumulated_region_width}).")

                regions_mapping_list.sort(key=lambda x: x[3]) # Sort by field_part_lsb_in_field
                
                display_name_length = total_length # JSON에 명시된 길이로 display name 구성
                if (total_length - field_bit_cursor_from_msb) != total_length and (total_length - field_bit_cursor_from_msb) > 0 :
                    # 만약 처리된 길이가 선언된 길이와 다르고 0보다 크다면, 처리된 길이를 사용할지 결정.
                    # 여기서는 일단 선언된 길이를 사용.
                    pass

                self.logical_fields_map[field_id] = LogicalFieldInfo(
                    id=field_id,
                    display_name=f"{field_id}<{display_name_length-1}:0>" if display_name_length > 1 else field_id,
                    access=map_access_to_type(reg_data.get("access")),
                    length=total_length,
                    global_lsb_index=0,
                    global_msb_index=total_length - 1 if total_length > 0 else 0,
                    initial_value_int=initial_val_int,
                    description=description_str, # 수정된 부분: description 추가
                    regions_mapping=regions_mapping_list
                )
        
        if not self.logical_fields_map and not parsing_errors:
            parsing_errors.append("Warning: No logical fields were successfully loaded from the JSON file, and no other parsing errors were detected.")

        if parsing_errors:
            return False, parsing_errors

        self._build_address_layout_and_initial_values()
        self.current_address_values = self.initial_address_values.copy()
        return True, None

    def _build_address_layout_and_initial_values(self):
        """
        Populates self.address_layout (mapping addresses to field parts)
        and self.initial_address_values (8-bit integer value for each address).
        """
        self.initial_address_values.clear()
        self.address_layout.clear()

        all_involved_addresses = set()
        for field_info in self.logical_fields_map.values():
            for addr_hex, _, _, _, _ in field_info['regions_mapping']:
                all_involved_addresses.add(addr_hex.upper())
        
        for addr_int in range(self._min_addr_int, self._max_addr_int + 1):
            all_involved_addresses.add(f"0X{addr_int:04X}")

        for addr_h in sorted(list(all_involved_addresses)): # 주소 순으로 처리
            self.initial_address_values[addr_h] = 0
            self.address_layout[addr_h] = []

        for field_id, field_info in self.logical_fields_map.items():
            field_initial_value = field_info['initial_value_int']
            field_total_length = field_info['length']

            for addr_hex, local_bit_offset, local_width, field_part_lsb, field_part_msb in field_info['regions_mapping']:
                addr_key = addr_hex.upper() 

                mask_for_field_part = ((1 << local_width) - 1)
                part_value_from_field = (field_initial_value >> field_part_lsb) & mask_for_field_part

                current_addr_val = self.initial_address_values.get(addr_key, 0)
                current_addr_val |= (part_value_from_field << local_bit_offset)
                self.initial_address_values[addr_key] = current_addr_val

                self.address_layout.setdefault(addr_key, []).append(AddressBitMapping(
                    field_id=field_id,
                    local_lsb=local_bit_offset,
                    local_msb=local_bit_offset + local_width - 1,
                    field_part_lsb_relative_to_field_lsb=field_part_lsb,
                    field_part_msb_relative_to_field_lsb=field_part_msb
                ))

        for addr_hex_key in self.address_layout:
            self.address_layout[addr_hex_key].sort(key=lambda x: x['local_lsb'])

    def apply_rega_updates(self, rega_path: str):
        """Parses a .rega file and updates self.current_address_values."""
        rega_updates_dict = self._parse_rega_to_updates_dict(rega_path)
        for addr_hex_rega, value_hex_str_rega in rega_updates_dict.items():
            addr_key = addr_hex_rega.upper() # Normalized address
            try:
                val_int = int(value_hex_str_rega, 16)
                if addr_key in self.current_address_values:
                    self.current_address_values[addr_key] = val_int
                else:
                    # If address from REGA is not in JSON map, it might be an error or intended.
                    # Current behavior: only update if address is known from JSON.
                    print(f"Warning: REGA - Address '{addr_key}' not in current map derived from JSON. Value not applied from REGA.")
            except ValueError:
                print(f"Warning: REGA - Invalid hex value '{value_hex_str_rega}' for address '{addr_key}'.")

    def _parse_rega_to_updates_dict(self, rega_path: str) -> Dict[str, str]:
        """Parses a .rega file into a dictionary {addr_hex_norm_upper: value_hex_norm_upper}."""
        updates: Dict[str, str] = {}
        try:
            with open(rega_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'): # Skip comments or empty lines
                        continue
                    
                    line_content = line.split('#', 1)[0].strip() # Remove inline comments
                    parts = re.split(r'\s+', line_content) # Split by whitespace

                    if len(parts) >= 2:
                        addr_str_raw = parts[0]
                        val_str_raw = parts[1]
                        
                        addr_str_norm = normalize_hex_input(addr_str_raw, 4) # Normalize to 4-char hex
                        val_str_norm = normalize_hex_input(val_str_raw, 2)   # Normalize to 2-char hex

                        if addr_str_norm and val_str_norm:
                            updates[addr_str_norm.upper()] = val_str_norm.upper()
                        else:
                            print(f"Warning: REGA file '{rega_path}', line {line_num}: Invalid address/value format '{line_content}'. Skipping.")
                    elif line_content: # Content exists but not in 2 parts
                        print(f"Warning: REGA file '{rega_path}', line {line_num}: Invalid line format '{line_content}'. Skipping.")

        except FileNotFoundError:
            print(f"Info: REGA file '{rega_path}' not found. No updates applied.")
        except Exception as e:
            print(f"Error processing REGA file '{rega_path}': {e}")
        return updates

    def get_logical_field_value(self, field_id: str, from_initial: bool = False) -> int:
        """Returns the current (or initial) integer value of the specified logical field."""
        if field_id not in self.logical_fields_map:
            raise ValueError(f"Field ID '{field_id}' not found in logical_fields_map.")

        field_info = self.logical_fields_map[field_id]
        source_values = self.initial_address_values if from_initial else self.current_address_values

        field_value_int = 0
        for addr_hex, local_bit_offset, local_width, field_part_lsb, _ in field_info['regions_mapping']:
            addr_key = addr_hex.upper()
            addr_byte_val = source_values.get(addr_key, 0) # If address not found (should not happen for loaded fields), assume 0
            if addr_key not in source_values: # Should ideally not happen if map is consistent
                 print(f"Warning: Address '{addr_key}' for field '{field_id}' not found in {'initial' if from_initial else 'current'} values. Assuming 0 for this part.")

            mask_for_local_part = ((1 << local_width) - 1)
            local_part_val = (addr_byte_val >> local_bit_offset) & mask_for_local_part
            field_value_int |= (local_part_val << field_part_lsb)
        
        field_mask = (1 << field_info['length']) - 1 if field_info['length'] > 0 else 0
        return field_value_int & field_mask


    def get_logical_field_value_hex(self, field_id: str, from_initial: bool = False) -> str:
        """Returns the current (or initial) value of the logical field as a hex string."""
        try:
            field_info = self.logical_fields_map.get(field_id)
            if not field_info:
                return constants.HEX_ERROR_NO_FIELD

            value_int = self.get_logical_field_value(field_id, from_initial)
            num_hex_digits = (field_info['length'] + 3) // 4 if field_info['length'] > 0 else 1
            return f"0x{value_int:0{num_hex_digits}X}"
        except ValueError: 
            return constants.HEX_ERROR_NO_FIELD
        except Exception: 
            return constants.HEX_ERROR_CONVERSION


    def set_logical_field_value(self, field_id: str, value_to_set_int: int) -> Tuple[List[Tuple[str, int]], Dict[str, int]]:
        """
        Calculates the I2C operations needed to set a logical field's value and
        the resulting address values if all operations succeed.
        This method DOES NOT modify self.current_address_values directly.

        Args:
            field_id (str): The ID of the logical field to set.
            value_to_set_int (int): The integer value to set the field to.

        Returns:
            Tuple[List[Tuple[str, int]], Dict[str, int]]:
                - A list of (address_hex_str, new_8bit_value_int) tuples for I2C writes.
                - A dictionary {address_hex_str: new_8bit_value_int} of addresses and their
                  new values, to be confirmed and applied to current_address_values upon
                  successful I2C operations.
        """
        if field_id not in self.logical_fields_map:
            raise ValueError(f"Field ID '{field_id}' not found for setting value.")

        field_info = self.logical_fields_map[field_id]
        field_mask = (1 << field_info['length']) - 1 if field_info['length'] > 0 else 0
        value_to_set_int &= field_mask # Ensure value fits within field length

        # Create a temporary copy of current values to calculate prospective changes
        prospective_address_values = self.current_address_values.copy()
        
        # Apply changes for this field to the prospective values
        for addr_hex, local_offset, local_width, field_part_lsb, _ in field_info['regions_mapping']:
            addr_key = addr_hex.upper()

            # Extract the part of the field's new value that corresponds to this region
            part_val_for_region = (value_to_set_int >> field_part_lsb) & ((1 << local_width) - 1)

            current_byte_val_at_addr = prospective_address_values.get(addr_key, 0)
            if addr_key not in prospective_address_values: # Should not happen if map is consistent
                 print(f"Warning: Address '{addr_key}' for field '{field_id}' not found in current values during prospective set. Assuming 0 for this address.")

            # Clear the bits for this field part in the current byte value
            byte_clear_mask = ~(((1 << local_width) - 1) << local_offset)
            modified_byte_val = current_byte_val_at_addr & byte_clear_mask

            # Set the new field part value into the byte
            modified_byte_val |= (part_val_for_region << local_offset)

            prospective_address_values[addr_key] = modified_byte_val
        
        i2c_ops_to_perform: List[Tuple[str, int]] = []
        values_to_confirm: Dict[str, int] = {}

        # Identify which addresses actually changed and need I2C writes
        related_addresses_for_field = {region_addr.upper() for region_addr,_,_,_,_ in field_info['regions_mapping']}

        for addr_k_norm, prospective_new_val_int in prospective_address_values.items():
            # Only consider addresses related to the current field for I2C ops triggered by this field set
            if addr_k_norm in related_addresses_for_field:
                original_val_int = self.current_address_values.get(addr_k_norm) # Can be None if addr_k_norm was not in current_address_values initially
                
                # If the value at this address has changed compared to the current state
                if original_val_int != prospective_new_val_int:
                    i2c_ops_to_perform.append((addr_k_norm, prospective_new_val_int))
                    values_to_confirm[addr_k_norm] = prospective_new_val_int
        
        return i2c_ops_to_perform, values_to_confirm


    def set_address_byte_value(self, addr_hex_to_set: str, byte_value_int: int) -> Tuple[List[Tuple[str, int]], Dict[str, int]]:
        """
        Calculates the I2C operation for directly setting an address's byte value and
        the resulting address value if the operation succeeds.
        This method DOES NOT modify self.current_address_values directly.

        Args:
            addr_hex_to_set (str): The hex string of the address to set.
            byte_value_int (int): The 8-bit integer value to set.

        Returns:
            Tuple[List[Tuple[str, int]], Dict[str, int]]:
                - A list containing a single (address_hex_str, new_8bit_value_int) tuple if
                  the value changes, or an empty list.
                - A dictionary {address_hex_str: new_8bit_value_int} if the value changes,
                  or an empty dictionary.
        """
        norm_addr = normalize_hex_input(addr_hex_to_set, 4, add_prefix=True)
        if norm_addr is None:
            raise ValueError(f"Invalid address format for set_address_byte_value: {addr_hex_to_set}")

        addr_key = norm_addr.upper()
        prospective_new_val = byte_value_int & 0xFF # Ensure it's a byte

        i2c_ops_to_perform: List[Tuple[str, int]] = []
        values_to_confirm: Dict[str, int] = {}

        original_val = self.current_address_values.get(addr_key) # Can be None
        
        # Only generate op and confirm value if the new value is different from current
        if original_val != prospective_new_val:
            i2c_ops_to_perform.append((addr_key, prospective_new_val))
            values_to_confirm[addr_key] = prospective_new_val
        
        return i2c_ops_to_perform, values_to_confirm

    def confirm_address_values_update(self, updated_values: Dict[str, int]):
        """
        Called externally (e.g., by SequencePlayer) after successful I2C writes
        to actually update the RegisterMap's current_address_values.

        Args:
            updated_values (Dict[str, int]): A dictionary of {address_hex_str: new_8bit_value_int}
                                              containing only the addresses and values that were
                                              successfully written to hardware.
        """
        for addr_key, new_val in updated_values.items():
            # Ensure address key is normalized for consistency, though it should be already
            norm_addr_key = normalize_hex_input(addr_key, 4, add_prefix=True)
            if norm_addr_key: 
                 self.current_address_values[norm_addr_key.upper()] = new_val & 0xFF # Ensure byte value
            else:
                # This case should ideally not be reached if inputs are validated upstream
                print(f"Warning (confirm_update): Invalid address format '{addr_key}' received. Skipping update for this address.")
        # For debugging:
        # print(f"Debug: RegisterMap current_address_values confirmed update with: {updated_values}")


    def get_all_field_ids(self) -> List[str]:
        """Returns a sorted list of all logical field IDs."""
        return sorted(list(self.logical_fields_map.keys()))

    def get_all_logical_fields_info(self) -> List[LogicalFieldInfo]:
        """Returns a list of all LogicalFieldInfo objects."""
        return list(self.logical_fields_map.values())

    def get_address_range_hex(self) -> Tuple[str, str]:
        """Returns the min/max address range from JSON metadata as hex strings."""
        return f"0X{self._min_addr_int:04X}", f"0X{self._max_addr_int:04X}"

# Example usage (for testing this module directly)
if __name__ == '__main__':
    # Ensure constants are available for the test, assuming this script
    # might be run in a way that `from core import constants` works.
    # If running `python core/register_map_backend.py`, this should be fine.
    
    # Fallback for constants if direct execution fails to find `core` package
    # This is primarily for making the __main__ block runnable in isolation if needed,
    # but in a proper package structure, direct script execution like this is less common.
    try:
        from core import constants as test_constants
    except ImportError:
        class MockConstants: # Define minimal constants for testing
            BITS_PER_ADDRESS = 8
            HEX_ERROR_NO_FIELD = "0xERR_NF" # Changed from ERR_FIELD for consistency
            HEX_ERROR_CONVERSION = "0xERR_CV"
        test_constants = MockConstants()
        # Also mock helpers if needed, or ensure they don't rely on constants not defined here
        print("Warning: Using MockConstants for __main__ test as 'core' package might not be in PYTHONPATH.")


    reg_map_instance = RegisterMap()
    
    # Test JSON data
    sample_json_content_ok = {
        "minAddress": "0x0000", "maxAddress": "0x000F",
        "registerBlocks": [{
            "id": "block1", "registers": [
                {"id": "CTRL_REG", "length": 8, "resetValue": "0xAB", "access": "read-write", "description": "Control Register", "regions": [{"address": "0x0000", "bitOffset": 0, "bitWidth": 8}]},
                {"id": "MULTI_BYTE_FIELD", "length": 12, "resetValue": "0xABC", "access": "read-write", "description": "Multi-byte field example", "regions": [
                    {"address": "0x0002", "bitOffset": 0, "bitWidth": 8}, # Field MSB part
                    {"address": "0x0003", "bitOffset": 4, "bitWidth": 4}  # Field LSB part (at upper nibble of 0x0003)
                ]}
            ]
        }]
    }
    test_json_path = "test_regmap_backend_core.json" # Use a distinct name
    with open(test_json_path, 'w') as f: json.dump(sample_json_content_ok, f)

    print(f"--- Loading from '{test_json_path}' ---")
    load_success_ok, errors_ok = reg_map_instance.load_from_json_file(test_json_path)
    print(f"Load successful: {load_success_ok}, Errors: {errors_ok}")
    assert load_success_ok
    assert errors_ok is None

    if load_success_ok:
        print("\n--- Initial Address Values (after OK load) ---")
        # Expected: 0x0000: 0xAB, 0x0002: 0xAB, 0x0003: 0xC0
        assert reg_map_instance.initial_address_values.get("0X0000") == 0xAB
        assert reg_map_instance.initial_address_values.get("0X0002") == 0xAB
        assert reg_map_instance.initial_address_values.get("0X0003") == 0xC0 
        print(f"0X0000: 0x{reg_map_instance.initial_address_values.get('0X0000',0):02X}")
        print(f"0X0002: 0x{reg_map_instance.initial_address_values.get('0X0002',0):02X}")
        print(f"0X0003: 0x{reg_map_instance.initial_address_values.get('0X0003',0):02X}")


        print("\n--- Getting Field Values (Initial, from current_address_values which is a copy) ---")
        print(f"CTRL_REG: {reg_map_instance.get_logical_field_value_hex('CTRL_REG')}") # Should be 0xAB
        print(f"MULTI_BYTE_FIELD: {reg_map_instance.get_logical_field_value_hex('MULTI_BYTE_FIELD')}") # Should be 0xABC
        assert reg_map_instance.get_logical_field_value('CTRL_REG') == 0xAB
        assert reg_map_instance.get_logical_field_value('MULTI_BYTE_FIELD') == 0xABC
        assert reg_map_instance.logical_fields_map['CTRL_REG']['description'] == "Control Register"


        print("\n--- Setting Field Value 'CTRL_REG' to 0x55 (Prospective) ---")
        i2c_ops, vals_to_confirm = reg_map_instance.set_logical_field_value('CTRL_REG', 0x55)
        print(f"  I2C Operations needed: {i2c_ops}")
        print(f"  Values to confirm on success: {vals_to_confirm}")
        print(f"  CTRL_REG value (before confirm): {reg_map_instance.get_logical_field_value_hex('CTRL_REG')}")
        assert reg_map_instance.get_logical_field_value('CTRL_REG') == 0xAB # Still initial
        assert i2c_ops == [("0X0000", 0x55)]
        assert vals_to_confirm == {"0X0000": 0x55}
        
        print("--- Confirming update for CTRL_REG=0x55 ---")
        reg_map_instance.confirm_address_values_update(vals_to_confirm)
        print(f"  New CTRL_REG value (after confirm): {reg_map_instance.get_logical_field_value_hex('CTRL_REG')}")
        assert reg_map_instance.get_logical_field_value('CTRL_REG') == 0x55

        print("\n--- Setting Field Value 'MULTI_BYTE_FIELD' to 0x123 (Prospective) ---")
        # Initial MULTI_BYTE_FIELD is 0xABC (0x0002=0xAB, 0x0003=0xC0)
        # New value 0x123 (0x0002=0x12, 0x0003=0x30)
        i2c_ops_multi, vals_to_confirm_multi = reg_map_instance.set_logical_field_value('MULTI_BYTE_FIELD', 0x123)
        print(f"  I2C Operations for MULTI_BYTE_FIELD=0x123: {i2c_ops_multi}")
        print(f"  Values to confirm: {vals_to_confirm_multi}")
        assert reg_map_instance.get_logical_field_value('MULTI_BYTE_FIELD') == 0xABC # Still initial
        
        # Expected I2C ops: 0x0002 changes from 0xAB to 0x12, 0x0003 changes from 0xC0 to 0x30
        expected_i2c_ops_multi_dict = {"0X0002": 0x12, "0X0003": 0x30}
        assert len(i2c_ops_multi) == 2
        for op_addr, op_val in i2c_ops_multi:
            assert expected_i2c_ops_multi_dict[op_addr] == op_val
        assert vals_to_confirm_multi == expected_i2c_ops_multi_dict

        print("--- Confirming update for MULTI_BYTE_FIELD=0x123 ---")
        reg_map_instance.confirm_address_values_update(vals_to_confirm_multi)
        print(f"  New MULTI_BYTE_FIELD value: {reg_map_instance.get_logical_field_value_hex('MULTI_BYTE_FIELD')}")
        assert reg_map_instance.get_logical_field_value('MULTI_BYTE_FIELD') == 0x123
        assert reg_map_instance.current_address_values.get("0X0002") == 0x12
        assert reg_map_instance.current_address_values.get("0X0003") == 0x30

    if os.path.exists(test_json_path): os.remove(test_json_path)
    print(f"\nTest file '{test_json_path}' removed.")