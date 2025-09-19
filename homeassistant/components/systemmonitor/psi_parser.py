"""Parses Pressure Stall Information (PSI) from /proc/pressure files on Linux systems"""

import re

def parse_pressure_file(file_path):
    """
    Parses a single /proc/pressure file (cpu, memory, or io).

    Args:
        file_path (str): The full path to the pressure file.

    Returns:
        dict: A dictionary containing the parsed pressure stall information,
              or None if the file cannot be read or parsed.
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except IOError:
        print(f"Error: Could not read file at {file_path}")
        return None

    data = {}
    # The regex looks for 'some' and 'full' lines and captures the values.
    # It accounts for floating point numbers and integer values.
    # Example line: "some avg10=0.00 avg60=0.00 avg300=0.00 total=0"
    pattern = re.compile(r'(some|full)\s+(.*)')
    lines = content.strip().split('\n')

    for line in lines:
        match = pattern.match(line)
        if match:
            line_type, values_str = match.groups()
            values = {}
            for item in values_str.split():
                key, value = item.split('=')
                # Convert values to float, except for 'total' which is an integer
                if key == 'total':
                    values[key] = int(value)
                else:
                    values[key] = float(value)
            data[line_type] = values
            
    return data

def get_all_pressure_info():
    """
    Parses all available pressure information from /proc/pressure/.

    Returns:
        dict: A dictionary containing cpu, memory, and io pressure info.
              Returns an empty dictionary if no pressure files are found.
    """
    pressure_info = {}
    resources = ['cpu', 'memory', 'io']

    for resource in resources:
        file_path = f'/proc/pressure/{resource}'
        parsed_data = parse_pressure_file(file_path)
        if parsed_data:
            pressure_info[resource] = parsed_data

    return pressure_info

if __name__ == '__main__':
    # This block will run when the script is executed directly
    pressure_data = get_all_pressure_info()

    if pressure_data:
        print("Pressure Stall Information:")
        for resource, data in pressure_data.items():
            print(f"\n--- {resource.upper()} ---")
            if 'some' in data:
                print("Some:")
                for key, value in data['some'].items():
                    print(f"  {key}: {value}")
            if 'full' in data:
                print("Full:")
                for key, value in data['full'].items():
                    print(f"  {key}: {value}")
    else:
        print("Could not retrieve any pressure stall information.")
        print("Please ensure you are running on a Linux system with PSI enabled.")
