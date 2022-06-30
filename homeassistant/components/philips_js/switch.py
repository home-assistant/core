"""Philips TV menu switches."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PhilipsTVDataUpdateCoordinator
from .const import DOMAIN

HUE_POWER_OFF = "Off"
HUE_POWER_ON = "On"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the configuration entry."""
    coordinator: PhilipsTVDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities([PhilipsTVScreenSwitch(coordinator)])

    if coordinator.api.json_feature_supported("ambilight", "Hue"):
        async_add_entities([PhilipsTVAmbilightHueSwitch(coordinator)])


class PhilipsTVScreenSwitch(
    CoordinatorEntity[PhilipsTVDataUpdateCoordinator], SwitchEntity
):
    """A Philips TV screen state switch."""

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
    ) -> None:
        """Initialize entity."""

        super().__init__(coordinator)

        self._attr_name = f"{coordinator.system['name']} Screen State"
        self._attr_icon = "mdi:television-shimmer"
        self._attr_unique_id = f"{coordinator.unique_id}_screenstate"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, coordinator.unique_id),
            }
        )

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        if not super().available:
            return False
        if not self.coordinator.api.on:
            return False
        return self.coordinator.api.powerstate == "On"

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.coordinator.api.screenstate == "On"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.coordinator.api.setScreenState("On")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.api.setScreenState("Off")


class PhilipsTVAmbilightHueSwitch(
    CoordinatorEntity[PhilipsTVDataUpdateCoordinator], SwitchEntity
):
    """A Philips TV Ambi+Hue switch."""

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
    ) -> None:
        """Initialize entity."""

        super().__init__(coordinator)

        self._attr_name = f"{coordinator.system['name']} Ambilight+Hue"
        self._attr_icon = "mdi:television-ambient-light"
        self._attr_unique_id = f"{coordinator.unique_id}_ambi_hue"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, coordinator.unique_id),
            }
        )

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        if not super().available:
            return False
        if not self.coordinator.api.on:
            return False
        return self.coordinator.api.powerstate == "On"

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.coordinator.api.huelamp_power == HUE_POWER_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.coordinator.api.setHueLampPower(HUE_POWER_ON)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.api.setHueLampPower(HUE_POWER_OFF)
        self.async_write_ha_state()
