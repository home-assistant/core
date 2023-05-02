from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import S2FlexMeasuresClient


@callback
def get_fm_client(hass: HomeAssistant) -> S2FlexMeasuresClient:
    """Return FlexMeasuresClient instance."""
    # NOTE: This assumes only one FlexMeasuresClient is used as coordinator.
    fm_client: S2FlexMeasuresClient = next(iter(hass.data[DOMAIN].values()))
    return fm_client


def get_previous_option(config: config_entries.ConfigEntry, option: str):
    """Get default from previous options or otherwise from initial config."""
    return config.options.get(option, config.data[option])
