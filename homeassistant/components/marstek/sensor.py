"""Sensor platform for Marstek devices."""

from dataclasses import dataclass
import logging
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import BATTERY_STATUS_OPTIONS, DEVICE_MODE_OPTIONS, PV_STATE_OPTIONS
from .coordinator import MarstekConfigEntry
from .entity import MarstekEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MarstekSensorEntityDescription(SensorEntityDescription):
    """Describe a Marstek sensor entity."""

    requires_value: bool = False


def _pv_sensor_descriptions() -> tuple[MarstekSensorEntityDescription, ...]:
    """Build sensors for each of the device's four PV input channels."""
    descriptions: list[MarstekSensorEntityDescription] = []
    for pv_channel in range(1, 5):
        for metric, device_class, unit, icon in (
            (
                "power",
                SensorDeviceClass.POWER,
                UnitOfPower.WATT,
                "mdi:solar-power",
            ),
            (
                "voltage",
                SensorDeviceClass.VOLTAGE,
                UnitOfElectricPotential.VOLT,
                "mdi:flash",
            ),
            (
                "current",
                SensorDeviceClass.CURRENT,
                UnitOfElectricCurrent.AMPERE,
                "mdi:current-ac",
            ),
            (
                "state",
                SensorDeviceClass.ENUM,
                None,
                "mdi:state-machine",
            ),
        ):
            key = f"pv{pv_channel}_{metric}"
            descriptions.append(
                MarstekSensorEntityDescription(
                    key=key,
                    translation_key=key,
                    device_class=device_class,
                    native_unit_of_measurement=unit,
                    icon=icon,
                    state_class=(
                        SensorStateClass.MEASUREMENT if metric != "state" else None
                    ),
                    options=list(PV_STATE_OPTIONS) if metric == "state" else None,
                    requires_value=True,
                )
            )
    return tuple(descriptions)


SENSOR_DESCRIPTIONS: tuple[MarstekSensorEntityDescription, ...] = (
    MarstekSensorEntityDescription(
        key="battery_soc",
        translation_key="battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MarstekSensorEntityDescription(
        key="battery_power",
        translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MarstekSensorEntityDescription(
        key="device_mode",
        translation_key="device_mode",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:cog",
        options=list(DEVICE_MODE_OPTIONS),
    ),
    MarstekSensorEntityDescription(
        key="battery_status",
        translation_key="battery_status",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:battery",
        options=list(BATTERY_STATUS_OPTIONS),
    ),
    *_pv_sensor_descriptions(),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MarstekConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Marstek sensors based on a config entry."""
    coordinator = config_entry.runtime_data.coordinator
    device_ip = coordinator.device_ip
    _LOGGER.debug("Setting up Marstek sensors: %s", device_ip)

    sensors = [
        MarstekSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        if not description.requires_value or coordinator.data.has_value(description.key)
    ]

    _LOGGER.debug("Device %s sensors set up, total %d", device_ip, len(sensors))
    async_add_entities(sensors)


class MarstekSensor(MarstekEntity, SensorEntity):
    """Representation of a Marstek sensor."""

    entity_description: MarstekSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType | None:
        """Return the state of the sensor."""
        return self.coordinator.data.get_value(self.entity_description.key)
