"""Support for Tuya (de)humidifiers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tuya_device_handlers.definition.humidifier import (
    TuyaHumidifierDefinition,
    get_default_definition,
)
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.humidifier import (
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityDescription,
    HumidifierEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .entity import TuyaEntity
from .util import ActionDPCodeNotFoundError


@dataclass(frozen=True)
class TuyaHumidifierEntityDescription(HumidifierEntityDescription):
    """Describe an Tuya (de)humidifier entity."""

    # DPCode, to use. If None, the key will be used as DPCode
    dpcode: DPCode | tuple[DPCode, ...] | None = None

    current_humidity: DPCode | None = None
    humidity: DPCode | None = None


HUMIDIFIERS: dict[DeviceCategory, TuyaHumidifierEntityDescription] = {
    DeviceCategory.CS: TuyaHumidifierEntityDescription(
        key=DPCode.SWITCH,
        dpcode=(DPCode.SWITCH, DPCode.SWITCH_SPRAY),
        current_humidity=DPCode.HUMIDITY_INDOOR,
        humidity=DPCode.DEHUMIDITY_SET_VALUE,
        device_class=HumidifierDeviceClass.DEHUMIDIFIER,
    ),
    DeviceCategory.JSQ: TuyaHumidifierEntityDescription(
        key=DPCode.SWITCH,
        dpcode=(DPCode.SWITCH, DPCode.SWITCH_SPRAY),
        current_humidity=DPCode.HUMIDITY_CURRENT,
        humidity=DPCode.HUMIDITY_SET,
        device_class=HumidifierDeviceClass.HUMIDIFIER,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya (de)humidifier dynamically through Tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya (de)humidifier."""
        entities: list[TuyaHumidifierEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if (description := HUMIDIFIERS.get(device.category)) and (
                definition := get_default_definition(
                    device,
                    switch_dpcode=description.dpcode or description.key,
                    current_humidity_dpcode=description.current_humidity,
                    humidity_dpcode=description.humidity,
                )
            ):
                entities.append(
                    TuyaHumidifierEntity(device, manager, description, definition)
                )
        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaHumidifierEntity(TuyaEntity, HumidifierEntity):
    """Tuya (de)humidifier Device."""

    entity_description: TuyaHumidifierEntityDescription
    _attr_name = None

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaHumidifierEntityDescription,
        definition: TuyaHumidifierDefinition,
    ) -> None:
        """Init Tuya (de)humidifier."""
        super().__init__(device, device_manager, description)

        self._current_humidity_wrapper = definition.current_humidity_wrapper
        self._mode_wrapper = definition.mode_wrapper
        self._switch_wrapper = definition.switch_wrapper
        self._target_humidity_wrapper = definition.target_humidity_wrapper

        # Determine humidity parameters
        if definition.target_humidity_wrapper:
            self._attr_min_humidity = round(
                definition.target_humidity_wrapper.min_value
            )
            self._attr_max_humidity = round(
                definition.target_humidity_wrapper.max_value
            )

        # Determine mode support and provided modes
        if definition.mode_wrapper:
            self._attr_supported_features |= HumidifierEntityFeature.MODES
            self._attr_available_modes = definition.mode_wrapper.options

    @property
    def is_on(self) -> bool | None:
        """Return the device is on or off."""
        return self._read_wrapper(self._switch_wrapper)

    @property
    def mode(self) -> str | None:
        """Return the current mode."""
        return self._read_wrapper(self._mode_wrapper)

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        return self._read_wrapper(self._target_humidity_wrapper)

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._read_wrapper(self._current_humidity_wrapper)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if self._switch_wrapper is None:
            raise ActionDPCodeNotFoundError(
                self.device,
                self.entity_description.dpcode or self.entity_description.key,
            )
        await self._async_send_wrapper_updates(self._switch_wrapper, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if self._switch_wrapper is None:
            raise ActionDPCodeNotFoundError(
                self.device,
                self.entity_description.dpcode or self.entity_description.key,
            )
        await self._async_send_wrapper_updates(self._switch_wrapper, False)

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        if self._target_humidity_wrapper is None:
            raise ActionDPCodeNotFoundError(
                self.device,
                self.entity_description.humidity,
            )
        await self._async_send_wrapper_updates(self._target_humidity_wrapper, humidity)

    async def async_set_mode(self, mode: str) -> None:
        """Set new target preset mode."""
        await self._async_send_wrapper_updates(self._mode_wrapper, mode)
