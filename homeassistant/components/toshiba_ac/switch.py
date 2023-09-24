"""Switch platform for the Toshiba AC integration."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
import logging
from typing import Any, Generic, TypeVar

from toshiba_ac.device import (
    ToshibaAcAirPureIon,
    ToshibaAcDevice,
    ToshibaAcFeatures,
    ToshibaAcMeritA,
    ToshibaAcStatus,
)

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)

from .const import DOMAIN
from .entity import ToshibaAcStateEntity
from .entity_description import ToshibaAcEnumEntityDescriptionMixin

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ToshibaAcSwitchDescription(SwitchEntityDescription):
    """Describe a Toshiba AC switch entity type."""

    device_class = SwitchDeviceClass.SWITCH
    off_icon: str | None = None

    async def async_turn_on(self, _device: ToshibaAcDevice):
        """Turn the switch on."""

    async def async_turn_off(self, _device: ToshibaAcDevice):
        """Turn the switch off."""

    def is_on(self, _device: ToshibaAcDevice):
        """Return True if the switch is on."""
        return False

    def is_supported(self, _features: ToshibaAcFeatures):
        """Return True if the switch is available.

        Called to determine if the switch should be created in the first place, and then
        later to determine if it should be available based on the current AC mode.
        """
        return False


TEnum = TypeVar("TEnum", bound=Enum)


@dataclass(kw_only=True)
class ToshibaAcEnumSwitchDescription(
    ToshibaAcSwitchDescription,
    ToshibaAcEnumEntityDescriptionMixin[TEnum],
    Generic[TEnum],
):
    """Describe a Toshiba AC switch that is controlled using an enum flag."""

    ac_on_value: TEnum | None = None
    ac_off_value: TEnum | None = None
    ac_attr_name: str = ""
    ac_attr_setter: str = ""

    async def async_turn_off(self, device: ToshibaAcDevice):
        """Turn the switch off."""
        await self.async_set_attr(device, self.ac_off_value)

    async def async_turn_on(self, device: ToshibaAcDevice):
        """Turn the switch on."""
        await self.async_set_attr(device, self.ac_on_value)

    def is_on(self, device: ToshibaAcDevice):
        """Return True if the switch is on."""
        return self.get_device_attr(device) == self.ac_on_value

    def is_supported(self, features: ToshibaAcFeatures):
        """Return True if the switch is available."""
        return self.ac_on_value in self.get_features_attr(features)


_SWITCH_DESCRIPTIONS: Sequence[ToshibaAcSwitchDescription] = [
    ToshibaAcEnumSwitchDescription(
        key="8_degc_mode",
        translation_key="8_degc_mode",
        icon="mdi:snowflake-melt",
        ac_attr_name="ac_merit_a",
        ac_on_value=ToshibaAcMeritA.HEATING_8C,
        ac_off_value=ToshibaAcMeritA.OFF,
    ),
    ToshibaAcEnumSwitchDescription(
        key="air_purifier",
        translation_key="air_purifier",
        icon="mdi:air-purifier",
        off_icon="mdi:air-purifier-off",
        ac_attr_name="ac_air_pure_ion",
        ac_on_value=ToshibaAcAirPureIon.ON,
        ac_off_value=ToshibaAcAirPureIon.OFF,
    ),
    ToshibaAcEnumSwitchDescription(
        key="eco_mode",
        translation_key="eco_mode",
        icon="mdi:eco",
        ac_attr_name="ac_merit_a",
        ac_on_value=ToshibaAcMeritA.ECO,
        ac_off_value=ToshibaAcMeritA.OFF,
    ),
    ToshibaAcEnumSwitchDescription(
        key="high_power_mode",
        translation_key="high_power_mode",
        icon="mdi:high-power",
        ac_attr_name="ac_merit_a",
        ac_on_value=ToshibaAcMeritA.HIGH_POWER,
        ac_off_value=ToshibaAcMeritA.OFF,
    ),
]


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add all sensors for passed config_entry in HA."""
    # The hub is loaded from the associated hass.data entry that was created in the
    # __init__.async_setup_entry function
    device_manager = hass.data[DOMAIN][config_entry.entry_id]
    new_entites = []

    devices: list[ToshibaAcDevice] = await device_manager.get_devices()
    for device in devices:
        for entity_description in _SWITCH_DESCRIPTIONS:
            if entity_description.is_supported(device.supported):
                new_entites.append(ToshibaAcSwitchEntity(device, entity_description))
            else:
                _LOGGER.info(
                    "AC device %s does not support %s",
                    device.name,
                    entity_description.key,
                )

    if new_entites:
        _LOGGER.info("Adding %d %s", len(new_entites), "switches")
        async_add_devices(new_entites)


class ToshibaAcSwitchEntity(ToshibaAcStateEntity, SwitchEntity):
    """Provides a switch entity based on a ToshibaAcSwitchDescription."""

    entity_description: ToshibaAcSwitchDescription
    _attr_has_entity_name = True

    def __init__(
        self, device: ToshibaAcDevice, entity_description: ToshibaAcSwitchDescription
    ) -> None:
        """Initialize the switch."""
        super().__init__(device)

        self.entity_description = entity_description
        self._attr_unique_id = f"{device.ac_unique_id}_{entity_description.key}"
        self.update_attrs()

    @property
    def available(self):
        """Return True if entity is available."""
        return (
            super().available
            and self._device.ac_status == ToshibaAcStatus.ON
            and self.entity_description.is_supported(
                self._device.supported.for_ac_mode(self._device.ac_mode)
            )
        )

    @property
    def icon(self):
        """Return the icon."""
        if self.entity_description.off_icon and not self.is_on:
            return self.entity_description.off_icon
        return super().icon

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        return self.entity_description.is_on(self._device)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.async_turn_off(self._device)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.async_turn_on(self._device)
