"""Demo platform that has two fake switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the demo switch platform."""
    async_add_entities(
        [
            DemoSwitch("switch1", "Decorative Lights", True, True),
            DemoSwitch(
                "switch2",
                "AC",
                False,
                False,
                translation_key="air_conditioner",
                device_class=SwitchDeviceClass.OUTLET,
            ),
        ]
    )


class DemoSwitch(SwitchEntity):
    """Representation of a demo switch."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        device_name: str,
        state: bool,
        assumed: bool,
        translation_key: str | None = None,
        device_class: SwitchDeviceClass | None = None,
    ) -> None:
        """Initialize the Demo switch."""
        self._attr_assumed_state = assumed
        self._attr_device_class = device_class
        self._attr_translation_key = translation_key
        self._attr_is_on = state
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._attr_is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._attr_is_on = False
        self.schedule_update_ha_state()
