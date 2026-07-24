# analyzer_features.py

FEATURE_FLAGS = {
    "ENABLE_EXTRA_DEVICE"   : False,
    "ENABLE_SETUP_DROPDOWN" : False,

    "ENABLE_BRD_DROPDOWN"   : False,
    "ENABLE_ADC_DROPDOWN"   : False,
    "ENABLE_SYS_DROPDOWN"   : False,

    "ENABLE_BUILD_TOP_BUTTON" : False,
    "ENABLE_TF_BTN" : False,
    "ENABLE_EXPORT_TF_DATA_BTN"      : True,

    # Add more as needed
}

# Sanity check
for key, value in FEATURE_FLAGS.items():
    assert isinstance(value, bool), f"Invalid value for {key}: {value}"

# Wrapper function for clean access
def IS_ENABLED(flag_name: str) -> bool:
    """Check if a feature flag is enabled."""
    try:
        return FEATURE_FLAGS[flag_name]
    except KeyError:
        raise KeyError(f"Unknown feature flag: {flag_name}")
