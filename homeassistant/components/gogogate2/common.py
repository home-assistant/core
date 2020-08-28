"""Common code for GogoGate2 component."""
from datetime import timedelta
import logging
from typing import Awaitable, Callable, NamedTuple, Optional

import async_timeout
from gogogate2_api import GogoGate2Api
from gogogate2_api.common import Door

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_UPDATE_COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)


class StateData(NamedTuple):
    """State data for a cover entity."""

    config_unique_id: str
    unique_id: Optional[str]
    door: Optional[Door]


class GogoGateDataUpdateCoordinator(DataUpdateCoordinator):
    """Manages polling for state changes from the device."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        api: GogoGate2Api,
        *,
        name: str,
        update_interval: timedelta,
        update_method: Optional[Callable[[], Awaitable]] = None,
        request_refresh_debouncer: Optional[Debouncer] = None,
    ):
        """Initialize the data update coordinator."""
        DataUpdateCoordinator.__init__(
            self,
            hass,
            logger,
            name=name,
            update_interval=update_interval,
            update_method=update_method,
            request_refresh_debouncer=request_refresh_debouncer,
        )
        self.api = api


def get_data_update_coordinator(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> GogoGateDataUpdateCoordinator:
    """Get an update coordinator."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(config_entry.entry_id, {})
    config_entry_data = hass.data[DOMAIN][config_entry.entry_id]

    if DATA_UPDATE_COORDINATOR not in config_entry_data:
        api = get_api(config_entry.data)

        async def async_update_data():
            try:
                async with async_timeout.timeout(3):
                    return await hass.async_add_executor_job(api.info)
            except Exception as exception:
                raise UpdateFailed(
                    f"Error communicating with API: {exception}"
                ) from exception

        config_entry_data[DATA_UPDATE_COORDINATOR] = GogoGateDataUpdateCoordinator(
            hass,
            _LOGGER,
            api,
            # Name of the data. For logging purposes.
            name="gogogate2",
            update_method=async_update_data,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=5),
        )

    return config_entry_data[DATA_UPDATE_COORDINATOR]


def cover_unique_id(config_entry: ConfigEntry, door: Door) -> str:
    """Generate a cover entity unique id."""
    return f"{config_entry.unique_id}_{door.door_id}"


def get_api(config_data: dict) -> GogoGate2Api:
    """Get an api object for config data."""
    return GogoGate2Api(
        config_data[CONF_IP_ADDRESS],
        config_data[CONF_USERNAME],
        config_data[CONF_PASSWORD],
    )
