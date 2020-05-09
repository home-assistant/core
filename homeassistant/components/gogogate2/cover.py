"""Support for Gogogate2 garage Doors."""
from datetime import datetime, timedelta
import logging
from typing import Callable, List, Optional

from gogogate2_api.common import Door, DoorStatus, get_configured_doors
import voluptuous as vol

from homeassistant.components.cover import (
    DEVICE_CLASS_GARAGE,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_CLOSING,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .common import DataManager, StateData, cover_unique_id, get_data_manager
from .const import DATA_UPDATED_SIGNAL, DOMAIN

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
    data_manager = get_data_manager(hass, config_entry)
    info = await hass.async_add_executor_job(data_manager.api.info)

    async_add_entities(
        [
            Gogogate2Cover(config_entry, data_manager, door)
            for door in get_configured_doors(info)
        ]
    )


class Gogogate2Cover(CoverEntity):
    """Cover entity for goggate2."""

    def __init__(
        self, config_entry: ConfigEntry, data_manager: DataManager, door: Door
    ) -> None:
        """Initialize the object."""
        self._api = data_manager.api
        self._door = door
        self._unique_id = cover_unique_id(config_entry, door)
        self._mid_state: Optional[str] = None
        self._mid_state_start: Optional[datetime] = None

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
        """Return the name of the garage door if any."""
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
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._mid_state == STATE_OPENING

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._mid_state == STATE_CLOSING

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
        self._mid_state = STATE_OPENING
        self._mid_state_start = datetime.now()

    async def async_close_cover(self, **kwargs):
        """Close the door."""
        await self.hass.async_add_executor_job(self._api.close_door, self._door.door_id)
        self._mid_state = STATE_CLOSING
        self._mid_state_start = datetime.now()

    @property
    def state_attributes(self):
        """Return the state attributes."""
        attrs = super().state_attributes
        attrs["door_id"] = self._door.door_id
        return attrs

    @callback
    def receive_data(self, state_data: StateData) -> None:
        """Receive data from data dispatcher."""
        if self._unique_id != state_data.unique_id:
            return

        if self._mid_state:
            is_mid_state_expired = (datetime.now() - self._mid_state_start) > timedelta(
                seconds=60
            )

            if is_mid_state_expired or self._door.status != state_data.door.status:
                self._mid_state = None
                self._mid_state_start = None

        self._door = state_data.door
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register update dispatcher."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DATA_UPDATED_SIGNAL, self.receive_data)
        )
