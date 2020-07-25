"""Support for Gogogate2 garage Doors."""
import logging
from typing import Callable, List, Optional

from gogogate2_api.common import Door, DoorStatus, get_configured_doors, get_door_by_id
import voluptuous as vol

from homeassistant.components.cover import (
    DEVICE_CLASS_GARAGE,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .common import (
    GogoGateDataUpdateCoordinator,
    cover_unique_id,
    get_data_update_coordinator,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


COVER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant, config: dict, add_entities: Callable, discovery_info=None
) -> None:
    """Convert old style file configs to new style configs."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], Optional[bool]], None],
) -> None:
    """Set up the config entry."""
    data_update_coordinator = get_data_update_coordinator(hass, config_entry)

    async_add_entities(
        [
            Gogogate2Cover(config_entry, data_update_coordinator, door)
            for door in get_configured_doors(data_update_coordinator.data)
        ]
    )


class Gogogate2Cover(CoverEntity):
    """Cover entity for goggate2."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        data_update_coordinator: GogoGateDataUpdateCoordinator,
        door: Door,
    ) -> None:
        """Initialize the object."""
        self._config_entry = config_entry
        self._data_update_coordinator = data_update_coordinator
        self._door = door
        self._api = data_update_coordinator.api
        self._unique_id = cover_unique_id(config_entry, door)
        self._is_available = True

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._is_available

    @property
    def should_poll(self) -> bool:
        """Return False as the data manager handles dispatching data."""
        return False

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the door."""
        return self._door.name

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        if self._door.status == DoorStatus.OPENED:
            return False
        if self._door.status == DoorStatus.CLOSED:
            return True

        return None

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_GARAGE

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    async def async_open_cover(self, **kwargs):
        """Open the door."""
        await self.hass.async_add_executor_job(self._api.open_door, self._door.door_id)

    async def async_close_cover(self, **kwargs):
        """Close the door."""
        await self.hass.async_add_executor_job(self._api.close_door, self._door.door_id)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        attrs = super().state_attributes
        attrs["door_id"] = self._door.door_id
        return attrs

    @callback
    def async_on_data_updated(self) -> None:
        """Receive data from data dispatcher."""
        if not self._data_update_coordinator.last_update_success:
            self._is_available = False
            self.async_write_ha_state()
            return

        door = get_door_by_id(self._door.door_id, self._data_update_coordinator.data)

        # Set the state.
        self._door = door
        self._is_available = True
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register update dispatcher."""
        self.async_on_remove(
            self._data_update_coordinator.async_add_listener(self.async_on_data_updated)
        )
