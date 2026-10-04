"""Philips TV menu switches."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import TV_STATE_OFF, TV_STATE_ON
from .coordinator import PhilipsTVConfigEntry, PhilipsTVDataUpdateCoordinator
from .entity import PhilipsJsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PhilipsTVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the configuration entry."""
    coordinator = config_entry.runtime_data

    async_add_entities([PhilipsTVScreenSwitch(coordinator)])

    if coordinator.api.json_feature_supported("ambilight", "Hue"):
        async_add_entities([PhilipsTVAmbilightHueSwitch(coordinator)])


class PhilipsTVScreenSwitch(PhilipsJsEntity, SwitchEntity):
    """A Philips TV screen state switch."""

    _attr_translation_key = "screen_state"

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
    ) -> None:
        """Initialize entity."""

        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.unique_id}_screenstate"

    @property
    @override
    def available(self) -> bool:
        """Return true if entity is available."""
        if not super().available:
            return False
        if not self.coordinator.api.on:
            return False
        return self.coordinator.api.powerstate in (TV_STATE_ON, None)

    @property
    @override
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.coordinator.api.screenstate == TV_STATE_ON

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.coordinator.api.setScreenState(TV_STATE_ON)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.api.setScreenState(TV_STATE_OFF)


class PhilipsTVAmbilightHueSwitch(PhilipsJsEntity, SwitchEntity):
    """A Philips TV Ambi+Hue switch."""

    _attr_translation_key = "ambilight_hue"

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
    ) -> None:
        """Initialize entity."""

        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.unique_id}_ambi_hue"

    @property
    @override
    def available(self) -> bool:
        """Return true if entity is available."""
        if not super().available:
            return False
        if not self.coordinator.api.on:
            return False
        return self.coordinator.api.powerstate in (TV_STATE_ON, None)

    @property
    @override
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.coordinator.api.huelamp_power == TV_STATE_ON

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.coordinator.api.setHueLampPower(TV_STATE_ON)
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.api.setHueLampPower(TV_STATE_OFF)
        self.async_write_ha_state()
