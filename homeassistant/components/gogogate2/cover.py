"""Support for Gogogate2 garage Doors."""
from typing import Callable, List, Optional

from gogogate2_api.common import AbstractDoor, DoorStatus, get_configured_doors
import voluptuous as vol

from homeassistant.components.cover import (
    DEVICE_CLASS_GARAGE,
    DEVICE_CLASS_GATE,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .common import (
    DeviceDataUpdateCoordinator,
    GoGoGate2Entity,
    get_data_update_coordinator,
)
from .const import DEVICE_TYPE_GOGOGATE2, DEVICE_TYPE_ISMARTGATE, DOMAIN

COVER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_DEVICE, default=DEVICE_TYPE_GOGOGATE2): vol.In(
            (DEVICE_TYPE_GOGOGATE2, DEVICE_TYPE_ISMARTGATE)
        ),
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
            DeviceCover(config_entry, data_update_coordinator, door)
            for door in get_configured_doors(data_update_coordinator.data)
        ]
    )


class DeviceCover(GoGoGate2Entity, CoverEntity):
    """Cover entity for goggate2."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        data_update_coordinator: DeviceDataUpdateCoordinator,
        door: AbstractDoor,
    ) -> None:
        """Initialize the object."""
        super().__init__(config_entry, data_update_coordinator, door)
        self._api = data_update_coordinator.api
        self._is_available = True

    @property
    def name(self):
        """Return the name of the door."""
        return self._get_door().name

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        door = self._get_door()

        if door.status == DoorStatus.OPENED:
            return False
        if door.status == DoorStatus.CLOSED:
            return True

        return None

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        door = self._get_door()
        if door.gate:
            return DEVICE_CLASS_GATE

        return DEVICE_CLASS_GARAGE

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    async def async_open_cover(self, **kwargs):
        """Open the door."""
        await self._api.async_open_door(self._get_door().door_id)

    async def async_close_cover(self, **kwargs):
        """Close the door."""
        await self._api.async_close_door(self._get_door().door_id)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"door_id": self._get_door().door_id}
