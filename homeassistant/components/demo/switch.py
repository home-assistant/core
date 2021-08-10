"""Demo platform that has two fake switches."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import DEVICE_DEFAULT_NAME

from . import DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the demo switches."""
    async_add_entities(
        [
            DemoSwitch("switch1", "Decorative Lights", True, None, True),
            DemoSwitch(
                "switch2",
                "AC",
                False,
                "mdi:air-conditioner",
                False,
                device_class="outlet",
            ),
        ]
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoSwitch(SwitchEntity):
    """Representation of a demo switch."""

    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        name: str,
        state: bool,
        icon: str | None,
        assumed: bool,
        device_class: str | None = None,
    ) -> None:
        """Initialize the Demo switch."""
        self._attr_assumed_state = assumed
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_is_on = state
        self._attr_name = name or DEVICE_DEFAULT_NAME
        self._attr_unique_id = unique_id

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
        }

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._attr_is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._attr_is_on = False
        self.schedule_update_ha_state()
