"""Sensor platform configuration for go-e Charger Cloud."""

import logging
import numbers
from typing import Literal

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CAR_STATUS,
    CHARGER_ACCESS,
    CHARGER_MAX_CURRENT,
    CHARGING_ALLOWED,
    CONF_CHARGERS,
    DOMAIN,
    ENERGY_SINCE_CAR_CONNECTED,
    ENERGY_TOTAL,
    MANUFACTURER,
    ONLINE,
    PHASE_SWITCH_MODE,
    PHASES_NUMBER_CONNECTED,
    STATUS,
)

MINUTE_IN_MS: Literal[60000] = 60_000

# Reference: https://developers.home-assistant.io/docs/core/entity/sensor/#long-term-statistics
AMPERE: Literal["A"] = "A"
K_WATT_HOUR: Literal["kWh"] = "kWh"
TIME_MINUTES: Literal["min"] = "min"

_LOGGER: logging.Logger = logging.getLogger(__name__)

CHARGER_SENSORS_CONFIG: dict = {
    "sensors": [
        CAR_STATUS,
        CHARGER_ACCESS,
        CHARGING_ALLOWED,
        CHARGER_MAX_CURRENT,
        ENERGY_SINCE_CAR_CONNECTED,
        ENERGY_TOTAL,
        PHASE_SWITCH_MODE,
        PHASES_NUMBER_CONNECTED,
        "name",
    ],
    "units": {
        CAR_STATUS: {"unit": "", "name": "Car charging status"},
        CHARGER_ACCESS: {"unit": "", "name": "Access Control"},
        CHARGING_ALLOWED: {"unit": "", "name": "Car charging allowed"},
        CHARGER_MAX_CURRENT: {"unit": AMPERE, "name": "Current charging speed (max)"},
        ENERGY_SINCE_CAR_CONNECTED: {
            "unit": K_WATT_HOUR,
            "name": "Energy since car connected",
        },
        ENERGY_TOTAL: {"unit": K_WATT_HOUR, "name": "Energy total"},
        PHASE_SWITCH_MODE: {"unit": "", "name": "Phase switch mode"},
        PHASES_NUMBER_CONNECTED: {"unit": "", "name": "Number of connected phases"},
        "name": {"unit": "", "name": "Charger name"},
    },
    "state_classes": {
        CHARGER_MAX_CURRENT: SensorStateClass.MEASUREMENT,
        ENERGY_SINCE_CAR_CONNECTED: SensorStateClass.TOTAL,
        ENERGY_TOTAL: SensorStateClass.TOTAL,
    },
    "device_classes": {
        CHARGER_ACCESS: f"{DOMAIN}__access_control",
        CHARGER_MAX_CURRENT: SensorDeviceClass.CURRENT,
        ENERGY_SINCE_CAR_CONNECTED: SensorDeviceClass.ENERGY,
        ENERGY_TOTAL: SensorDeviceClass.ENERGY,
        CHARGING_ALLOWED: f"{DOMAIN}__allow_charging",
        PHASE_SWITCH_MODE: f"{DOMAIN}__phase_switch_mode",
    },
}


