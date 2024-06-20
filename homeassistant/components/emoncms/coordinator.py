"""DataUpdateCoordinator for the emoncms integration."""

from datetime import timedelta
import logging
from typing import Any

from pyemoncms import EmoncmsClient

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class EmoncmsCoordinator(DataUpdateCoordinator[list[dict[str, Any]] | None]):
    """Emoncms Data Update Coordinator."""

    def __init__(
        self, hass: HomeAssistant, emoncms_client: EmoncmsClient, config: ConfigType
    ) -> None:
        """Initialize the emoncms data coordinator."""
        scan_interval = config.get(CONF_SCAN_INTERVAL, timedelta(seconds=30))
        super().__init__(
            hass,
            _LOGGER,
            name="emoncms_coordinator",
            update_method=emoncms_client.async_list_feeds,
            update_interval=scan_interval,
        )
