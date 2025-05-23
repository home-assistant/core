"""iNELS switch entity."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from inelsmqtt.devices import Device

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from . import InelsConfigEntry
from .const import ICON_SWITCH, LOGGER
from .entity import InelsBaseEntity


@dataclass(frozen=True, kw_only=True)
class InelsSwitchEntityDescription(SwitchEntityDescription):
    """Class describing iNELS switch entities."""

    icon: str = ICON_SWITCH
    name: str | None = None
    value_fn: Callable[[Device, int], bool | None]
    set_fn: Callable[[Device, int, bool], None]
    name_fn: Callable[[Device, str, int | None], str]
    get_state_fn: Callable[[Device, int], Any]
    get_last_state_fn: Callable[[Device, int], Any]
    alerts: list[tuple[str, str]] | None = None


SWITCH_TYPES = [
    InelsSwitchEntityDescription(
        key="bit",
        value_fn=lambda device, index: device.state.bit[index].is_on,
        set_fn=lambda device, index, value: setattr(
            device.state.bit[index], "is_on", value
        ),
        name_fn=lambda device, key, index: f"{key} {device.state.bit[index].addr}",
        get_state_fn=lambda device, index: device.state.bit[index],
        get_last_state_fn=lambda device, index: device.last_values.ha_value.bit[index],
    ),
    InelsSwitchEntityDescription(
        key="simple_relay",
        value_fn=lambda device, index: device.state.simple_relay[index].is_on,
        set_fn=lambda device, index, value: setattr(
            device.state.simple_relay[index], "is_on", value
        ),
        name_fn=(
            lambda device, key, index: key if index is None else f"{key} {index + 1}"
        ),
        get_state_fn=lambda device, index: device.state.simple_relay[index],
        get_last_state_fn=(
            lambda device, index: device.last_values.ha_value.simple_relay[index]
        ),
    ),
    InelsSwitchEntityDescription(
        key="relay",
        value_fn=lambda device, index: device.state.relay[index].is_on,
        set_fn=lambda device, index, value: setattr(
            device.state.relay[index], "is_on", value
        ),
        name_fn=(
            lambda device, key, index: key if index is None else f"{key} {index + 1}"
        ),
        get_state_fn=lambda device, index: device.state.relay[index],
        get_last_state_fn=(
            lambda device, index: device.last_values.ha_value.relay[index]
        ),
        alerts=[("overflow", "Relay overflow in %s of %s")],
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
                values_cnt = len(getattr(device.state, description.key))
                for idx in range(values_cnt):
                    name = description.name_fn(
                        device,
                        description.key,
                        None if values_cnt == 1 else idx,
                    )
                    entity_description = replace(description, name=name)
                    entities.append(
                        InelsSwitch(
                            device=device,
                            description=entity_description,
                            index=idx,
                        )
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
    ) -> None:
        """Initialize the switch."""
        super().__init__(device=device, key=description.key, index=index)
        self.entity_description = description

        # Include index in unique_id for devices with multiple switches
        unique_key = f"{description.key}{index}" if index else description.key

        self._attr_unique_id = slugify(f"{self._attr_unique_id}_{unique_key}")
        self._attr_name = description.name

    @property
    def available(self) -> bool:
        """Return entity availability."""
        if self.entity_description.alerts:
            try:
                last_state = self.entity_description.get_last_state_fn(
                    self._device, self._index
                )
            except (KeyError, IndexError, AttributeError):
                last_state = None

            current_value = self.entity_description.get_state_fn(
                self._device, self._index
            )
            for alert_key, alert_msg in self.entity_description.alerts:
                if getattr(current_value, alert_key, None):
                    if not last_state or not getattr(last_state, alert_key, None):
                        LOGGER.warning(alert_msg, self.name, self._device.state_topic)
                    return False
        return super().available

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
