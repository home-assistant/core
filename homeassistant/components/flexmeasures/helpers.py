"""Helper to create S2 FlexMeasures Client instance."""
from homeassistant import config_entries


def get_previous_option(config: config_entries.ConfigEntry, option: str):
    """Get default from previous options or otherwise from initial config."""
    return config.options.get(option, config.data[option])
