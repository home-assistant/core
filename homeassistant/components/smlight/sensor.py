"""Support for SLZB-06 sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import chain
from typing import override

from pysmlight import Info, Sensors

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfInformation, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from .const import UPTIME_DEVIATION
from .coordinator import SmConfigEntry, SmDataUpdateCoordinator
from .entity import SmEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SmSensorEntityDescription(SensorEntityDescription):
    """Class describing SMLIGHT sensor entities."""

    value_fn: Callable[[Sensors], float | None]


@dataclass(frozen=True, kw_only=True)
class SmRadioUptimeSensorEntityDescription(SensorEntityDescription):
    """Class describing SMLIGHT radio uptime sensor entities."""


@dataclass(frozen=True, kw_only=True)
class SmInfoEntityDescription(SensorEntityDescription):
    """Class describing SMLIGHT information entities."""

    value_fn: Callable[[Info, int], StateType]


INFO: list[SmInfoEntityDescription] = [
    SmInfoEntityDescription(
        key="device_mode",
        translation_key="device_mode",
        device_class=SensorDeviceClass.ENUM,
        options=["eth", "wifi", "usb"],
        value_fn=lambda x, idx: x.coord_mode,
    ),
    SmInfoEntityDescription(
        key="firmware_channel",
        translation_key="firmware_channel",
        device_class=SensorDeviceClass.ENUM,
        options=["dev", "release"],
        value_fn=lambda x, idx: x.fw_channel,
    ),
]

RADIO_TYPE_OPTIONS = ["coordinator", "router", "thread", "thread_border_router"]
RADIO_TYPE_MAP = {
    0: "coordinator",
    1: "router",
    2: "thread",
    8: "thread_border_router",
}
THREAD_BORDER_ROUTER = 8
SOCKET_UPTIME_FIELDS = ("socket_uptime", "socket2_uptime", "socket3_uptime")

RADIO_INFO = SmInfoEntityDescription(
    key="zigbee_type",
    translation_key="zigbee_type",
    device_class=SensorDeviceClass.ENUM,
    options=RADIO_TYPE_OPTIONS,
    value_fn=lambda x, idx: RADIO_TYPE_MAP.get(x.radios[idx].zb_type),
)


SENSORS: list[SmSensorEntityDescription] = [
    SmSensorEntityDescription(
        key="core_temperature",
        translation_key="core_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda x: x.esp32_temp,
    ),
    SmSensorEntityDescription(
        key="zigbee_temperature",
        translation_key="zigbee_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda x: x.zb_temp,
    ),
    SmSensorEntityDescription(
        key="ram_usage",
        translation_key="ram_usage",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.ram_usage,
    ),
    SmSensorEntityDescription(
        key="fs_usage",
        translation_key="fs_usage",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.fs_used,
    ),
]


EXTRA_SENSOR = SmSensorEntityDescription(
    key="zigbee_temperature_2",
    translation_key="zigbee_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=1,
    value_fn=lambda x: x.zb_temp2,
)

PSRAM_SENSOR = SmSensorEntityDescription(
    key="psram_usage",
    translation_key="psram_usage",
    device_class=SensorDeviceClass.DATA_SIZE,
    native_unit_of_measurement=UnitOfInformation.KILOBYTES,
    entity_registry_enabled_default=False,
    value_fn=lambda x: x.psram_usage,
)

CORE_UPTIME = SmSensorEntityDescription(
    key="core_uptime",
    translation_key="core_uptime",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_registry_enabled_default=False,
    value_fn=lambda x: x.uptime,
)

RADIO_UPTIME = SmRadioUptimeSensorEntityDescription(
    key="socket_uptime",
    translation_key="socket_uptime",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_registry_enabled_default=False,
)


def _positive_uptime(uptime: float | None) -> float | None:
    """Return uptime if it represents a running radio socket."""
    if uptime is None or uptime <= 0:
        return None
    return uptime


def _radio_uptime(sensors: Sensors, info: Info, idx: int) -> float | None:
    """Return the uptime value for a radio index."""
    if info.radios[idx].zb_type == THREAD_BORDER_ROUTER:
        return _positive_uptime(sensors.otbr_uptime)

    if idx >= len(SOCKET_UPTIME_FIELDS):
        return None

    return _positive_uptime(getattr(sensors, SOCKET_UPTIME_FIELDS[idx]))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SMLIGHT sensor based on a config entry."""
    coordinator = entry.runtime_data.data
    entities: list[SmEntity] = list(
        chain(
            (SmInfoSensorEntity(coordinator, description) for description in INFO),
            (SmSensorEntity(coordinator, description) for description in SENSORS),
            (SmUptimeSensorEntity(coordinator, CORE_UPTIME),),
        )
    )

    entities.extend(
        SmInfoSensorEntity(coordinator, RADIO_INFO, idx)
        for idx, _ in enumerate(coordinator.data.info.radios)
    )
    entities.extend(
        SmRadioUptimeSensorEntity(coordinator, RADIO_UPTIME, idx)
        for idx, _ in enumerate(coordinator.data.info.radios)
    )

    if coordinator.data.sensors.zb_temp2 is not None:
        entities.append(SmSensorEntity(coordinator, EXTRA_SENSOR))

    if coordinator.data.info.u_device:
        entities.append(SmSensorEntity(coordinator, PSRAM_SENSOR))

    async_add_entities(entities)


