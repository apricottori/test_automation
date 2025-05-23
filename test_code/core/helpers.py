# helpers.py
import re
from typing import List, Optional, Tuple

# pandas는 UI 로직에서 직접 사용하지 않으므로, 헬퍼 함수에서는 pd.isna 대신 일반적인 None 확인을 사용합니다.
# 만약 pandas가 특정 헬퍼 함수에 필요하다면, 해당 함수에서만 import 하거나,
# 이 프로젝트의 다른 부분(예: DataFrame 생성)에서 pandas를 사용한다면 여기에 포함할 수 있습니다.
# 현재로서는 pandas 의존성을 최소화합니다.
# import pandas as pd # Optional, if needed for specific helpers not yet defined

from . import constants
def normalize_hex_input(hex_str: Optional[str], 
                        default_num_chars: Optional[int] = None, 
                        add_prefix: bool = True) -> Optional[str]:
    """
    Normalizes hexadecimal string input.
    - Strips whitespace.
    - Converts to uppercase.
    - Ensures "0x" prefix if add_prefix is True.
    - Optionally zero-pads the hexadecimal part (after "0x") to default_num_chars.
    - Returns None if input is None, empty after strip, or contains invalid hex characters.

    Examples:
    normalize_hex_input("ff", 2) -> "0xFF"
    normalize_hex_input("0xff", 4) -> "0x00FF"
    normalize_hex_input("FF") -> "0xFF"
    normalize_hex_input("invalid", 2) -> None
    normalize_hex_input("0x", 2) -> None (or "0x00" if we decide empty "0x" is valid 0)
    normalize_hex_input(None, 2) -> None
    """
    if hex_str is None:
        return None
    
    s = str(hex_str).strip().upper()

    if s.startswith("0X"):
        s = s[2:]
    
    if not s: # If string is empty after stripping "0X" (e.g., input was "0x")
        if default_num_chars is not None: # If padding is requested, treat as 0
            s = "0".zfill(default_num_chars)
        else: # Otherwise, it's an empty hex string, could be invalid or 0
            return "0x0" if add_prefix else "0" # Or return None if strictly invalid

    if not all(c in "0123456789ABCDEF" for c in s):
        return None # Contains non-hex characters

    if default_num_chars is not None:
        s = s.zfill(default_num_chars)
        
    return "0x" + s if add_prefix else s

def convert_hex_to_bits(hex_val_str: Optional[str], num_bits: int) -> List[str]:
    """
    Converts a hexadecimal string (e.g., "0xFF") to a list of binary strings (MSB first).
    Returns a list of '0's if hex_val_str is None or empty.
    Returns a list of 'ERROR' strings upon conversion failure or invalid input.
    """
    if num_bits <= 0:
        return []

    normalized_hex = normalize_hex_input(hex_val_str) # Ensures "0x" prefix for int()

    if normalized_hex is None: # Handles None, empty, or invalid characters
        # print(f"Debug: normalize_hex_input for '{hex_val_str}' returned None. Defaulting to zeros.")
        return ['0'] * num_bits 

    try:
        # Ensure that we are not trying to convert an empty hex string like "0x"
        if normalized_hex == "0x": # If original was empty or just "0x"
            val = 0
        else:
            val = int(normalized_hex, 16)

        if val < 0:
             # print(f"Debug: Negative hex value {val} not supported.")
             return ['ERROR'] * num_bits
        
        binary_str = format(val, f'0{num_bits}b')
        
        # Handle potential overflow if the number is too large for num_bits
        if len(binary_str) > num_bits:
            # print(f"Debug: Hex value {normalized_hex} overflows {num_bits} bits. Truncating MSBs.")
            return list(binary_str[-num_bits:]) # Take LSBs
        return list(binary_str)
    except ValueError:
        # print(f"Debug: ValueError converting hex '{normalized_hex}' to bits.")
        return ['ERROR'] * num_bits

