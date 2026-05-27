"""Sensor platform for ALLNET."""

from dataclasses import dataclass
from typing import Any

from allnet.models import Channel, ChannelKind

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import AllnetConfigEntry
from .coordinator import AllnetDataUpdateCoordinator
from .entity import AllnetEntity

LIGHT_LUX = "lx"


@dataclass(frozen=True)
class _UnitMapping:
    """Mapping from API unit string to HA sensor attributes."""

    device_class: SensorDeviceClass | None
    unit: str | None
    state_class: SensorStateClass | None


_UNIT_MAP: dict[str, _UnitMapping] = {
    "°C": _UnitMapping(
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
    ),
    "°F": _UnitMapping(
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.FAHRENHEIT,
        SensorStateClass.MEASUREMENT,
    ),
    "%": _UnitMapping(
        SensorDeviceClass.HUMIDITY, PERCENTAGE, SensorStateClass.MEASUREMENT
    ),
    "ppm": _UnitMapping(
        SensorDeviceClass.CO2,
        CONCENTRATION_PARTS_PER_MILLION,
        SensorStateClass.MEASUREMENT,
    ),
    "µg/m³": _UnitMapping(
        None, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, SensorStateClass.MEASUREMENT
    ),
    "pt./cm³": _UnitMapping(None, "pt./cm³", SensorStateClass.MEASUREMENT),
    "µm": _UnitMapping(None, "µm", SensorStateClass.MEASUREMENT),
    "A": _UnitMapping(
        SensorDeviceClass.CURRENT,
        UnitOfElectricCurrent.AMPERE,
        SensorStateClass.MEASUREMENT,
    ),
    "Hz": _UnitMapping(
        SensorDeviceClass.FREQUENCY, UnitOfFrequency.HERTZ, SensorStateClass.MEASUREMENT
    ),
    "cos φ": _UnitMapping(
        SensorDeviceClass.POWER_FACTOR, None, SensorStateClass.MEASUREMENT
    ),
    "W": _UnitMapping(
        SensorDeviceClass.POWER, UnitOfPower.WATT, SensorStateClass.MEASUREMENT
    ),
    "kWh": _UnitMapping(
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.KILO_WATT_HOUR,
        SensorStateClass.TOTAL_INCREASING,
    ),
    "V": _UnitMapping(
        SensorDeviceClass.VOLTAGE,
        UnitOfElectricPotential.VOLT,
        SensorStateClass.MEASUREMENT,
    ),
    "mbar": _UnitMapping(
        SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        UnitOfPressure.MBAR,
        SensorStateClass.MEASUREMENT,
    ),
    "hPa": _UnitMapping(
        SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        UnitOfPressure.HPA,
        SensorStateClass.MEASUREMENT,
    ),
    "lx": _UnitMapping(
        SensorDeviceClass.ILLUMINANCE, LIGHT_LUX, SensorStateClass.MEASUREMENT
    ),
}


def _pm_device_class(name: str) -> SensorDeviceClass | None:
    """Disambiguate PM sub-type from channel name."""
    name_upper = name.upper()
    if "PM10" in name_upper:
        return SensorDeviceClass.PM10
    if "PM2.5" in name_upper or "PM25" in name_upper:
        return SensorDeviceClass.PM25
    if "PM4" in name_upper:
        return SensorDeviceClass.PM4
    if "PM1" in name_upper:
        return SensorDeviceClass.PM1
    return None


def _resolve_mapping(channel: Channel) -> _UnitMapping:
    """Return device_class/unit/state_class for a channel."""
    unit = channel.unit or ""
    mapping = _UNIT_MAP.get(unit)
    if mapping is None:
        # Unknown unit — pass it through verbatim with MEASUREMENT state_class
        return _UnitMapping(
            None, unit or None, SensorStateClass.MEASUREMENT if unit else None
        )
    if unit == "µg/m³":
        pm_class = _pm_device_class(channel.name)
        return _UnitMapping(
            pm_class,
            CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            SensorStateClass.MEASUREMENT,
        )
    return mapping


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AllnetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ALLNET sensors."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    device_info = runtime.ha_device_info
    device_unique_id = entry.unique_id or entry.entry_id

    known_ids: set[str] = set()

    def _check_new_entities() -> None:
        new_entities: list[AllnetSensorEntity] = []
        for channel in coordinator.data.values():
            if channel.kind != ChannelKind.SENSOR:
                continue
            if channel.id in known_ids:
                continue
            known_ids.add(channel.id)
            mapping = _resolve_mapping(channel)
            unique_id = f"{device_unique_id}_{channel.id}_sensor"
            new_entities.append(
                AllnetSensorEntity(
                    coordinator=coordinator,
                    channel_id=channel.id,
                    device_info=device_info,
                    unique_id=unique_id,
                    name=channel.name,
                    device_class=mapping.device_class,
                    native_unit=mapping.unit,
                    state_class=mapping.state_class,
                )
            )
        if new_entities:
            async_add_entities(new_entities)

    _check_new_entities()

    entry.async_on_unload(coordinator.async_add_listener(_check_new_entities))


class AllnetSensorEntity(AllnetEntity, SensorEntity):
    """Representation of an ALLNET sensor channel."""

    def __init__(
        self,
        coordinator: AllnetDataUpdateCoordinator,
        channel_id: str,
        device_info: Any,
        unique_id: str,
        name: str,
        device_class: SensorDeviceClass | None,
        native_unit: str | None,
        state_class: SensorStateClass | None,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, channel_id, device_info)
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit
        self._attr_state_class = state_class

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        channel = self.coordinator.data.get(self._channel_id)
        if channel is None:
            return None
        return channel.value
