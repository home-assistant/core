"""iNELS switch entity."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inelsmqtt.const import (  # Inels types
    RC3_610DALI,
    RFSC_61,
    SA3_01B,
    SA3_02B,
    SA3_02M,
    SA3_04M,
    SA3_06M,
    SA3_012M,
)
from inelsmqtt.devices import Device

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import InelsBaseEntity
from .const import DEVICES, DOMAIN, ICON_SWITCH, LOGGER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load iNELS switch.."""
    device_list: list[Device] = hass.data[DOMAIN][config_entry.entry_id][DEVICES]

    entities: list[InelsBaseEntity] = []
    for device in device_list:
        if device.device_type == Platform.SWITCH:
            if device.inels_type == RFSC_61:
                entities.append(InelsSwitch(device=device))
            elif device.inels_type == SA3_01B:
                entities.append(InelsSwitch(device=device))
            elif device.inels_type in [
                SA3_02B,
                SA3_02M,
                SA3_04M,
                SA3_06M,
                SA3_012M,
                RC3_610DALI,
            ]:
                if len(device.state.re) == 1:
                    entities.append(
                        InelsBusSwitch(
                            device=device,
                            description=InelsSwitchEntityDescription(
                                key="re",
                                name="Relay",
                                icon=ICON_SWITCH,
                                index=0,
                            ),
                        )
                    )
                for k in range(len(device.state.temps)):
                    entities.append(
                        InelsBusSwitch(
                            device=device,
                            description=InelsSwitchEntityDescription(
                                key=f"re{k}",
                                name=f"Relay {k+1}",
                                icon=ICON_SWITCH,
                                index=k,
                            ),
                        )
                    )
    async_add_entities(entities, False)


class InelsSwitch(InelsBaseEntity, SwitchEntity):
    """The platform class required by Home Assistant."""

    def __init__(self, device: Device) -> None:
        """Initialize a switch."""
        super().__init__(device=device)

    @property
    def available(self) -> bool:
        """Return entity availability."""
        if "relay_overflow" in self._device.state.__dict__:
            return super().available and not self._device.state.relay_overflow
        return super().available

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""

        state = self._device.state
        return state.on

    @property
    def icon(self) -> str | None:
        """Switch icon."""
        return ICON_SWITCH

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        if not self._device.is_available:
            return None

        ha_val = self._device.get_value().ha_value
        ha_val.on = False
        await self.hass.async_add_executor_job(self._device.set_ha_value, ha_val)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        if not self._device.is_available:
            return None

        ha_val = self._device.get_value().ha_value
        ha_val.on = True
        await self.hass.async_add_executor_job(self._device.set_ha_value, ha_val)


@dataclass
class InelsSwitchEntityDescription(SwitchEntityDescription):
    """Class for description inels entities."""

    index: int | None = None
    name: str | None = None


class InelsBusSwitch(InelsBaseEntity, SwitchEntity):
    """The platform class required by Home Assistant, bus version."""

    entity_description: InelsSwitchEntityDescription

    def __init__(
        self, device: Device, description: InelsSwitchEntityDescription
    ) -> None:
        """Initialize a bus switch."""
        super().__init__(device=device)

        self.entity_description = description

        self._attr_unique_id = f"{self._attr_unique_id}-{description.key}"
        self._attr_name = f"{self._attr_name} {description.name}"

    @property
    def available(self) -> bool:
        """Return entity availability."""
        if "relay_overflow" in self._device.state.__dict__:
            if self._device.state.relay_overflow[self.entity_description.index]:
                LOGGER.warning(
                    "Relay overflow in relay %d of %d",
                    self.entity_description.key,
                    self._device_id,
                )
                return False
            return super().available
        return super().available

    @property
    def is_on(self) -> bool | None:
        """Return if switch is on."""
        state = self._device.state
        return state.re[self.entity_description.index]

    @property
    def icon(self) -> str | None:
        """Switch icon."""
        return ICON_SWITCH

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        if not self._device.is_available:
            return None

        ha_val = self._device.get_value().ha_value
        ha_val.re[self.entity_description.index] = False

        await self.hass.async_add_executor_job(self._device.set_ha_value, ha_val)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        if not self._device.is_available:
            return None

        ha_val = self._device.get_value().ha_value
        ha_val.re[self.entity_description.index] = True

        await self.hass.async_add_executor_job(self._device.set_ha_value, ha_val)
