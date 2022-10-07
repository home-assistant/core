"""Platform for sensor integration."""
from __future__ import annotations

from dataclasses import asdict
import logging

from ultraheat_api.response import HeatMeterResponse

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from . import DOMAIN
from .const import API_KEY, GJ_ONLY_KEYS, HEAT_METER_SENSOR_TYPES, MWH_ONLY_KEYS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    unique_id = entry.entry_id
    coordinator: DataUpdateCoordinator[HeatMeterResponse] = hass.data[DOMAIN][
        entry.entry_id
    ]

    model = entry.data["model"]

    device = DeviceInfo(
        identifiers={(DOMAIN, unique_id)},
        manufacturer="Landis & Gyr",
        model=model,
        name="Landis+Gyr Heat Meter",
    )

    # get energy unit from config
    if "energy_unit" in entry.data:
        energy_unit = entry.data["energy_unit"]
    else:
        # get energy unit from data
        energy_unit = energy_unit_from_data(coordinator.data)
        if energy_unit:
            # Add energy unit to config entry
            new_data = {**entry.data}
            new_data["energy_unit"] = energy_unit
            hass.config_entries.async_update_entry(entry, data=new_data)
            _LOGGER.info("Updated config entry with energy unit: %s", energy_unit)
    if energy_unit == UnitOfEnergy.GIGA_JOULE:
        exclude_keys = MWH_ONLY_KEYS
    elif energy_unit == UnitOfEnergy.MEGA_WATT_HOUR:
        exclude_keys = GJ_ONLY_KEYS
    else:
        exclude_keys = []

    sensors = []
    for description in HEAT_METER_SENSOR_TYPES:
        if description.key not in exclude_keys:
            sensors.append(HeatMeterSensor(coordinator, description, device))

    async_add_entities(sensors)


class HeatMeterSensor(
    CoordinatorEntity[DataUpdateCoordinator[HeatMeterResponse]], SensorEntity
):
    """Representation of a Sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[HeatMeterResponse],
        description: SensorEntityDescription,
        device: DeviceInfo,
    ) -> None:
        """Set up the sensor with the initial values."""
        super().__init__(coordinator)
        self.key = description.key
        self._attr_unique_id = f"{coordinator.config_entry.data['device_number']}_{description.key}"  # type: ignore[union-attr]
        self._attr_name = f"Heat Meter {description.name}"
        self.entity_description = description

        self._attr_device_info = device
        self.update_values_from_api()

    def update_values_from_api(self):
        """Update attribute values with the data from the api coordinator."""
        if self.coordinator.data is None:
            _LOGGER.debug(
                "Cannot update %s: could not read any data from the Heat Meter",
                self.key,
            )
            return

        api_key = API_KEY[self.key]
        if api_key in asdict(self.coordinator.data):
            if self.device_class == SensorDeviceClass.TIMESTAMP:
                self._attr_native_value = dt_util.as_utc(
                    asdict(self.coordinator.data)[api_key]
                )
            else:
                self._attr_native_value = asdict(self.coordinator.data)[api_key]

        _LOGGER.debug(
            "Updated value of %s",
            self.key,
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update_values_from_api()
        self.async_write_ha_state()
        _LOGGER.debug(
            "Updated value of %s",
            self.key,
        )


def energy_unit_from_data(data) -> str | None:
    """Determine the energy unit of measurement (MWh or GJ) this device uses."""
    if data:
        mwh_api_key = API_KEY["heat_usage"]
        mwh_supplied = hasattr(data, mwh_api_key) and asdict(data)[mwh_api_key]

        gj_api_key = API_KEY["heat_usage_gj"]
        gj_supplied = hasattr(data, gj_api_key) and asdict(data)[gj_api_key]

        if mwh_supplied and not gj_supplied:
            # MWh is returned and GJ not: remove GJ entities
            return UnitOfEnergy.MEGA_WATT_HOUR

        if gj_supplied and not mwh_supplied:
            # GJ is returned and MWH not: remove MWH entities
            return UnitOfEnergy.GIGA_JOULE

    return None