def convert_bit_list_to_hex_string(bit_list: List[str], 
                                   total_bits_for_field: Optional[int] = None) -> str:
    """
    Converts a list of bit strings (MSB first, e.g., ['1','1','0','0'])
    to a "0x" prefixed hexadecimal string (e.g., "0xC").
    Pads with leading zeros if total_bits_for_field is specified and bit_list is shorter.
    """
    if not bit_list:
        return "0x0" # Default for empty bit list
    
    actual_bits_to_convert = bit_list
    
    # If total_bits_for_field is specified, ensure the list matches this length for hex conversion
    if total_bits_for_field is not None:
        if len(bit_list) < total_bits_for_field:
            padding = ['0'] * (total_bits_for_field - len(bit_list))
            actual_bits_to_convert = padding + bit_list
        elif len(bit_list) > total_bits_for_field:
            # This implies the input bit_list is longer than the field,
            # which might indicate an issue upstream. For conversion, take MSBs.
            actual_bits_to_convert = bit_list[:total_bits_for_field] 

    valid_bits = []
    for bit in actual_bits_to_convert:
        if bit in ('0', '1'):
            valid_bits.append(bit)
        elif bit == '' or bit is None: # Treat empty string or None as '0'
            valid_bits.append('0') 
        else: # Contains 'ERROR' or other invalid char
            return "0xERR_BITS" # Indicate an error in the input bits

    if not valid_bits: # If all bits were invalid or empty, resulting in an empty list
        return "0x0"

    binary_string = "".join(valid_bits)
        
    try:
        decimal_value = int(binary_string, 2)
        # Calculate needed hex digits, ensuring at least 1 for "0"
        num_hex_digits = max(1, (len(valid_bits) + 3) // 4) 
        return f"0x{decimal_value:0{num_hex_digits}X}"
    except ValueError: # Should not happen if bits are '0' or '1'
        return "0xERR_CONV"

def map_access_to_type(access_str: Optional[str]) -> str:
    """Maps JSON 'access' string to a simplified 'Type' (RO/RW/WO)."""
    if access_str is None or str(access_str).strip() == "":
        return "N/A" # Not Available or Not Applicable
    
    access_lower = str(access_str).lower()
    mapping = {
        "read-only": "RO",
        "read-write": "RW",
        "write-only": "WO"
    }
    return mapping.get(access_lower, "N/A") # Default to N/A if unknown access type

def get_base_name_from_field_id(field_id_str: Optional[str]) -> str:
    """
    Extracts the base name from a field ID that might contain <...>.
    E.g., "SW_RESET<12:0>" -> "SW_RESET"
          "ENABLE"          -> "ENABLE"
          "FIELD<7>"        -> "FIELD"
    """
    if field_id_str is None or str(field_id_str).strip() == "":
        return ""
    
    s = str(field_id_str)
    match = re.match(r"(.+?)<.*>$", s)
    if match:
        return match.group(1)
    return s

# Example usage (can be removed or kept for testing this module)
if __name__ == '__main__':
    print(f"'ff' (2 chars) -> {normalize_hex_input('ff', 2)}")
    print(f"'0xff' (4 chars) -> {normalize_hex_input('0xff', 4)}")
    print(f"'FF' -> {normalize_hex_input('FF')}")
    print(f"'0x1' (1 char for val) -> {normalize_hex_input('0x1', 1, add_prefix=False)}")
    print(f"None -> {normalize_hex_input(None)}")
    print(f"'0x' -> {normalize_hex_input('0x')}")
    print(f"'' -> {normalize_hex_input('')}")


    print(f"\nconvert_hex_to_bits('0xFF', 8) -> {convert_hex_to_bits('0xFF', 8)}")
    print(f"convert_hex_to_bits('F', 4) -> {convert_hex_to_bits('F', 4)}")
    print(f"convert_hex_to_bits('0x123', 12) -> {convert_hex_to_bits('0x123', 12)}")
    print(f"convert_hex_to_bits('0x123', 8) -> {convert_hex_to_bits('0x123', 8)} (overflow truncated)")
    print(f"convert_hex_to_bits(None, 4) -> {convert_hex_to_bits(None, 4)}")
    print(f"convert_hex_to_bits('0x', 4) -> {convert_hex_to_bits('0x', 4)}")


    print(f"\nconvert_bit_list_to_hex_string(['1','1','1','1']) -> {convert_bit_list_to_hex_string(['1','1','1','1'])}")
    print(f"convert_bit_list_to_hex_string(['0','0','1','0']) -> {convert_bit_list_to_hex_string(['0','0','1','0'])}")
    print(f"convert_bit_list_to_hex_string(['1','0','1'], 4) -> {convert_bit_list_to_hex_string(['1','0','1'], 4)} (padded)")
    print(f"convert_bit_list_to_hex_string(['1','0','1','0','1'], 4) -> {convert_bit_list_to_hex_string(['1','0','1','0','1'], 4)} (truncated)")
    print(f"convert_bit_list_to_hex_string(['1','ERROR','0']) -> {convert_bit_list_to_hex_string(['1','ERROR','0'])}")
    print(f"convert_bit_list_to_hex_string([]) -> {convert_bit_list_to_hex_string([])}")

    print(f"\nmap_access_to_type('read-only') -> {map_access_to_type('read-only')}")
    print(f"map_access_to_type('READ-WRITE') -> {map_access_to_type('READ-WRITE')}")
    print(f"map_access_to_type(None) -> {map_access_to_type(None)}")

    print(f"\nget_base_name_from_field_id('FIELD<15:0>') -> {get_base_name_from_field_id('FIELD<15:0>')}")
    print(f"get_base_name_from_field_id('ENABLE') -> {get_base_name_from_field_id('ENABLE')}")
    print(f"get_base_name_from_field_id('OTHER<7>') -> {get_base_name_from_field_id('OTHER<7>')}")