"""Sensor platform for Marstek devices."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import cast, override

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

from .coordinator import MarstekConfigEntry, MarstekDataUpdateCoordinator
from .entity import MarstekEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MarstekSensorEntityDescription(SensorEntityDescription):
    """Describe a Marstek sensor entity."""

    value_fn: Callable[[object], StateType | None] | None = None
    exists_fn: Callable[[dict[str, object]], bool] = lambda data: True


def _int_value(value: object) -> int | None:
    """Return an integer value or None."""
    if isinstance(value, int | float | str):
        return int(value)
    return None


def _exists_for_key(key: str) -> Callable[[dict[str, object]], bool]:
    """Return a predicate checking whether a sensor key is present."""

    def exists(data: dict[str, object]) -> bool:
        return key in data

    return exists


def _pv_sensor_descriptions() -> tuple[MarstekSensorEntityDescription, ...]:
    """Build PV sensor descriptions for all supported channels."""
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
            ("state", None, None, "mdi:state-machine"),
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
                    value_fn=_int_value if metric != "state" else None,
                    exists_fn=_exists_for_key(key),
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
        value_fn=_int_value,
    ),
    MarstekSensorEntityDescription(
        key="battery_power",
        translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_int_value,
    ),
    MarstekSensorEntityDescription(
        key="device_mode",
        translation_key="device_mode",
        icon="mdi:cog",
    ),
    MarstekSensorEntityDescription(
        key="battery_status",
        translation_key="battery_status",
        icon="mdi:battery",
    ),
    *_pv_sensor_descriptions(),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MarstekConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Marstek sensors based on a config entry."""
    coordinator = config_entry.runtime_data
    device_ip = coordinator.device_ip
    _LOGGER.debug("Setting up Marstek sensors: %s", device_ip)

    sensors = [
        MarstekSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        if description.exists_fn(coordinator.data)
    ]

    _LOGGER.debug("Device %s sensors set up, total %d", device_ip, len(sensors))
    async_add_entities(sensors)


class MarstekSensor(MarstekEntity, SensorEntity):
    """Representation of a Marstek sensor."""

    entity_description: MarstekSensorEntityDescription

    def __init__(
        self,
        coordinator: MarstekDataUpdateCoordinator,
        entity_description: MarstekSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description)

    @property
    @override
    def native_value(self) -> StateType | None:
        """Return the state of the sensor."""
        data = self.coordinator.data
        if not data:
            return None

        value = data.get(self.entity_description.key)
        if value is None:
            return None

        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(value)
        return cast(StateType, value)
