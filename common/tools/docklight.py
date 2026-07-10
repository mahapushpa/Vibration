import os

HEADER_BLOCK = [
    "VERSION",
    "8",
    "",
    "COMMSETTINGS",
    "0",
    "COM3",
    "COM2",
    "115200",
    "2",
    "63",
    "4",
    "0",
    "0",
    "",
    "COMMDISPLAY",
    "0",
    "",
    "VERSATAP",
    "0",
    "",
    "CHANNELALIAS",
    "",
    "",
    "",        
]

BLOCK_SIZE = 6  # Each command block has 6 lines

def format_docklight_from_two_lines(input_filename: str, output_filename: str):
    """
    Reads input file (two lines per command):
      - line0: command name
      - line1: command string
    Writes Docklight script output with blocks of 6 lines + blank line:
      SEND
      cmd_number
      command_name
      command_string (space every 2 chars)
      0
      5
      "" (blank line)
    Header is added at top.
    """
    folder = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(folder, input_filename)
    output_path = os.path.join(folder, output_filename)

    # Read input file
    with open(input_path, 'r') as f:
        raw_lines = [line.rstrip('\n') for line in f if line.strip()]

    formatted_lines = []
    formatted_lines.extend(HEADER_BLOCK)

    cmd_counter = 0
    i = 0
    while i < len(raw_lines):
        if i + 1 >= len(raw_lines):
            print(f"[WARN] Last command has no pair at line {i}. Skipping.")
            break

        cmd_name = raw_lines[i]
        cmd_string = raw_lines[i+1].replace(" ", "")
        spaced_command = ' '.join(cmd_string[j:j+2] for j in range(0, len(cmd_string), 2))

        # Build Docklight block
        block = [
            "SEND",
            str(cmd_counter),
            cmd_name,
            spaced_command,
            "0",
            "5",
            ""
        ]
        formatted_lines.extend(block)

        cmd_counter += 1
        i += 2

    # Write output
    with open(output_path, 'w') as f:
        for line in formatted_lines:
            f.write(line + '\n')

    print(f"[INFO] Docklight script written to '{output_path}' with {cmd_counter} commands.")

#-------------------------------------------------------------------------------
# Example Usage
if __name__ == "__main__":
    # Same folder as the script
    format_docklight_from_two_lines("docklight_input.txt", "docklight_output.ptp")

