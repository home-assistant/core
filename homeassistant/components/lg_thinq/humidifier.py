"""Support for humidifier entities."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from thinqconnect import DeviceType
from thinqconnect.devices.const import Property as ThinQProperty
from thinqconnect.integration import ActiveMode

from homeassistant.components.humidifier import (
    HumidifierAction,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityDescription,
    HumidifierEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ThinqConfigEntry
from .coordinator import DeviceDataUpdateCoordinator
from .entity import ThinQEntity


@dataclass(frozen=True, kw_only=True)
class ThinQHumidifierEntityDescription(HumidifierEntityDescription):
    """Describes ThinQ humidifier entity."""

    current_humidity_key: str
    operation_key: str
    mode_key: str = ThinQProperty.CURRENT_JOB_MODE


DEVICE_TYPE_HUM_MAP: dict[DeviceType, ThinQHumidifierEntityDescription] = {
    DeviceType.DEHUMIDIFIER: ThinQHumidifierEntityDescription(
        key=ThinQProperty.TARGET_HUMIDITY,
        name=None,
        device_class=HumidifierDeviceClass.DEHUMIDIFIER,
        translation_key="dehumidifier",
        current_humidity_key=ThinQProperty.CURRENT_HUMIDITY,
        operation_key=ThinQProperty.DEHUMIDIFIER_OPERATION_MODE,
    ),
    DeviceType.HUMIDIFIER: ThinQHumidifierEntityDescription(
        key=ThinQProperty.TARGET_HUMIDITY,
        name=None,
        device_class=HumidifierDeviceClass.HUMIDIFIER,
        translation_key="humidifier",
        current_humidity_key=ThinQProperty.HUMIDITY,
        operation_key=ThinQProperty.HUMIDIFIER_OPERATION_MODE,
    ),
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an entry for humidifier platform."""
    entities: list[ThinQHumidifierEntity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        if (
            description := DEVICE_TYPE_HUM_MAP.get(coordinator.api.device.device_type)
        ) is not None:
            entities.extend(
                ThinQHumidifierEntity(coordinator, description, property_id)
                for property_id in coordinator.api.get_active_idx(
                    description.key, ActiveMode.READ_WRITE
                )
            )

    if entities:
        async_add_entities(entities)


class ThinQHumidifierEntity(ThinQEntity, HumidifierEntity):
    """Represent a ThinQ humidifier entity."""

    entity_description: ThinQHumidifierEntityDescription
    _attr_supported_features = HumidifierEntityFeature.MODES

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        entity_description: ThinQHumidifierEntityDescription,
        property_id: str,
    ) -> None:
        """Initialize a humidifier entity."""
        super().__init__(coordinator, entity_description, property_id)
        self._attr_available_modes = self.coordinator.data[
            self.entity_description.mode_key
        ].options

        if self.data.max is not None:
            self._attr_max_humidity = self.data.max
        if self.data.min is not None:
            self._attr_min_humidity = self.data.min
        self._attr_target_humidity_step = (
            self.data.step if self.data.step is not None else 1
        )

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        self._attr_target_humidity = self.data.value
        self._attr_current_humidity = self.coordinator.data[
            self.entity_description.current_humidity_key
        ].value
        self._attr_is_on = self.coordinator.data[
            self.entity_description.operation_key
        ].is_on
        self._attr_mode = self.coordinator.data[self.entity_description.mode_key].value
        if self.is_on:
            self._attr_action = (
                HumidifierAction.DRYING
                if self.entity_description.device_class
                == HumidifierDeviceClass.DEHUMIDIFIER
                else HumidifierAction.HUMIDIFYING
            )
        else:
            self._attr_action = HumidifierAction.OFF

        _LOGGER.debug(
            "[%s:%s] update status: c:%s, t:%s, mode:%s, action:%s, is_on:%s",
            self.coordinator.device_name,
            self.property_id,
            self.current_humidity,
            self.target_humidity,
            self.mode,
            self.action,
            self.is_on,
        )

    async def async_set_mode(self, mode: str) -> None:
        """Set new target preset mode."""
        _LOGGER.debug(
            "[%s:%s] async_set_mode: %s",
            self.coordinator.device_name,
            self.entity_description.mode_key,
            mode,
        )
        await self.async_call_api(
            self.coordinator.api.post(self.entity_description.mode_key, mode)
        )

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        _target_humidity = round(humidity / (self.target_humidity_step or 1)) * (
            self.target_humidity_step or 1
        )
        _LOGGER.debug(
            "[%s:%s] async_set_humidity: %s, target_humidity: %s, step: %s",
            self.coordinator.device_name,
            self.property_id,
            humidity,
            _target_humidity,
            self.target_humidity_step,
        )
        if _target_humidity == self.target_humidity:
            return
        await self.async_call_api(
            self.coordinator.api.post(self.property_id, _target_humidity)
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if self.is_on:
            return
        _LOGGER.debug(
            "[%s:%s] async_turn_on",
            self.coordinator.device_name,
            self.entity_description.operation_key,
        )
        await self.async_call_api(
            self.coordinator.api.async_turn_on(self.entity_description.operation_key)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        if not self.is_on:
            return
        _LOGGER.debug(
            "[%s:%s] async_turn_off",
            self.coordinator.device_name,
            self.entity_description.operation_key,
        )
        await self.async_call_api(
            self.coordinator.api.async_turn_off(self.entity_description.operation_key)
        )
