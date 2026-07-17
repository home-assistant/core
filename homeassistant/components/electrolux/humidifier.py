"""Humidifier entity for Electrolux Integration."""

import logging
from typing import Any, override

from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.dh_appliance import DHAppliance

from homeassistant.components.humidifier import (
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper

_LOGGER = logging.getLogger(__name__)


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return all entities for a single appliance."""
    appliance = appliance_data.appliance
    coordinator = coordinators[appliance.applianceId]
    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, DHAppliance):
        entities.append(
            DehumidifierEntity(appliance_data=appliance_data, coordinator=coordinator)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set Dehumidifier entity for Electrolux Integration."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class DehumidifierEntity(ElectroluxBaseEntity[DHAppliance], HumidifierEntity):
    """Representation of an Electrolux Dehumidifier unit."""

    _attr_supported_features = HumidifierEntityFeature.MODES

    def __init__(
        self,
        appliance_data: DHAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize the Dehumidifier device."""
        super().__init__(appliance_data, coordinator, "dehumidifier")

        self._attr_key = "dehumidifier"
        self._attr_translation_key = "dehumidifier"
        self._attr_available_modes = self._get_supported_modes()
        self._attr_max_humidity = (
            self._appliance_data.get_supported_max_humidity() or 85
        )
        self._attr_min_humidity = (
            self._appliance_data.get_supported_min_humidity() or 35
        )
        self._humidity_step = self._appliance_data.get_supported_step_humidity() or 5
        self._attr_device_class = HumidifierDeviceClass.DEHUMIDIFIER

        self._attr_mode = self._get_current_mode()
        self._attr_current_humidity = self._get_sensor_humidity()
        self._attr_target_humidity = self._get_target_humidity()
        self._attr_is_on = self._is_dh_on()

    @override
    def _update_attr_state(self) -> bool:
        state_changed = False

        new_mode = self._get_current_mode()
        if new_mode != self._attr_mode:
            self._attr_mode = new_mode
            state_changed = True

        new_humidity = self._get_sensor_humidity()
        if new_humidity != self._attr_current_humidity:
            self._attr_current_humidity = new_humidity
            state_changed = True

        new_target_humidity = self._get_target_humidity()
        if new_target_humidity != self._attr_target_humidity:
            self._attr_target_humidity = new_target_humidity
            state_changed = True

        new_on_state = self._is_dh_on()
        if new_on_state != self._attr_is_on:
            self._attr_is_on = new_on_state
            state_changed = True

        return state_changed

    def _get_supported_modes(self) -> list[str]:
        supported_modes = self._appliance_data.get_supported_modes()
        if not supported_modes:
            return []
        return list(supported_modes)

    def _get_current_mode(self) -> str:
        """Return current mode."""
        return self._appliance_data.get_current_mode()

    def _get_target_humidity(self) -> int:
        """Return target humidity."""
        return self._appliance_data.get_current_target_humidity() or 0

    def _get_sensor_humidity(self) -> int:
        """Return sensor humidity."""
        return self._appliance_data.get_current_sensor_humidity() or 0

    def _is_dh_on(self) -> bool:
        """Return true if the DH is on."""
        return self._appliance_data.is_appliance_on() or False

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        command = self._appliance_data.get_turn_off_command()

        await self.coordinator.client.send_command(self._appliance_id, command)
        await self.coordinator.async_refresh()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        command = self._appliance_data.get_turn_on_command()
        await self.coordinator.client.send_command(self._appliance_id, command)
        await self.coordinator.async_refresh()

    @override
    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        rounded_humidity = int(
            round(humidity / self._humidity_step) * self._humidity_step
        )
        command = self._appliance_data.get_humidity_command(rounded_humidity)
        await self.coordinator.client.send_command(self._appliance_id, command)
        await self.coordinator.async_refresh()

    @override
    async def async_set_mode(self, mode: str) -> None:
        """Set new target preset mode."""
        command = self._appliance_data.get_mode_command(mode)
        await self.coordinator.client.send_command(self._appliance_id, command)
        await self.coordinator.async_refresh()