class ChargerSensor(CoordinatorEntity, SensorEntity):
    """Representation of a sensor for the go-e Charger Cloud."""

    def __init__(
        self,
        coordinator,
        entity_id,
        device_id,
        attributes,
    ) -> None:
        """Initialize the Base sensor."""

        super().__init__(coordinator)
        self._device_id = device_id
        self.entity_id = entity_id
        self._name: str = attributes["name"]
        self._attribute: str = attributes["attribute"]
        self._unit: str = attributes["unit"]
        self._attr_state_class = attributes["state_class"]
        self._attr_device_class = attributes["device_class"]

    @property
    def device_info(self) -> entity.DeviceInfo:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_id,
            "manufacturer": MANUFACTURER,
            "model": "",
        }

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        return self._unit

    @property
    def native_value(self) -> float | str | int | None:
        """Return the state of the sensor."""
        if self._attribute not in self.coordinator.data[self._device_id]:
            return None

        attr_value: float | str = self.coordinator.data[self._device_id][
            self._attribute
        ]

        # if charging is not allowed, show current as 0
        if (
            self._attribute == CHARGER_MAX_CURRENT
            and self.coordinator.data[self._device_id][CHARGING_ALLOWED] == "off"
        ):
            return 0

        # convert Wh to kWh and round to 2 decimal positions
        if self._unit == K_WATT_HOUR and isinstance(attr_value, numbers.Number):
            attr_value = round(float(attr_value) / 1000, 2)

        # if attribute is a number and larger than 0, convert it to minutes
        if (
            self.state_class == TIME_MINUTES
            and isinstance(attr_value, numbers.Number)
            and float(attr_value) > 0
        ):
            return round(float(attr_value) / MINUTE_IN_MS, 2)

        return attr_value

    @property
    def available(self) -> bool:
        """Make the sensor input (un)available based on the status."""

        data: dict = self.coordinator.data[self._device_id]

        return data[STATUS] == ONLINE


def _setup_sensors(
    hass: HomeAssistant,
    sensor_ids: list,
    coordinator_name: str,
) -> list:
    entities: list[ChargerSensor] = []

    for sensor_id in sensor_ids:
        sensors: list[ChargerSensor] = []
        _LOGGER.debug("Creating sensors for the %s=%s", DOMAIN, sensor_id)

        for sensor in CHARGER_SENSORS_CONFIG.get("sensors", []):
            _LOGGER.debug("Adding sensor=%s for the %s=%s", sensor, DOMAIN, sensor_id)

            sensor_unit: str = (
                CHARGER_SENSORS_CONFIG.get("units", {}).get(sensor).get("unit")
                if CHARGER_SENSORS_CONFIG.get("units", {}).get(sensor)
                else ""
            )
            sensor_name: str = (
                CHARGER_SENSORS_CONFIG.get("units", {}).get(sensor).get("name")
                if CHARGER_SENSORS_CONFIG.get("units", {}).get(sensor)
                else sensor
            )
            sensor_state_class: str = (
                CHARGER_SENSORS_CONFIG.get("state_classes", {})[sensor]
                if sensor in CHARGER_SENSORS_CONFIG.get("state_classes", {})
                else ""
            )
            sensor_device_class: str = (
                CHARGER_SENSORS_CONFIG.get("device_classes", {})[sensor]
                if sensor in CHARGER_SENSORS_CONFIG.get("device_classes", {})
                else ""
            )

            sensors.append(
                ChargerSensor(
                    hass.data[DOMAIN][coordinator_name],
                    f"{SENSOR_DOMAIN}.{DOMAIN}_{sensor_id}_{sensor}",
                    sensor_id,
                    {
                        "name": sensor_name,
                        "attribute": sensor,
                        "unit": sensor_unit,
                        "state_class": sensor_state_class,
                        "device_class": sensor_device_class,
                    },
                )
            )

        entities.extend(sensors)

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set sensors from a config entry created in the integrations UI."""

    entry_id: str = config_entry.entry_id
    config: dict = hass.data[DOMAIN][entry_id]
    _LOGGER.debug("Setting up the go-e Charger Cloud sensor for=%s", entry_id)

    if config_entry.options:
        config.update(config_entry.options)

    async_add_entities(
        _setup_sensors(
            hass,
            [entry_id],
            f"{entry_id}_coordinator",
        ),
        update_before_add=True,
    )


# pylint: disable=unused-argument
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None,
) -> None:
    """Set up go-e Charger Cloud Sensor platform."""

    _LOGGER.debug("Setting up the go-e Charger Cloud sensor platform")

    if discovery_info is None:
        _LOGGER.error("Missing discovery_info, skipping setup")
        return

    for charger_name in discovery_info[CONF_CHARGERS]:
        async_add_entities(
            _setup_sensors(
                hass,
                [charger_name],
                f"{charger_name}_coordinator",
            )
        )
