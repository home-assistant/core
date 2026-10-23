"""Base entities for the BLUETTI Modbus integration."""

from typing import Any, override

from modbus_connection import ModbusError
from yarl import URL

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODEL, MODEL_ID
from .coordinator import (
    BluettiModbusConfigEntry,
    BluettiModbusDataUpdateCoordinator,
    BluettiModbusSettingsCoordinator,
)


def bluetti_modbus_device_info(
    serial: str, sw_version: str, *, host: str
) -> DeviceInfo:
    """Return device information for a BLUETTI Modbus device."""
    return DeviceInfo(
        configuration_url=str(URL.build(scheme="http", host=host)),
        identifiers={(DOMAIN, serial)},
        manufacturer="BLUETTI",
        model=MODEL,
        model_id=MODEL_ID,
        name=MODEL,
        serial_number=serial,
        sw_version=sw_version,
    )


class BluettiModbusEntity(CoordinatorEntity[BluettiModbusDataUpdateCoordinator]):
    """Defines a BLUETTI Modbus entity."""

    _attr_has_entity_name = True

    def __init__(self, *, entry: BluettiModbusConfigEntry, field_name: str) -> None:
        """Initialize a BLUETTI Modbus entity."""
        super().__init__(coordinator=entry.runtime_data.coordinator)
        self._field_name = field_name
        self._attr_unique_id = f"{entry.runtime_data.serial}_{field_name}"
        self._attr_device_info = entry.runtime_data.device_info


class BluettiModbusSettingEntity(CoordinatorEntity[BluettiModbusSettingsCoordinator]):
    """Defines an entity for a setting the power station can be given."""

    _attr_has_entity_name = True

    def __init__(self, *, entry: BluettiModbusConfigEntry, field_name: str) -> None:
        """Initialize a BLUETTI Modbus setting entity."""
        super().__init__(coordinator=entry.runtime_data.settings)
        self._readings = entry.runtime_data.coordinator
        self._field_name = field_name
        self._attr_unique_id = f"{entry.runtime_data.serial}_{field_name}"
        self._attr_device_info = entry.runtime_data.device_info

    @override
    async def async_added_to_hass(self) -> None:
        """Also follow the readings poll, which decides availability."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._readings.async_add_listener(self._handle_coordinator_update)
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the setting can be read and written.

        The readings poll is what confirms the device is still the one this
        entry was set up for, so a setting is never written to another one.
        """
        return super().available and self._readings.last_update_success

    async def _async_write(self, value: Any) -> None:
        """Write the setting, then show it until the next poll confirms it.

        The device serves the old value for a moment after a write.
        """
        try:
            await self.coordinator.device.write(self._field_name, value)
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self.coordinator.async_set_updated_data(
            self.coordinator.data | {self._field_name: value}
        )
