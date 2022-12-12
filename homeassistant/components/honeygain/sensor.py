"""Sensors for HoneyGain data."""
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_DOLLAR
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HoneygainData
from .const import DOMAIN


@dataclass
class SensorValueEntityDescription(SensorEntityDescription):
    """Class describing Honeygain sensor entities."""

    value: Callable = lambda x: x


HONEYGAIN_SENSORS: list[SensorValueEntityDescription] = [
    SensorValueEntityDescription(
        key="account_balance",
        name="Account balance",
        icon="mdi:hand-coin",
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_DOLLAR,
        value=lambda x: x.balances.get("payout").get("usd_cents") / 100,
    ),
    SensorValueEntityDescription(
        key="today_earnings",
        name="Today's earnings",
        icon="mdi:calendar-today",
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_DOLLAR,
        value=lambda x: x.balances.get("realtime").get("usd_cents") / 100,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensor set up for HoneyGain."""
    honeygain_data: HoneygainData = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        HoneygainAccountSensor(honeygain_data, sensor_description)
        for sensor_description in HONEYGAIN_SENSORS
    ]
    async_add_entities(entities)


class HoneygainAccountSensor(SensorEntity):
    """Sensor to track Honeygain data."""

    honeygain_data: HoneygainData
    entity_description: SensorValueEntityDescription

    def __init__(
        self,
        honeygain_data: HoneygainData,
        sensor_description: SensorValueEntityDescription,
    ) -> None:
        """Create Sensor for displaying Honeygain account details."""
        self.entity_description = sensor_description
        self._honeygain_data = honeygain_data
        self._attr_unique_id = f"honeygain-{self._honeygain_data.user['referral_code']}-{sensor_description.key}"
        self._attr_native_value = sensor_description.value(self._honeygain_data)
        self._attr_device_info = DeviceInfo(
            configuration_url="https://dashboard.honeygain.com/profile",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._honeygain_data.user["referral_code"])},
            manufacturer="Honeygain",
            name="Honeygain",
        )

    def update(self) -> None:
        """Update Sensor data."""
        self._honeygain_data.update()
        self._attr_native_value = self.entity_description.value(self._honeygain_data)
