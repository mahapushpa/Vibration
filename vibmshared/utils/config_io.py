# config_io.py
"""
Handles reading, writing, and managing Master and Device config files for vibmtool.
Supports .ini-style format with sections and metadata headers.
"""

import os
import ast  # Make sure this is at the top
import configparser

class ConfigIO:
    """
    A utility class for managing INI-style configuration files for production tool use.
    Supports both master and device configurations, including section-based access and serial status updates.
    """
    def __init__(self, path_handler = None, log_handler = None):
        self.path_handler = path_handler
        self.log_handler  = log_handler

    def load_file(self, filepath):
        """
        Load and parse an INI file into a nested dictionary structure.
        Returns:
            Dict[section][key] = parsed_value (int, float, bool, dict, or str)
        Raises:
            FileNotFoundError if file does not exist.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Config file not found: {filepath}")

        # Fresh parser per load: configparser.read() MERGES into existing
        # state, so the old shared self.parser accumulated sections across
        # calls if one ConfigIO instance was ever reused.
        parser = configparser.ConfigParser()
        parser.read(filepath)
        data_dict = {}

        for section in parser.sections():
            data_dict[section] = {}
            for key, value in parser.items(section):
                try:
                    # NOTE [T6]: literal_eval coerces numeric-looking free
                    # text ("1234" -> int, "True" -> bool); consumers of
                    # free-text fields must str() before str-methods.
                    parsed_val = ast.literal_eval(value)
                    data_dict[section][key] = parsed_val
                except Exception:
                    # normal path for plain text values (configparser values
                    # are always str — the old isinstance warn was dead code)
                    data_dict[section][key] = value  # Fallback to raw string

        # self.log_handler.log(f"Config loaded successfully from: {filepath}", tag='info')
        return data_dict

    def save_file(self, filepath, data_dict):
        """
        Save a nested dictionary structure to an INI file format.
        Parameters:
            filepath (str): Path to the INI file.
            data_dict (dict): Dictionary of sections -> key-values to save.
        """
        parser = configparser.ConfigParser()
        for section, fields in data_dict.items():
            parser[section] = {}
            for key, value in fields.items():
                parser[section][key] = str(value)

        dir_name = os.path.dirname(filepath)
        if dir_name:   # bare filename -> current dir; makedirs('') would raise
            os.makedirs(dir_name, exist_ok=True)
        with open(filepath, 'w') as configfile:
            parser.write(configfile)
        
        #self.log_handler.log(f"Config loaded successfully from: {filepath}", tag='info')


