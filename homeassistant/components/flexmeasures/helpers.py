from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import S2FlexMeasuresClient


@callback
def get_fm_client(hass: HomeAssistant) -> S2FlexMeasuresClient:
    """Return FlexMeasuresClient instance."""
    # NOTE: This assumes only one FlexMeasuresClient is used as coordinator.
    fm_client: S2FlexMeasuresClient = next(iter(hass.data[DOMAIN].values()))
    return fm_client
