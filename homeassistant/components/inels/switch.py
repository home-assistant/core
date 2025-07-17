"""iNELS switch entity."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from inelsmqtt.devices import Device

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from . import InelsConfigEntry
from .const import ICON_SWITCH
from .entity import InelsBaseEntity


@dataclass(frozen=True, kw_only=True)
class InelsSwitchEntityDescription(SwitchEntityDescription):
    """Class describing iNELS switch entities."""

    icon: str = ICON_SWITCH
    value_fn: Callable[[Device, int], bool | None]
    set_fn: Callable[[Device, int, bool], None]
    get_state_fn: Callable[[Device, int], Any]
    get_last_state_fn: Callable[[Device, int], Any]
    alerts: list[tuple[str, str]] | None = None
    placeholder_fn: Callable[[Device, int, bool], dict[str, str]]


SWITCH_TYPES = [
    InelsSwitchEntityDescription(
        key="bit",
        translation_key="bit",
        value_fn=lambda device, index: device.state.bit[index].is_on,
        set_fn=lambda device, index, value: setattr(
            device.state.bit[index], "is_on", value
        ),
        get_state_fn=lambda device, index: device.state.bit[index],
        get_last_state_fn=lambda device, index: device.last_values.ha_value.bit[index],
        placeholder_fn=lambda device, index, indexed: {
            "addr": device.state.bit[index].addr
        },
    ),
    InelsSwitchEntityDescription(
        key="simple_relay",
        translation_key="simple_relay",
        value_fn=lambda device, index: device.state.simple_relay[index].is_on,
        set_fn=lambda device, index, value: setattr(
            device.state.simple_relay[index], "is_on", value
        ),
        get_state_fn=lambda device, index: device.state.simple_relay[index],
        get_last_state_fn=(
            lambda device, index: device.last_values.ha_value.simple_relay[index]
        ),
        placeholder_fn=lambda device, index, indexed: {
            "index": str(index + 1) if indexed else ""
        },
    ),
    InelsSwitchEntityDescription(
        key="relay",
        translation_key="relay",
        value_fn=lambda device, index: device.state.relay[index].is_on,
        set_fn=lambda device, index, value: setattr(
            device.state.relay[index], "is_on", value
        ),
        get_state_fn=lambda device, index: device.state.relay[index],
        get_last_state_fn=(
            lambda device, index: device.last_values.ha_value.relay[index]
        ),
        alerts=[("overflow", "Relay overflow in %s of %s")],
        placeholder_fn=lambda device, index, indexed: {
            "index": str(index + 1) if indexed else ""
        },
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InelsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Load iNELS switch."""
    entities: list[InelsSwitch] = []

    for device in entry.runtime_data.devices:
        for description in SWITCH_TYPES:
            if hasattr(device.state, description.key):
                switch_count = len(getattr(device.state, description.key))
                entities.extend(
                    InelsSwitch(
                        device=device,
                        description=description,
                        index=idx,
                        switch_count=switch_count,
                    )
                    for idx in range(switch_count)
                )

    async_add_entities(entities, False)


class InelsSwitch(InelsBaseEntity, SwitchEntity):
    """The platform class required by Home Assistant."""

    entity_description: InelsSwitchEntityDescription

    def __init__(
        self,
        device: Device,
        description: InelsSwitchEntityDescription,
        index: int = 0,
        switch_count: int = 1,
    ) -> None:
        """Initialize the switch."""
        super().__init__(device=device, key=description.key, index=index)
        self.entity_description = description
        self._switch_count = switch_count

        # Include index in unique_id for devices with multiple switches
        unique_key = f"{description.key}{index}" if index else description.key

        self._attr_unique_id = slugify(f"{self._attr_unique_id}_{unique_key}")

        # Set translation placeholders
        self._attr_translation_placeholders = self.entity_description.placeholder_fn(
            self._device, self._index, self._switch_count > 1
        )

    @property
    def available(self) -> bool:
        """Return entity availability."""
        if not self.entity_description.alerts:
            return super().available

        current_value = self.entity_description.get_state_fn(self._device, self._index)
        return (
            not any(
                getattr(current_value, alert_key, None)
                for alert_key, _ in self.entity_description.alerts
            )
            and super().available
        )

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        self._attr_is_on = self.entity_description.value_fn(self._device, self._index)

    @property
    def is_on(self) -> bool | None:
        """Return if switch is on."""
        return self.entity_description.value_fn(self._device, self._index)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        self.entity_description.set_fn(self._device, self._index, False)
        await self.hass.async_add_executor_job(
            self._device.set_ha_value, self._device.state
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        self.entity_description.set_fn(self._device, self._index, True)
        await self.hass.async_add_executor_job(
            self._device.set_ha_value, self._device.state
        )
