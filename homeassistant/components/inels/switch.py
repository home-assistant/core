"""iNELS switch entity."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from inelsmqtt.devices import Device
from inelsmqtt.utils.common import Bit, Relay, SimpleRelay

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import InelsConfigEntry
from .entity import InelsBaseEntity


@dataclass(frozen=True, kw_only=True)
class InelsSwitchEntityDescription(SwitchEntityDescription):
    """Class describing iNELS switch entities."""

    get_state_fn: Callable[[Device, int], Bit | SimpleRelay | Relay]
    alerts: list[str] | None = None
    placeholder_fn: Callable[[Device, int, bool], dict[str, str]]


SWITCH_TYPES = [
    InelsSwitchEntityDescription(
        key="bit",
        translation_key="bit",
        get_state_fn=lambda device, index: device.state.bit[index],
        placeholder_fn=lambda device, index, indexed: {
            "addr": f" {device.state.bit[index].addr}"
        },
    ),
    InelsSwitchEntityDescription(
        key="simple_relay",
        translation_key="simple_relay",
        get_state_fn=lambda device, index: device.state.simple_relay[index],
        placeholder_fn=lambda device, index, indexed: {
            "index": f" {index + 1}" if indexed else ""
        },
    ),
    InelsSwitchEntityDescription(
        key="relay",
        translation_key="relay",
        get_state_fn=lambda device, index: device.state.relay[index],
        alerts=["overflow"],
        placeholder_fn=lambda device, index, indexed: {
            "index": f" {index + 1}" if indexed else ""
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

        self._attr_unique_id = f"{self._attr_unique_id}_{unique_key}".lower()

        # Set translation placeholders
        self._attr_translation_placeholders = self.entity_description.placeholder_fn(
            self._device, self._index, self._switch_count > 1
        )

    def _check_alerts(self, current_state: Bit | SimpleRelay | Relay) -> None:
        """Check if there are active alerts and raise ServiceValidationError if found."""
        if self.entity_description.alerts and any(
            getattr(current_state, alert_key, None)
            for alert_key in self.entity_description.alerts
        ):
            raise ServiceValidationError("Cannot operate switch with active alerts")

    @property
    def is_on(self) -> bool | None:
        """Return if switch is on."""
        current_state = self.entity_description.get_state_fn(self._device, self._index)
        return current_state.is_on

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        current_state = self.entity_description.get_state_fn(self._device, self._index)
        self._check_alerts(current_state)
        current_state.is_on = False
        await self._device.set_ha_value(self._device.state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        current_state = self.entity_description.get_state_fn(self._device, self._index)
        self._check_alerts(current_state)
        current_state.is_on = True
        await self._device.set_ha_value(self._device.state)
