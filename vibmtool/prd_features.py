# feature_flags.py

GLB_VALID   = 1
GLB_INVALID = 0

FEATURE_FLAGS = {
    "ENABLE_EXTRA_DEVICE"   : GLB_INVALID,
    "ENABLE_SETUP_DROPDOWN" : GLB_INVALID,
    
    "ENABLE_BRD_DROPDOWN"   : GLB_VALID,
    "ENABLE_ADC_DROPDOWN"   : GLB_VALID,
    "ENABLE_SYS_DROPDOWN"   : GLB_VALID,
    
    "ENABLE_BUILD_TOP_BUTTON" : GLB_INVALID,
    
    # Add more as needed
}

# Sanity check
for key, value in FEATURE_FLAGS.items():
    assert value in (GLB_VALID, GLB_INVALID), f"Invalid value for {key}: {value}"

# Wrapper function for clean access
def IS_ENABLED(flag_name: str) -> bool:
    """Check if a feature flag is enabled."""
    try:
        return FEATURE_FLAGS[flag_name] == GLB_VALID
    except KeyError:
        raise KeyError(f"Unknown feature flag: {flag_name}")




