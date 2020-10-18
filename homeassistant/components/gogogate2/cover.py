"""Support for Gogogate2 garage Doors."""
import time
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
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .common import (
    DeviceDataUpdateCoordinator,
    cover_unique_id,
    get_data_update_coordinator,
)
from .const import (
    DEVICE_TYPE_GOGOGATE2,
    DEVICE_TYPE_ISMARTGATE,
    DOMAIN,
    MANUFACTURER,
    TRANSITION_COMPLETE_DURATION,
)

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
        self._last_action_timestamp = 0
        self._scheduled_transition_update = None
        self._is_opening = False
        self._is_closing = False

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

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._is_closing

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._is_opening

    async def async_open_cover(self, **kwargs):
        """Open the door."""
        if await self.hass.async_add_executor_job(
            self._api.open_door, self._get_door().door_id
        ):
            self._is_opening = True
            self._async_schedule_update_for_transition()

    async def async_close_cover(self, **kwargs):
        """Close the door."""
        if await self.hass.async_add_executor_job(
            self._api.close_door, self._get_door().door_id
        ):
            self._is_closing = True
            self._async_schedule_update_for_transition()

    @property
    def state_attributes(self):
        """Return the state attributes."""
        attrs = super().state_attributes
        attrs["door_id"] = self._get_door().door_id
        return attrs

    def _get_door(self) -> AbstractDoor:
        if time.time() - self._last_action_timestamp <= TRANSITION_COMPLETE_DURATION:
            # If we just started a transition we need
            # to prevent a bouncy state
            return self._door

        self._is_closing = False
        self._is_opening = False
        door = get_door_by_id(self._door.door_id, self.coordinator.data)
        self._door = door or self._door
        return self._door

    def _async_schedule_update_for_transition(self):
        self.async_write_ha_state()

        # Cancel any previous updates
        if self._scheduled_transition_update:
            self._scheduled_transition_update()

        # Schedule an update for when we expect the transition
        # to be completed so the garage door or gate does not
        # seem like its closing or opening for a long time
        self._scheduled_transition_update = async_call_later(
            self.hass,
            TRANSITION_COMPLETE_DURATION,
            self._async_complete_schedule_update,
        )

    async def _async_complete_schedule_update(self, _):
        """Update status of the cover via coordinator."""
        self._scheduled_transition_update = None
        await self.coordinator.async_request_refresh()

    async def async_will_remove_from_hass(self):
        """Undo transition call later."""
        if self._scheduled_transition_update:
            self._scheduled_transition_update()

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
