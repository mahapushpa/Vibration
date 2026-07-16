import os
import logging
import requests
import configparser
from   pathlib import Path

# ------------------------------------------------------------------------------
from vibmshared.core.path_manager import PathManager

# ------------------------------------------------------------------------------
    
# ------------------------------------------------------------------------------
# Product Metadata
# Purpose: Product branding, title and icon setup
# ------------------------------------------------------------------------------
class ProductMeta:
    _version = 'V1.0'
    _name    = 'vibmscope™'
    _icon    = 'maps_logo.ico'

    @classmethod
    def configure(cls, product: str):
        """Configure the product meta based on selected product type."""
        product_map = {
            'vibmanalyser': {
                'name':    'VibAnalyser™',
                'version': 'V1.0',
                'icon':    'maps_logo.ico',
            },
            'vibmscope': {
                'name':    'vibmscope™',
                'version': 'V1.0',
                'icon':    'maps_logo.ico',
            },
            'vibmtool': {
                'name':    'vibmtool™',
                'version': 'V1.0',
                'icon':    'maps_logo.ico',
            },
        }
        if product not in product_map:
            raise ValueError(f"Unknown product type: {product}")

        # Apply configuration
        config = product_map[product]
        cls._name    = config['name']
        cls._version = config['version']
        cls._icon    = config['icon']

    @classmethod
    def set_title(cls, tk_root):
        """Set the application title for the Tkinter root window."""
        tk_root.title(f"{cls._name} {cls._version}")

    @classmethod
    def get_title(cls):
        """Set the application title for the Tkinter root window."""
        return(f"{cls._name} {cls._version}")

    @classmethod
    def get_icon(cls) -> str:
        """Return full path to the icon file."""
        ico_path = PathManager.find_file_in_subfolders(cls._icon)
        if ico_path:
            return str(ico_path)
        
        logging.warning(f"Icon file '{cls._icon}' not found in sys.path, using fallback.")
        print(f"[WARNING] Icon path does not exist: {ico_path}")
        return cls._icon  # fallback to original (relative) name

    @classmethod
    def set_icon(cls, window):
        """Set the icon on the Tkinter root window."""
        icon_path = cls.get_icon()
        
        try:
            if os.path.exists(icon_path):
                window.iconbitmap(icon_path)
                # print(f"[ICON] Icon set from: {icon_path}")
            else:
                print(f"[WARNING] Icon file not found: {icon_path}")
        except Exception as e:
            print(f"[WARNING] Failed to set icon: {e}")

    @classmethod
    def get_name(cls):
        return cls._name

    @classmethod
    def get_version(cls):
        return cls._version

