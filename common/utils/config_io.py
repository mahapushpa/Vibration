# config_io.py
"""
Handles reading, writing, and managing Master and Device config files for ProductionTool.
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
        self.parser = configparser.ConfigParser()

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

        self.parser.read(filepath)
        data_dict = {}

        for section in self.parser.sections():
            data_dict[section] = {}
            for key, value in self.parser.items(section):
                try:
                    parsed_val = ast.literal_eval(value)
                    data_dict[section][key] = parsed_val
                except Exception as e:
                    if not isinstance(value, str):
                        self.log_handler.log(
                            f"[{section}] {key} = '{value}' could not be parsed: {e} — using raw string.",
                            tag='warn'
                        )
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

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as configfile:
            parser.write(configfile)
        
        #self.log_handler.log(f"Config loaded successfully from: {filepath}", tag='info')


