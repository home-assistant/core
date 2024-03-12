"""Support for Arve devices."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from asyncarve import Arve

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_ARVE_CLIENT, DOMAIN, LOGGER
from .entity import ArveDeviceEntity

SCAN_INTERVAL = timedelta(seconds=10)


@dataclass(frozen=True, kw_only=True)
class ArveDeviceEntityDescription(SensorEntityDescription):
    """Describes Arve device entity."""

    value_fn: Callable[[Arve], Coroutine[Any, Any, int | float]]
    # value_fn: int | float


SENSORS: tuple[ArveDeviceEntityDescription, ...] = (
    ArveDeviceEntityDescription(
        key="CO2",
        translation_key="co2_value",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        value_fn=lambda arve: arve.get_curr_co2(),
    ),
    ArveDeviceEntityDescription(
        key="AQI",
        translation_key="aqi_value",
        native_unit_of_measurement=None,
        value_fn=lambda arve: arve.get_curr_aqi(),
    ),
    ArveDeviceEntityDescription(
        key="Humidity",
        translation_key="humidity_value",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda arve: arve.get_curr_humidity(),
    ),
    ArveDeviceEntityDescription(
        key="PM10",
        translation_key="pm10_value",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        value_fn=lambda arve: arve.get_curr_pm10(),
    ),
    ArveDeviceEntityDescription(
        key="PM25",
        translation_key="pm25_value",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        value_fn=lambda arve: arve.get_curr_pm25(),
    ),
    ArveDeviceEntityDescription(
        key="Temperature",
        translation_key="temperature_value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda arve: arve.get_curr_temperature(),
    ),
    ArveDeviceEntityDescription(
        key="TVOC",
        translation_key="tvoc_value",
        native_unit_of_measurement=None,
        value_fn=lambda arve: arve.get_curr_tvoc(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Arve device based on a config entry."""
    arve = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            ArveDevice(arve[DATA_ARVE_CLIENT], entry, description)
            for description in SENSORS
        ],
        True,
    )


class ArveDevice(ArveDeviceEntity, SensorEntity):
    """Define an Arve device."""

    entity_description: ArveDeviceEntityDescription

    def __init__(
        self, arve: Arve, entry: ConfigEntry, description: ArveDeviceEntityDescription
    ) -> None:
        """Initialize Arve device."""
        super().__init__(
            arve,
            entry,
        )
        self.sn = arve.device_sn
        self.formated_sn = "_".join(self.sn.lower().split("-"))
        self.entity_description = description
        self.trans_key = str(self.entity_description.translation_key)
        self._attr_unique_id = "_".join(
            [
                self.sn,
                self.trans_key,
            ]
        )

        LOGGER.info(self._attr_unique_id)

        self.name = description.key

    async def _arve_update(self) -> None:
        """Update Arve device entity."""
        value = await self.entity_description.value_fn(self.arve)
        self._attr_native_value = value
        if isinstance(value, float):
            self._attr_native_value = f"{value:.2f}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the Arve device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.sn)},
            serial_number=self.sn,
            manufacturer="Calanda Air AG",
            model="Arve Sens Pro",
            sw_version="1.0.0",
        )