# ------------------------------------------------------------------------------
class UserMeta:
    """Metadata information for file headers."""
    MAX_LINE_LENGTH = 40   # Maximum length in one line of user details

    def __init__(self, config_path = None):
        self.config_path = os.path.join(config_path, "user_details.ini")        
        self.name = ''
        self.address_lines = []
        self.geo_code = ''
        self.geo_comment = ''
        self.load_or_create_config()

    def load_or_create_config(self):
        config = configparser.ConfigParser(strict = False, delimiters = ('='))

        if not os.path.exists(self.config_path):
            self.create_default_config()

        config.read(self.config_path, encoding='utf-8')

        self.address_lines = []
        if 'User' in config:
            # First line is always Name
            self.name = config['User'].get('name', '').strip()[:self.MAX_LINE_LENGTH]
            # Remaining address lines
            for key, val in config.items('User'):
                if key.lower().startswith('address'):
                    line = val.strip()[:self.MAX_LINE_LENGTH]
                    if line:
                        self.address_lines.append((key.capitalize(), line))

        # Read [Geocode] section
        geo_code_line = config.get('Geocode', 'Location', fallback='').strip()
        if geo_code_line:
            self.geo_code = geo_code_line
            self.geo_comment = ''
        else:
            self.geo_code = 'Please add in user_details.ini'
            self.geo_comment = '(Geo missing)'

    def create_default_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.write("# Do not delete lines which have [text]\n")
            f.write("# Other lines are needed to change as user needs\n")
            f.write("\n[User]\n")
            f.write("name = MAPS Technologies\n")
            f.write("address1 = 57 Yashoda Marg\n")
            f.write("address2 = Officers Campus Ext\n")
            f.write("address3 = Sirsi Road\n")
            f.write("address4 = Jaipur - 302012\n")
            f.write("address5 = Rajasthan, India\n")

            # Use IP-based geo once
            geo_code = self.get_ip_geolocation_dms() or 'Add in user_details.ini'
            comment = ' (IP approx)' if geo_code != 'Add in user_details.ini' else ' (Geo missing)'
            
            f.write("\n[Geocode]\n")
            f.write(f"Location = {geo_code}{comment}\n")

    @staticmethod
    def deg_to_dms_str(degree_float):
        """Convert decimal degrees to DMS string with rounding."""
        deg = int(degree_float)
        fractional = abs(degree_float - deg)
        minutes = int(fractional * 60)
        seconds = int(round((fractional * 60 - minutes) * 60))
        
        # Handle rounding overflow
        if seconds == 60:
            seconds = 0
            minutes += 1
        if minutes == 60:
            minutes = 0
            deg += 1 if deg >= 0 else -1
        
        return f"{abs(deg)}°{minutes}'{seconds}\""
         
    @staticmethod
    def get_ip_geolocation_dms():
        """Get approximate location using public IP, return as DMS with direction."""
        try:
            response = requests.get('https://ipinfo.io/', timeout=5)
            data = response.json()
            loc = data.get('loc')  # Example: "26.9124,75.7873"
            if loc:
                lat_str, lon_str = loc.split(',')
                lat_f = float(lat_str.strip())
                lon_f = float(lon_str.strip())

                lat_dir = 'N' if lat_f >= 0 else 'S'
                lon_dir = 'E' if lon_f >= 0 else 'W'

                lat_dms = UserMeta.deg_to_dms_str(lat_f)
                lon_dms = UserMeta.deg_to_dms_str(lon_f)

                return f"{lat_dms}{lat_dir} {lon_dms}{lon_dir}"
        except Exception as e:
            print(f"[ERROR] IP geolocation failed: {e}")
            logging.error(f"[ERROR] IP geolocation failed: {e}")
            return None

    def get_user_info_block(self):
        """Format metadata into a header string."""
        lines = []
        lines.append("-" * 80)
        lines.append(" User Information")
        lines.append("-" * 80)

        if self.name:
            lines.append(f" Name     : {self.name}")
        for label, line in self.address_lines:
            lines.append(f" {label:<9}: {line}")

        # Always print GeoCode field
        if self.geo_code:
            comment = f" {self.geo_comment}" if self.geo_comment else ''
            lines.append(f" GeoCode  : {self.geo_code}{comment}")

        # lines.append("-" * 80)
        return "\n".join(lines)

    def update_geocode(self, new_code, comment = '(Manual override)'):
        """Helper to override the GeoCode in real-time and update .ini."""
        config = configparser.ConfigParser()
        config.read(self.config_path, encoding='utf-8')
        if 'Geocode' not in config:
            config.add_section('Geocode')
        config.set('Geocode', 'Location', f"{new_code.strip()} {comment}")
        with open(self.config_path, 'w', encoding = 'utf-8') as f:
            config.write(f)
        self.geo_code = new_code.strip()
        self.geo_comment = comment

# ------------------------------------------------------------------------------
if __name__ == '__main__':
    import  tkinter as tk
    root = tk.Tk()
    
    ProductMeta.configure('vibmtool') #'VibrationAnalyser','vibmscope','vibmtool'

    ProductMeta.set_icon(root)
    ProductMeta.set_title(root)
    root.update_idletasks()
    root.state('zoomed')
    root.update()
    
    print("[TEST] Testing ProductMeta")
    print("App Name:", ProductMeta.get_name())
    print("Version:",  ProductMeta.get_version())
    print("Icon:",     ProductMeta.get_icon())
    
    print("[TEST] UserMeta from user_details.ini")
    config_path = os.path.join('.', 'config')
    user_meta = UserMeta(config_path)
    user_info = user_meta.get_user_info_block()
    print(user_info)

    root.mainloop()
