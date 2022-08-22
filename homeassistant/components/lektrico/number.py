"""Support for Lektrico charging station numbers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import lektricowifi

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_FRIENDLY_NAME,
    ELECTRIC_CURRENT_AMPERE,
    PERCENTAGE,
)
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
    def set_value(
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
    def set_value(cls, device: lektricowifi.Charger, value: float, data: Any) -> bool:
        """Set the value for the led brightness in %, from 20 to 100."""
        # Quick change the value displayed on the entity.
        data.led_max_brightness = int(value)
        return bool(
            device.send_command(
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
    def set_value(cls, device: lektricowifi.Charger, value: float, data: Any) -> bool:
        """Set the value of the dynamic current, as int between 0 and 32 A."""
        # Quick change the value displayed on the entity.
        data.dynamic_current = int(value)
        return bool(
            device.send_command(f'dynamic_current.set?dynamic_current="{int(value)}"')
        )


@dataclass
class UserCurrentNumberEntityDescription(LektricoNumberEntityDescription):
    """A class that describes the Lektrico User Current number entity."""

    @classmethod
    def get_value(cls, data: Any) -> int:
        """Get the Lektrico User Current."""
        return int(data.user_current)

    @classmethod
    def set_value(cls, device: lektricowifi.Charger, value: float, data: Any) -> bool:
        """Set the value of the user current, as int between 6 and 32 A."""
        # Quick change the value displayed on the entity.
        data.user_current = int(value)
        return bool(
            device.send_command(
                f'app_config.set?config_key="user_current"&config_value="{int(value)}"'
            )
        )


SENSORS: tuple[LektricoNumberEntityDescription, ...] = (
    LedBrightnessNumberEntityDescription(
        key="led_max_brightness",
        name="Led Brightness",
        min_value=20,
        max_value=100,
        step=5,
        unit_of_measurement=PERCENTAGE,
    ),
    DynamicCurrentNumberEntityDescription(
        key="dynamic_current",
        name="Dynamic Current",
        min_value=0,
        max_value=32,
        step=1,
        unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
    UserCurrentNumberEntityDescription(
        key="user_current",
        name="User Current",
        min_value=6,
        max_value=32,
        step=1,
        unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lektrico charger based on a config entry."""
    _lektrico_device: LektricoDeviceDataUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    sensors = [
        LektricoNumber(
            sensor_desc,
            _lektrico_device,
            entry.data[CONF_FRIENDLY_NAME],
        )
        for sensor_desc in SENSORS
    ]

    async_add_entities(sensors, False)


class LektricoNumber(CoordinatorEntity, NumberEntity):
    """The entity class for Lektrico charging stations numbers."""

    entity_description: LektricoNumberEntityDescription

    def __init__(
        self,
        description: LektricoNumberEntityDescription,
        _lektrico_device: LektricoDeviceDataUpdateCoordinator,
        friendly_name: str,
    ) -> None:
        """Initialize Lektrico charger."""
        super().__init__(_lektrico_device)
        self.friendly_name = friendly_name
        self.serial_number = _lektrico_device.serial_number
        self.board_revision = _lektrico_device.board_revision
        self.entity_description = description

        self._attr_name = f"{self.friendly_name} {description.name}"
        self._attr_unique_id = f"{self.serial_number}_{description.name}"
        # ex: 500006_No Authorisation

        self._lektrico_device = _lektrico_device

        self._attr_value = 20
        if description.step is not None:
            self._attr_step = description.step
        if description.max_value is not None:
            self._attr_max_value = description.max_value
        if description.min_value is not None:
            self._attr_min_value = description.min_value

    @property
    def value(self) -> int | None:
        """Return the value of the number as integer."""
        return self.entity_description.get_value(self._lektrico_device.data)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Lektrico charger."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self.serial_number)},
            ATTR_NAME: self.friendly_name,
            ATTR_MANUFACTURER: "Lektrico",
            ATTR_MODEL: f"1P7K {self.serial_number} rev.{self.board_revision}",
            ATTR_SW_VERSION: self._lektrico_device.data.fw_version,
        }

    async def async_set_value(self, value: float) -> None:
        """Set the value of the number."""
        self.entity_description.set_value(
            self._lektrico_device.device, value, self._lektrico_device.data
        )
        # Refresh the coordinator because some buttons change some values.
        await self._lektrico_device.async_refresh()
