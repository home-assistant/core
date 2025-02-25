"""iNELS switch entity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inelsmqtt.devices import Device

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from . import InelsConfigEntry
from .const import ICON_SWITCH, LOGGER
from .entity import InelsBaseEntity


# SWITCH PLATFORM
@dataclass
class InelsSwitchAlert:
    """Inels switch alert property description."""

    key: str
    message: str


relay_overflow = InelsSwitchAlert(key="overflow", message="Relay overflow in %s of %s")


@dataclass
class InelsSwitchType:
    """Inels switch property description."""

    name: str = "Relay"
    icon: str = ICON_SWITCH
    alerts: list[InelsSwitchAlert] | None = None


INELS_SWITCH_TYPES: dict[str, InelsSwitchType] = {
    "bit": InelsSwitchType(),
    "simple_relay": InelsSwitchType(),
    "relay": InelsSwitchType(alerts=[relay_overflow]),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InelsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Load iNELS switch.."""

    items = INELS_SWITCH_TYPES.items()
    entities: list[InelsBaseEntity] = []
    for device in entry.runtime_data.devices:
        for key, type_dict in items:
            if hasattr(device.state, key):
                if len(device.state.__dict__[key]) == 1:
                    entities.append(
                        InelsBusSwitch(
                            device=device,
                            key=key,
                            index=0,
                            description=InelsSwitchEntityDescription(
                                key=key,
                                name=type_dict.name,
                                icon=type_dict.icon,
                                alerts=getattr(type_dict, "alerts", None),
                            ),
                        )
                    )
                else:
                    entities.extend(
                        [
                            InelsBusSwitch(
                                device=device,
                                key=key,
                                index=k,
                                description=InelsSwitchEntityDescription(
                                    key=f"{key}{k}",
                                    name=f"{type_dict.name} {k + 1}"
                                    if device.inels_type != "BITS"
                                    else f"Bit {device.state.__dict__[key][k].addr}",
                                    icon=type_dict.icon,
                                    alerts=getattr(type_dict, "alerts", None),
                                ),
                            )
                            for k in range(len(device.state.__dict__[key]))
                        ]
                    )
    async_add_entities(entities, False)


@dataclass(frozen=True)
class InelsSwitchEntityDescription(SwitchEntityDescription):
    """Class for description inels entities."""

    name: str | None
    alerts: list[InelsSwitchAlert] | None = None


class InelsBusSwitch(InelsBaseEntity, SwitchEntity):
    """The platform class required by Home Assistant, bus version."""

    entity_description: InelsSwitchEntityDescription

    def __init__(
        self,
        device: Device,
        key: str,
        index: int,
        description: InelsSwitchEntityDescription,
    ) -> None:
        """Initialize a bus switch."""
        super().__init__(device=device, key=key, index=index)

        self.entity_description = description

        self._attr_unique_id = slugify(f"{self._attr_unique_id}_{description.key}")
        self._attr_name = description.name

    @property
    def available(self) -> bool:
        """Return entity availability."""
        if self.entity_description.alerts:
            try:
                last_state = self._device.last_values.ha_value.__dict__[self.key][
                    self.index
                ]
            except (KeyError, IndexError, AttributeError):
                last_state = None

            for alert in self.entity_description.alerts:
                if getattr(
                    self._device.state.__dict__[self.key][self.index], alert.key, None
                ):
                    if not last_state or not getattr(last_state, alert.key):
                        LOGGER.warning(
                            alert.message, self.name, self._device.state_topic
                        )
                    return False
        return super().available

    @property
    def is_on(self) -> bool | None:
        """Return if switch is on."""
        state: bool | None = self._device.state.__dict__[self._key][self._index].is_on
        return state

    @property
    def icon(self) -> str | None:
        """Switch icon."""
        return self.entity_description.icon

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        if not self._device.is_available:
            return

        ha_val = self._device.state
        ha_val.__dict__[self.key][self.index].is_on = False

        await self.hass.async_add_executor_job(self._device.set_ha_value, ha_val)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        if not self._device.is_available:
            return

        ha_val = self._device.state
        ha_val.__dict__[self.key][self.index].is_on = True

        await self.hass.async_add_executor_job(self._device.set_ha_value, ha_val)