class SmSensorEntity(SmEntity, SensorEntity):
    """Representation of a slzb sensor."""

    coordinator: SmDataUpdateCoordinator
    entity_description: SmSensorEntityDescription
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
        description: SmSensorEntityDescription,
    ) -> None:
        """Initiate slzb sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"

    @property
    @override
    def native_value(self) -> datetime | str | float | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data.sensors)


class SmInfoSensorEntity(SmEntity, SensorEntity):
    """Representation of a slzb info sensor."""

    coordinator: SmDataUpdateCoordinator
    entity_description: SmInfoEntityDescription
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
        description: SmInfoEntityDescription,
        idx: int = 0,
    ) -> None:
        """Initiate slzb sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self.idx = idx
        sensor = f"_{idx}" if idx else ""
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}{sensor}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        value = self.entity_description.value_fn(self.coordinator.data.info, self.idx)
        options = self.entity_description.options

        if isinstance(value, int) and options is not None:
            value = options[value] if 0 <= value < len(options) else None

        return value


class SmBaseUptimeSensorEntity(SmEntity, SensorEntity):
    """Base representation of an SMLIGHT uptime sensor."""

    coordinator: SmDataUpdateCoordinator
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
    ) -> None:
        "Initialize uptime sensor instance."
        super().__init__(coordinator)
        self._last_uptime: datetime | None = None

    def get_uptime(self, uptime: float | None) -> datetime | None:
        """Return device uptime or zigbee socket uptime.

        Converts uptime from seconds to a datetime value, allow up to 5
        seconds deviation. This avoids unnecessary updates to sensor state,
        that may be caused by clock jitter.
        """
        if uptime is None:
            # reset to unknown state
            self._last_uptime = None
            return None

        new_uptime = utcnow() - timedelta(seconds=uptime)

        if (
            not self._last_uptime
            or abs(new_uptime - self._last_uptime) > UPTIME_DEVIATION
        ):
            self._last_uptime = new_uptime

        return self._last_uptime


class SmUptimeSensorEntity(SmBaseUptimeSensorEntity):
    """Representation of a slzb uptime sensor."""

    entity_description: SmSensorEntityDescription

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
        description: SmSensorEntityDescription,
    ) -> None:
        """Initialize uptime sensor instance."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"

    @property
    @override
    def native_value(self) -> datetime | None:
        """Return the sensor value."""
        value = self.entity_description.value_fn(self.coordinator.data.sensors)

        return self.get_uptime(value)


class SmRadioUptimeSensorEntity(SmBaseUptimeSensorEntity):
    """Representation of a radio uptime sensor."""

    entity_description: SmRadioUptimeSensorEntityDescription
    idx: int

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
        description: SmRadioUptimeSensorEntityDescription,
        idx: int = 0,
    ) -> None:
        """Initialize radio uptime sensor instance."""
        super().__init__(coordinator)
        self.entity_description = description
        self.idx = idx
        sensor = f"_{idx}" if idx else ""
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}{sensor}"

    @property
    def native_value(self) -> datetime | None:
        """Return the radio uptime value."""
        value = _radio_uptime(
            self.coordinator.data.sensors, self.coordinator.data.info, self.idx
        )

        return self.get_uptime(value)
