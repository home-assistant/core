"""Coordinator class to coordinate data updates."""
import logging
from typing import Any, cast

from huawei_smart_logger.huawei_smart_logger import HuaweiSmartLogger3000API

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, MIN_TIME_BETWEEN_UPDATES

_LOGGER = logging.getLogger(__name__)


class HuaweiSmartLogger3000DataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class definition for data coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: HuaweiSmartLogger3000API,
    ) -> None:
        """Initializion method for class definition for data coordinator."""
        self.hass = hass
        self.api = api
        _LOGGER.debug("In coordinator.py class")
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Async update data to retrieve data - no non-async method is supported."""
        _LOGGER.debug("In coordinator.py _async_update_data")
        try:
            data_dict = await self.api.fetch_data()

        except Exception as e:
            raise ConnectionError from e

        return cast(dict[str, Any], data_dict)
