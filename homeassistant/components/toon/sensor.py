"""Support for Toon sensors."""
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    ATTR_DEFAULT_ENABLED,
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_MEASUREMENT,
    ATTR_NAME,
    ATTR_SECTION,
    ATTR_UNIT_OF_MEASUREMENT,
    DOMAIN,
    SENSOR_ENTITIES,
)
from .coordinator import ToonDataUpdateCoordinator
from .models import (
    ToonBoilerDeviceEntity,
    ToonDisplayDeviceEntity,
    ToonElectricityMeterDeviceEntity,
    ToonEntity,
    ToonGasMeterDeviceEntity,
    ToonSolarDeviceEntity,
    ToonWaterMeterDeviceEntity,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Toon sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        ToonElectricityMeterDeviceSensor(coordinator, key=key)
        for key in (
            "power_average_daily",
            "power_average",
            "power_daily_cost",
            "power_daily_value",
            "power_meter_reading_low",
            "power_meter_reading",
            "power_value",
            "solar_meter_reading_low_produced",
            "solar_meter_reading_produced",
        )
    ]

    sensors.extend(
        [ToonDisplayDeviceSensor(coordinator, key="current_display_temperature")]
    )

    sensors.extend(
        [
            ToonGasMeterDeviceSensor(coordinator, key=key)
            for key in (
                "gas_average_daily",
                "gas_average",
                "gas_daily_cost",
                "gas_daily_usage",
                "gas_meter_reading",
                "gas_value",
            )
        ]
    )

    sensors.extend(
        [
            ToonWaterMeterDeviceSensor(coordinator, key=key)
            for key in (
                "water_average_daily",
                "water_average",
                "water_daily_cost",
                "water_daily_usage",
                "water_meter_reading",
                "water_value",
            )
        ]
    )

    if coordinator.data.agreement.is_toon_solar:
        sensors.extend(
            [
                ToonSolarDeviceSensor(coordinator, key=key)
                for key in [
                    "solar_value",
                    "solar_maximum",
                    "solar_produced",
                    "solar_average_produced",
                    "power_usage_day_produced_solar",
                    "power_usage_day_from_grid_usage",
                    "power_usage_day_to_grid_usage",
                    "power_usage_current_covered_by_solar",
                ]
            ]
        )

    if coordinator.data.thermostat.have_opentherm_boiler:
        sensors.extend(
            [
                ToonBoilerDeviceSensor(
                    coordinator, key="thermostat_info_current_modulation_level"
                )
            ]
        )

    async_add_entities(sensors, True)


class ToonSensor(ToonEntity):
    """Defines a Toon sensor."""

    def __init__(self, coordinator: ToonDataUpdateCoordinator, *, key: str) -> None:
        """Initialize the Toon sensor."""
        self.key = key

        super().__init__(
            coordinator,
            enabled_default=SENSOR_ENTITIES[key][ATTR_DEFAULT_ENABLED],
            icon=SENSOR_ENTITIES[key][ATTR_ICON],
            name=SENSOR_ENTITIES[key][ATTR_NAME],
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        agreement_id = self.coordinator.data.agreement.agreement_id
        # This unique ID is a bit ugly and contains unneeded information.
        # It is here for legacy / backward compatible reasons.
        return f"{DOMAIN}_{agreement_id}_sensor_{self.key}"

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        section = getattr(
            self.coordinator.data, SENSOR_ENTITIES[self.key][ATTR_SECTION]
        )
        return getattr(section, SENSOR_ENTITIES[self.key][ATTR_MEASUREMENT])

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit this state is expressed in."""
        return SENSOR_ENTITIES[self.key][ATTR_UNIT_OF_MEASUREMENT]

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class."""
        return SENSOR_ENTITIES[self.key][ATTR_DEVICE_CLASS]


class ToonElectricityMeterDeviceSensor(ToonSensor, ToonElectricityMeterDeviceEntity):
    """Defines a Electricity Meter sensor."""


class ToonGasMeterDeviceSensor(ToonSensor, ToonGasMeterDeviceEntity):
    """Defines a Gas Meter sensor."""


class ToonWaterMeterDeviceSensor(ToonSensor, ToonWaterMeterDeviceEntity):
    """Defines a Water Meter sensor."""


class ToonSolarDeviceSensor(ToonSensor, ToonSolarDeviceEntity):
    """Defines a Solar sensor."""


class ToonBoilerDeviceSensor(ToonSensor, ToonBoilerDeviceEntity):
    """Defines a Boiler sensor."""


class ToonDisplayDeviceSensor(ToonSensor, ToonDisplayDeviceEntity):
    """Defines a Display sensor."""
