"""Cover Platform for the Somfy MyLink component."""
import logging

from homeassistant.components.cover import (
    DEVICE_CLASS_BLIND,
    DEVICE_CLASS_SHUTTER,
    DEVICE_CLASS_WINDOW,
    CoverEntity,
)
from homeassistant.const import STATE_CLOSED, STATE_OPEN
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_REVERSED_TARGET_IDS,
    DATA_SOMFY_MYLINK,
    DOMAIN,
    MANUFACTURER,
    MYLINK_STATUS,
)

_LOGGER = logging.getLogger(__name__)

MYLINK_COVER_TYPE_TO_DEVICE_CLASS = {0: DEVICE_CLASS_BLIND, 1: DEVICE_CLASS_SHUTTER}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Discover and configure Somfy covers."""
    reversed_target_ids = config_entry.options.get(CONF_REVERSED_TARGET_IDS, {})

    data = hass.data[DOMAIN][config_entry.entry_id]
    mylink_status = data[MYLINK_STATUS]
    somfy_mylink = data[DATA_SOMFY_MYLINK]
    cover_list = []

    for cover in mylink_status["result"]:
        cover_config = {
            "target_id": cover["targetID"],
            "name": cover["name"],
            "device_class": MYLINK_COVER_TYPE_TO_DEVICE_CLASS.get(
                cover.get("type"), DEVICE_CLASS_WINDOW
            ),
            "reverse": reversed_target_ids.get(cover["targetID"], False),
        }

        cover_list.append(SomfyShade(somfy_mylink, **cover_config))

        _LOGGER.info(
            "Adding Somfy Cover: %s with targetID %s",
            cover_config["name"],
            cover_config["target_id"],
        )

    async_add_entities(cover_list)


class SomfyShade(RestoreEntity, CoverEntity):
    """Object for controlling a Somfy cover."""

    def __init__(
        self,
        somfy_mylink,
        target_id,
        name="SomfyShade",
        reverse=False,
        device_class=DEVICE_CLASS_WINDOW,
    ):
        """Initialize the cover."""
        self.somfy_mylink = somfy_mylink
        self._target_id = target_id
        self._name = name
        self._reverse = reverse
        self._closed = None
        self._is_opening = None
        self._is_closing = None
        self._device_class = device_class

    @property
    def should_poll(self):
        """No polling since assumed state."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of this cover."""
        return self._target_id

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def assumed_state(self):
        """Let HA know the integration is assumed state."""
        return True

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def is_opening(self):
        """Return if the cover is opening."""
        return self._is_opening

    @property
    def is_closing(self):
        """Return if the cover is closing."""
        return self._is_closing

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return self._closed

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._target_id)},
            "name": self._name,
            "manufacturer": MANUFACTURER,
        }

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        self._is_closing = True
        self.async_write_ha_state()
        try:
            # Blocks until the close command is sent
            if not self._reverse:
                await self.somfy_mylink.move_down(self._target_id)
            else:
                await self.somfy_mylink.move_up(self._target_id)
            self._closed = True
        finally:
            self._is_closing = None
            self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self._is_opening = True
        self.async_write_ha_state()
        try:
            # Blocks until the open command is sent
            if not self._reverse:
                await self.somfy_mylink.move_up(self._target_id)
            else:
                await self.somfy_mylink.move_down(self._target_id)
            self._closed = False
        finally:
            self._is_opening = None
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self.somfy_mylink.move_stop(self._target_id)

    async def async_added_to_hass(self):
        """Complete the initialization."""
        await super().async_added_to_hass()
        # Restore the last state
        last_state = await self.async_get_last_state()

        if last_state is not None and last_state.state in (
            STATE_OPEN,
            STATE_CLOSED,
        ):
            self._closed = last_state.state == STATE_CLOSED
