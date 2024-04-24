"""Support for ISY lights."""

from __future__ import annotations

from typing import Any, cast

from pyisy.constants import ISY_VALUE_UNKNOWN
from pyisy.helpers import NodeProperty
from pyisy.nodes import Node

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import _LOGGER, CONF_RESTORE_LIGHT_STATE, DOMAIN, UOM_PERCENTAGE
from .entity import ISYNodeEntity
from .models import IsyData

ATTR_LAST_BRIGHTNESS = "last_brightness"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ISY light platform."""
    isy_data: IsyData = hass.data[DOMAIN][entry.entry_id]
    devices: dict[str, DeviceInfo] = isy_data.devices
    isy_options = entry.options
    restore_light_state = isy_options.get(CONF_RESTORE_LIGHT_STATE, False)

    async_add_entities(
        ISYLightEntity(node, restore_light_state, devices.get(node.primary_node))
        for node in isy_data.nodes[Platform.LIGHT]
    )


class ISYLightEntity(ISYNodeEntity, LightEntity, RestoreEntity):
    """Representation of an ISY light device."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        node: Node,
        restore_light_state: bool,
        device_info: DeviceInfo | None = None,
    ) -> None:
        """Initialize the ISY light device."""
        super().__init__(node, device_info=device_info)
        self._last_brightness: int | None = None
        self._restore_light_state = restore_light_state

    @property
    def is_on(self) -> bool:
        """Get whether the ISY light is on."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return False
        return int(self._node.status) != 0

    @property
    def brightness(self) -> int | None:
        """Get the brightness of the ISY light."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        # Special Case for ISY Z-Wave Devices using % instead of 0-255:
        if self._node.uom == UOM_PERCENTAGE:
            return round(cast(float, self._node.status) * 255.0 / 100.0)
        return int(self._node.status)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the turn off command to the ISY light device."""
        self._last_brightness = self.brightness
        if not await self._node.turn_off():
            _LOGGER.debug("Unable to turn off light")

    @callback
    def async_on_update(self, event: NodeProperty) -> None:
        """Save brightness in the update event from the ISY Node."""
        if self._node.status not in (0, ISY_VALUE_UNKNOWN):
            self._last_brightness = self._node.status
            if self._node.uom == UOM_PERCENTAGE:
                self._last_brightness = round(self._node.status * 255.0 / 100.0)
            else:
                self._last_brightness = self._node.status
        super().async_on_update(event)

    async def async_turn_on(self, brightness: int | None = None, **kwargs: Any) -> None:
        """Send the turn on command to the ISY light device."""
        if self._restore_light_state and brightness is None and self._last_brightness:
            brightness = self._last_brightness
        # Special Case for ISY Z-Wave Devices using % instead of 0-255:
        if brightness is not None and self._node.uom == UOM_PERCENTAGE:
            brightness = round(brightness * 100.0 / 255.0)
        if not await self._node.turn_on(val=brightness):
            _LOGGER.debug("Unable to turn on light")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the light attributes."""
        attribs = super().extra_state_attributes
        attribs[ATTR_LAST_BRIGHTNESS] = self._last_brightness
        return attribs

    async def async_added_to_hass(self) -> None:
        """Restore last_brightness on restart."""
        await super().async_added_to_hass()

        self._last_brightness = self.brightness or 255
        if not (last_state := await self.async_get_last_state()):
            return

        if last_brightness := last_state.attributes.get(ATTR_LAST_BRIGHTNESS):
            self._last_brightness = last_brightness
