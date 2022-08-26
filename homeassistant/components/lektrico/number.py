"""Support for Lektrico charging station numbers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import lektricowifi

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FRIENDLY_NAME, ELECTRIC_CURRENT_AMPERE, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LektricoDeviceDataUpdateCoordinator
from .const import DOMAIN


@dataclass
class LektricoNumberEntityDescription(NumberEntityDescription):
    """A class that describes the Lektrico number entities."""

    @classmethod
    def get_value(cls, data: Any) -> int | None:
        """Return None."""
        return None

    @classmethod
    async def set_value(
        cls, device: lektricowifi.Charger, value: float, data: Any
    ) -> bool | None:
        """Return None."""
        return None


@dataclass
class LedBrightnessNumberEntityDescription(LektricoNumberEntityDescription):
    """A class that describes the Lektrico Led Brightness number entity."""

    @classmethod
    def get_value(cls, data: Any) -> int:
        """Get the Led Brightness."""
        return int(data.led_max_brightness)

    @classmethod
    async def set_value(
        cls, device: lektricowifi.Charger, value: float, data: Any
    ) -> bool:
        """Set the value for the led brightness in %, from 20 to 100."""
        # Quick change the value displayed on the entity.
        data.led_max_brightness = int(value)
        return bool(
            await device.send_command(
                f'app_config.set?config_key="led_max_brightness"&config_value={int(value)}'
            )
        )


@dataclass
class DynamicCurrentNumberEntityDescription(LektricoNumberEntityDescription):
    """A class that describes the Lektrico Dynamic Current number entity."""

    @classmethod
    def get_value(cls, data: Any) -> int:
        """Get the Lektrico Dynamic."""
        return int(data.dynamic_current)

    @classmethod
    async def set_value(
        cls, device: lektricowifi.Charger, value: float, data: Any
    ) -> bool:
        """Set the value of the dynamic current, as int between 0 and 32 A."""
        # Quick change the value displayed on the entity.
        data.dynamic_current = int(value)
        return bool(
            await device.send_command(
                f'dynamic_current.set?dynamic_current="{int(value)}"'
            )
        )


@dataclass
class UserCurrentNumberEntityDescription(LektricoNumberEntityDescription):
    """A class that describes the Lektrico User Current number entity."""

    @classmethod
    def get_value(cls, data: Any) -> int:
        """Get the Lektrico User Current."""
        return int(data.user_current)

    @classmethod
    async def set_value(
        cls, device: lektricowifi.Charger, value: float, data: Any
    ) -> bool:
        """Set the value of the user current, as int between 6 and 32 A."""
        # Quick change the value displayed on the entity.
        data.user_current = int(value)
        return bool(
            await device.send_command(
                f'app_config.set?config_key="user_current"&config_value="{int(value)}"'
            )
        )


SENSORS: tuple[LektricoNumberEntityDescription, ...] = (
    LedBrightnessNumberEntityDescription(
        key="led_max_brightness",
        name="Led brightness",
        native_min_value=20,
        native_max_value=100,
        native_step=5,
        native_unit_of_measurement=PERCENTAGE,
    ),
    DynamicCurrentNumberEntityDescription(
        key="dynamic_current",
        name="Dynamic current",
        native_min_value=0,
        native_max_value=32,
        native_step=1,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    UserCurrentNumberEntityDescription(
        key="user_current",
        name="User current",
        native_min_value=6,
        native_max_value=32,
        native_step=1,
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lektrico charger based on a config entry."""
    coordinator: LektricoDeviceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    sensors = [
        LektricoNumber(
            sensor_desc,
            coordinator,
            entry.data[CONF_FRIENDLY_NAME],
        )
        for sensor_desc in SENSORS
    ]

    async_add_entities(sensors, False)


class LektricoNumber(CoordinatorEntity, NumberEntity):
    """The entity class for Lektrico charging stations numbers."""

    entity_description: LektricoNumberEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        description: LektricoNumberEntityDescription,
        coordinator: LektricoDeviceDataUpdateCoordinator,
        friendly_name: str,
    ) -> None:
        """Initialize Lektrico charger."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial_number)},
            model=f"1P7K {coordinator.serial_number} rev.{coordinator.board_revision}",
            name=friendly_name,
            manufacturer="Lektrico",
            sw_version=coordinator.data.fw_version,
        )

        self._attr_native_value = 20
        if description.native_step is not None:
            self._attr_native_step = description.native_step
        if description.native_max_value is not None:
            self._attr_native_max_value = description.native_max_value
        if description.native_min_value is not None:
            self._attr_native_min_value = description.native_min_value

    @property
    def native_value(self) -> int | None:
        """Return the value of the number as integer."""
        return self.entity_description.get_value(self.coordinator.data)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the number."""
        await self.entity_description.set_value(
            self.coordinator.device, value, self.coordinator.data
        )
        # Refresh the coordinator because some buttons change some values.
        await self.coordinator.async_refresh()
