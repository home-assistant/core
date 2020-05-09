"""Common code for GogoGate2 component."""
from datetime import datetime, timedelta
import logging
from typing import Callable, NamedTuple, Optional

from gogogate2_api import GogoGate2Api, InfoResponse
from gogogate2_api.common import Door, get_configured_doors

from homeassistant.components.gogogate2.const import (
    DATA_MANAGERS,
    DATA_UPDATED_SIGNAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)


class StateData(NamedTuple):
    """State data for a cover entity."""

    config_unique_id: str
    unique_id: Optional[str]
    door: Optional[Door]


class DataManager:
    """Manage data retrieval and update from gogogate2 devices."""

    def __init__(
        self, hass: HomeAssistant, api: GogoGate2Api, config_entry: ConfigEntry
    ) -> None:
        """Initialize the object."""
        self._hass = hass
        self._api = api
        self._config_entry = config_entry
        self._cancel_polling_func: Optional[Callable] = None

    @property
    def api(self) -> GogoGate2Api:
        """Get the api."""
        return self._api

    def start_polling(self) -> None:
        """Start polling for data."""

        async def runner(now: datetime) -> None:
            await self.async_update()

        self._cancel_polling_func = async_track_time_interval(
            self._hass, runner, timedelta(seconds=5)
        )

    def stop_polling(self) -> None:
        """Stop polling for data."""
        if self._cancel_polling_func:
            self._cancel_polling_func()

        self._cancel_polling_func = None

    async def async_update(self) -> None:
        """Update data from the gogogate2 device."""
        data = await async_api_info_or_none(self._hass, self._api)
        if data is None:
            self.async_update_door(None)
        else:
            for door in get_configured_doors(data):
                self.async_update_door(door)

    def async_update_door(self, door: Optional[Door]) -> None:
        """Dispatch new state data to a cover entity."""
        async_dispatcher_send(
            self._hass,
            DATA_UPDATED_SIGNAL,
            StateData(
                config_unique_id=self._config_entry.unique_id,
                unique_id=None
                if door is None
                else cover_unique_id(self._config_entry, door),
                door=door,
            ),
        )


def cover_unique_id(config_entry: ConfigEntry, door: Door) -> str:
    """Generate a cover entity unique id."""
    return f"{config_entry.unique_id}_{door.door_id}"


def create_data_manager(
    hass: HomeAssistant, config_entry: ConfigEntry, api: GogoGate2Api
) -> DataManager:
    """Create a data manager."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_MANAGERS, {})
    hass.data[DOMAIN][DATA_MANAGERS].setdefault(
        config_entry.unique_id, DataManager(hass, api, config_entry)
    )

    return hass.data[DOMAIN][DATA_MANAGERS][config_entry.unique_id]


def get_data_manager(hass: HomeAssistant, config_entry: ConfigEntry) -> DataManager:
    """Get an existing data manager."""
    return hass.data[DOMAIN][DATA_MANAGERS][config_entry.unique_id]


def get_api(config_data: dict) -> GogoGate2Api:
    """Get an api object for config data."""
    return GogoGate2Api(
        config_data[CONF_IP_ADDRESS],
        config_data[CONF_USERNAME],
        config_data[CONF_PASSWORD],
    )


async def async_api_info_or_none(
    hass: HomeAssistant, api: GogoGate2Api
) -> Optional[InfoResponse]:
    """Check if the device is accessible.

    Returns InfoResponse if accessible, False otherwise.
    """
    try:
        return await hass.async_add_executor_job(api.info)

    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Failed to connect")
        return None
