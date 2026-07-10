#-------------------------------------------------------------------------------
# Production INI Metadata Cleaned and Reviewed
#-------------------------------------------------------------------------------
"""
Defines metadata structure, default values, and tooltip descriptions used for
Master and Device INI configuration in the Production Tool.
This includes:
- Field definitions and input types for metadata section
- Tooltip strings for GUI display
- Lists of keys/sections to skip for Master, Device, and Summary modes
"""

#-------------------------------------------------------------------------------
# Metadata Field Definitions
#-------------------------------------------------------------------------------
META_DEFINITIONS = {
    "client_info": {
        "client":        {"type": "entry", "default": "MAPS"},
        "order_id":      {"type": "entry", "default": "202506"},

        "base_serial":   {"type": "entry", "default": "101"},
        # "serial_no":     {"type": "entry", "default": ""},

        "total_qty":     {"type": "entry", "default": "10"},
        "source":        {"type": "entry", "default": ""},
        "created_on":    {"type": "entry", "default": "DD MMM YYYY"},
    },
    "product_info": {
        # "control_board": {"type": "entry", "default": ""},
        "analog_board":  {"type": "entry", "default": "ADC_VER"},
        "comm_board":    {"type": "entry", "default": "COM_VER"},
        "display_board": {"type": "entry", "default": "DSP_VER"},
        "power_board":   {"type": "entry", "default": "PWR_VER"},
    },
}


#-------------------------------------------------------------------------------
# INI Sections Sections name in INI files of master and device ini's
#-------------------------------------------------------------------------------
PRD_INI_SECTIONS = {
    "CLIENT":   "client_info",  # Client Info
    "PRODUCT":  "product_info", # Product Info
    "BRD":      "hardware_info",# BRD
    "ADC":      "analog_info",  # ADC
    "SYS":      "system_info",  # SYS
    "DEVICE":   "device_info",  # List of devices for Client
}

#-------------------------------------------------------------------------------
# Tooltip Strings for Meta Fields (used in GUI)
#-------------------------------------------------------------------------------
META_FIELD_TOOLTIPS = {
    "client_info":   "Client and Order Details",
    "product_info":  "Product HW and FW Revisions used details",
    "client":        "Client name for order",
    "order_id":      "Product order number",
    "base_serial":   "First serial number for batch",
    "total_qty":     "Units in this batch",
    "created_on":    "Date on which this File Created",
    "serial_no":     "Unique numeric ID for device (0-9999)",
    "source":        "Input data to generate this config",
    "power_board":   "Power PCB revision",
    "analog_board":  "Analog PCB revision",
    "control_board": "Controller PCB revision",
    "comm_board":    "Communication PCB revision",
    "display_board": "Display PCB revision",
    "firmware":      "Firmware version used in units",
}

PROGAM_KEY_TOOLTIPS = {
    "write":  "Send selected settings to the connected device",
    "read":   "Read selected parameters from the device",
    "verify": "Compare INI values and device values for validation",
    "save":   "Save current settings to a new INI file",
    "select_all": "Select and deselect all Params",
    "cancel": "Cancel the Operation and exit",
}

#-------------------------------------------------------------------------------
# Skip Keys Meta-level keys to exclude from GUI or processing
#-------------------------------------------------------------------------------
META_MASTER_SKIP_KEYS  = {"serial_no"}
META_DEVICE_SKIP_KEYS  = {"base_serial", "serial_no", "total_qty"}
META_PROGRAM_SKIP_KEYS = {"base_serial", "serial_no", "total_qty"}

SECTION_MASTER_SKIP   = {}
SECTION_DEVICE_SKIP   = {"device_info"}
SECTION_PROGRAM_SKIP  = {"device_info"}

# below list from CMD_TABLE, flat_key names
PARAM_MASTER_SKIP_KEYS  = {"sys_ser_no",  "sys_mfg_date"}
PARAM_DEVICE_SKIP_KEYS  = {"base_serial", "total_qty"}
PARAM_PROGRAM_SKIP_KEYS = {"base_serial", "total_qty"}

SUMMARY_SKIP_SECTION = {"product_info", "hardware_info", "analog_info", "system_info"}

