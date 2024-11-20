"""Demo platform that has some fake switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .device import async_create_device


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the demo switch platform."""
    async_create_device(
        hass,
        config_entry.entry_id,
        None,
        "n_ch_power_strip",
        {"number_of_sockets": "2"},
        "2_ch_power_strip",
    )

    async_add_entities(
        [
            DemoSwitch(
                unique_id="outlet_1",
                device_name="Outlet 1",
                entity_name=None,
                state=False,
                assumed=False,
                via_device="2_ch_power_strip",
            ),
            DemoSwitch(
                unique_id="outlet_2",
                device_name="Outlet 2",
                entity_name=None,
                state=True,
                assumed=False,
                via_device="2_ch_power_strip",
            ),
        ]
    )


class DemoSwitch(SwitchEntity):
    """Representation of a demo switch."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        *,
        unique_id: str,
        device_name: str,
        entity_name: str | None,
        state: bool,
        assumed: bool,
        translation_key: str | None = None,
        device_class: SwitchDeviceClass | None = None,
        via_device: str | None = None,
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
        if via_device:
            self._attr_device_info["via_device"] = (DOMAIN, via_device)
        self._attr_name = entity_name

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._attr_is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._attr_is_on = False
        self.schedule_update_ha_state()
