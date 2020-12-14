"""Support for Gogogate2 garage Doors."""
from typing import Callable, List, Optional

from gogogate2_api.common import (
    AbstractDoor,
    DoorStatus,
    get_configured_doors,
    get_door_by_id,
)
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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .common import (
    DeviceDataUpdateCoordinator,
    cover_unique_id,
    get_data_update_coordinator,
)
from .const import DEVICE_TYPE_GOGOGATE2, DEVICE_TYPE_ISMARTGATE, DOMAIN, MANUFACTURER

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


class DeviceCover(CoordinatorEntity, CoverEntity):
    """Cover entity for goggate2."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        data_update_coordinator: DeviceDataUpdateCoordinator,
        door: AbstractDoor,
    ) -> None:
        """Initialize the object."""
        super().__init__(data_update_coordinator)
        self._config_entry = config_entry
        self._door = door
        self._api = data_update_coordinator.api
        self._unique_id = cover_unique_id(config_entry, door)
        self._is_available = True

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._unique_id

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
        await self.hass.async_add_executor_job(
            self._api.open_door, self._get_door().door_id
        )

    async def async_close_cover(self, **kwargs):
        """Close the door."""
        await self.hass.async_add_executor_job(
            self._api.close_door, self._get_door().door_id
        )

    @property
    def state_attributes(self):
        """Return the state attributes."""
        attrs = super().state_attributes
        attrs["door_id"] = self._get_door().door_id
        return attrs

    def _get_door(self) -> AbstractDoor:
        door = get_door_by_id(self._door.door_id, self.coordinator.data)
        self._door = door or self._door
        return self._door

    @property
    def device_info(self):
        """Device info for the controller."""
        data = self.coordinator.data
        return {
            "identifiers": {(DOMAIN, self._config_entry.unique_id)},
            "name": self._config_entry.title,
            "manufacturer": MANUFACTURER,
            "model": data.model,
            "sw_version": data.firmwareversion,
        }
