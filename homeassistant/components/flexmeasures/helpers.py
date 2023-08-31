"""Helper to create S2 FlexMeasures Client instance."""
from datetime import datetime

from homeassistant import config_entries


def get_previous_option(config: config_entries.ConfigEntry, option: str):
    """Get default from previous options or otherwise from initial config."""
    return config.options.get(option, config.data[option])


def time_mod(time, delta, epoch=None):
    """From https://stackoverflow.com/a/57877961/13775459."""
    if epoch is None:
        epoch = datetime(1970, 1, 1, tzinfo=time.tzinfo)
    return (time - epoch) % delta


def time_ceil(time, delta, epoch=None):
    """From https://stackoverflow.com/a/57877961/13775459."""
    mod = time_mod(time, delta, epoch)
    if mod:
        return time + (delta - mod)
    return time
