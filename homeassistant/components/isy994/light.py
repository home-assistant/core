"""Support for ISY994 lights."""
from typing import Callable, Dict

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.light import (
    DOMAIN as LIGHT,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    _LOGGER,
    CONF_RESTORE_LIGHT_STATE,
    DOMAIN as ISY994_DOMAIN,
    ISY994_NODES,
)
from .entity import ISYNodeEntity
from .helpers import migrate_old_unique_ids
from .services import async_setup_device_services, async_setup_light_services

ATTR_LAST_BRIGHTNESS = "last_brightness"


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[list], None],
) -> bool:
    """Set up the ISY994 light platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    isy_options = entry.options
    restore_light_state = isy_options.get(CONF_RESTORE_LIGHT_STATE, False)

    devices = []
    for node in hass_isy_data[ISY994_NODES][LIGHT]:
        devices.append(ISYLightEntity(node, restore_light_state))

    await migrate_old_unique_ids(hass, LIGHT, devices)
    async_add_entities(devices)
    async_setup_device_services(hass)
    async_setup_light_services(hass)


class ISYLightEntity(ISYNodeEntity, LightEntity, RestoreEntity):
    """Representation of an ISY994 light device."""

    def __init__(self, node, restore_light_state) -> None:
        """Initialize the ISY994 light device."""
        super().__init__(node)
        self._last_brightness = None
        self._restore_light_state = restore_light_state

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 light is on."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return False
        return int(self._node.status) != 0

    @property
    def brightness(self) -> float:
        """Get the brightness of the ISY994 light."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return int(self._node.status)

    def turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 light device."""
        self._last_brightness = self.brightness
        if not self._node.turn_off():
            _LOGGER.debug("Unable to turn off light")

    def on_update(self, event: object) -> None:
        """Save brightness in the update event from the ISY994 Node."""
        if self._node.status not in (0, ISY_VALUE_UNKNOWN):
            self._last_brightness = self._node.status
        super().on_update(event)

    # pylint: disable=arguments-differ
    def turn_on(self, brightness=None, **kwargs) -> None:
        """Send the turn on command to the ISY994 light device."""
        if self._restore_light_state and brightness is None and self._last_brightness:
            brightness = self._last_brightness
        if not self._node.turn_on(val=brightness):
            _LOGGER.debug("Unable to turn on light")

    @property
    def device_state_attributes(self) -> Dict:
        """Return the light attributes."""
        attribs = super().device_state_attributes
        attribs[ATTR_LAST_BRIGHTNESS] = self._last_brightness
        return attribs

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    async def async_added_to_hass(self) -> None:
        """Restore last_brightness on restart."""
        await super().async_added_to_hass()

        self._last_brightness = self.brightness or 255
        last_state = await self.async_get_last_state()
        if not last_state:
            return

        if (
            ATTR_LAST_BRIGHTNESS in last_state.attributes
            and last_state.attributes[ATTR_LAST_BRIGHTNESS]
        ):
            self._last_brightness = last_state.attributes[ATTR_LAST_BRIGHTNESS]

    def set_on_level(self, value):
        """Set the ON Level for a device."""
        self._node.set_on_level(value)

    def set_ramp_rate(self, value):
        """Set the Ramp Rate for a device."""
        self._node.set_ramp_rate(value)
