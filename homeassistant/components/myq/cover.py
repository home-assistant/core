"""Support for MyQ-Enabled Garage Doors."""
import logging

from pymyq.const import DEVICE_TYPE_GATE as MYQ_DEVICE_TYPE_GATE
from pymyq.errors import MyQError

from homeassistant.components.cover import (
    DEVICE_CLASS_GARAGE,
    DEVICE_CLASS_GATE,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverEntity,
)
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING
from homeassistant.exceptions import HomeAssistantError

from . import MyQEntity
from .const import DOMAIN, MYQ_COORDINATOR, MYQ_GATEWAY, MYQ_TO_HASS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up mysq covers."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    myq = data[MYQ_GATEWAY]
    coordinator = data[MYQ_COORDINATOR]

    async_add_entities(
        [MyQCover(coordinator, device) for device in myq.covers.values()]
    )


class MyQCover(MyQEntity, CoverEntity):
    """Representation of a MyQ cover."""

    _attr_supported_features = SUPPORT_OPEN | SUPPORT_CLOSE

    def __init__(self, coordinator, device):
        """Initialize with API object, device id."""
        super().__init__(coordinator, device)
        self._device = device
        if device.device_type == MYQ_DEVICE_TYPE_GATE:
            self._attr_device_class = DEVICE_CLASS_GATE
        else:
            self._attr_device_class = DEVICE_CLASS_GARAGE
        self._attr_unique_id = device.device_id

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_CLOSED

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_CLOSING

    @property
    def is_open(self):
        """Return if the cover is opening or not."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_OPEN

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_OPENING

    async def async_close_cover(self, **kwargs):
        """Issue close command to cover."""
        if self.is_closing or self.is_closed:
            return

        try:
            wait_task = await self._device.close(wait_for_state=False)
        except MyQError as err:
            raise HomeAssistantError(
                f"Closing of cover {self._device.name} failed with error: {err}"
            ) from err

        # Write closing state to HASS
        self.async_write_ha_state()

        result = wait_task if isinstance(wait_task, bool) else await wait_task

        # Write final state to HASS
        self.async_write_ha_state()

        if not result:
            raise HomeAssistantError(f"Closing of cover {self._device.name} failed")

    async def async_open_cover(self, **kwargs):
        """Issue open command to cover."""
        if self.is_opening or self.is_open:
            return

        try:
            wait_task = await self._device.open(wait_for_state=False)
        except MyQError as err:
            raise HomeAssistantError(
                f"Opening of cover {self._device.name} failed with error: {err}"
            ) from err

        # Write opening state to HASS
        self.async_write_ha_state()

        result = wait_task if isinstance(wait_task, bool) else await wait_task

        # Write final state to HASS
        self.async_write_ha_state()

        if not result:
            raise HomeAssistantError(f"Opening of cover {self._device.name} failed")
