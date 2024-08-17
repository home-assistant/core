"""Binary sensors for myUplink."""

from myuplink import DeviceConnectionState, DevicePoint

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyUplinkConfigEntry, MyUplinkDataCoordinator
from .entity import MyUplinkEntity, MyUplinkSystemEntity
from .helpers import find_matching_platform

CATEGORY_BASED_DESCRIPTIONS: dict[str, dict[str, BinarySensorEntityDescription]] = {
    "NIBEF": {
        "43161": BinarySensorEntityDescription(
            key="elect_add",
            translation_key="elect_add",
        ),
    },
}

CONNECTED_BINARY_SENSOR_DESCRIPTION = BinarySensorEntityDescription(
    key="connected_state",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)

ALARM_BINARY_SENSOR_DESCRIPTION = BinarySensorEntityDescription(
    key="has_alarm",
    device_class=BinarySensorDeviceClass.PROBLEM,
    translation_key="alarm",
)


def get_description(device_point: DevicePoint) -> BinarySensorEntityDescription | None:
    """Get description for a device point.

    Priorities:
    1. Category specific prefix e.g "NIBEF"
    2. Default to None
    """
    prefix, _, _ = device_point.category.partition(" ")
    return CATEGORY_BASED_DESCRIPTIONS.get(prefix, {}).get(device_point.parameter_id)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyUplinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up myUplink binary_sensor."""
    entities: list[BinarySensorEntity] = []
    coordinator = config_entry.runtime_data

    # Setup device point bound sensors
    for device_id, point_data in coordinator.data.points.items():
        for point_id, device_point in point_data.items():
            if find_matching_platform(device_point) == Platform.BINARY_SENSOR:
                description = get_description(device_point)

                entities.append(
                    MyUplinkDevicePointBinarySensor(
                        coordinator=coordinator,
                        device_id=device_id,
                        device_point=device_point,
                        entity_description=description,
                        unique_id_suffix=point_id,
                    )
                )

    # Setup device bound sensors
    entities.extend(
        MyUplinkDeviceBinarySensor(
            coordinator=coordinator,
            device_id=device.id,
            entity_description=CONNECTED_BINARY_SENSOR_DESCRIPTION,
            unique_id_suffix="connection_state",
        )
        for system in coordinator.data.systems
        for device in system.devices
    )

    # Setup system bound sensors
    for system in coordinator.data.systems:
        device_id = system.devices[0].id
        entities.append(
            MyUplinkSystemBinarySensor(
                coordinator=coordinator,
                device_id=device_id,
                system_id=system.id,
                entity_description=ALARM_BINARY_SENSOR_DESCRIPTION,
                unique_id_suffix="has_alarm",
            )
        )

    async_add_entities(entities)


class MyUplinkDevicePointBinarySensor(MyUplinkEntity, BinarySensorEntity):
    """Representation of a myUplink device point bound binary sensor."""

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        device_id: str,
        device_point: DevicePoint,
        entity_description: BinarySensorEntityDescription | None,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the binary_sensor."""
        super().__init__(
            coordinator=coordinator,
            device_id=device_id,
            unique_id_suffix=unique_id_suffix,
        )

        # Internal properties
        self.point_id = device_point.parameter_id
        self._attr_name = device_point.parameter_name

        if entity_description is not None:
            self.entity_description = entity_description

    @property
    def is_on(self) -> bool:
        """Binary sensor state value."""
        device_point = self.coordinator.data.points[self.device_id][self.point_id]
        return int(device_point.value) != 0

    @property
    def available(self) -> bool:
        """Return device data availability."""
        return super().available and (
            self.coordinator.data.devices[self.device_id].connectionState
            == DeviceConnectionState.Connected
        )


class MyUplinkDeviceBinarySensor(MyUplinkEntity, BinarySensorEntity):
    """Representation of a myUplink device bound binary sensor."""

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        device_id: str,
        entity_description: BinarySensorEntityDescription | None,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the binary_sensor."""
        super().__init__(
            coordinator=coordinator,
            device_id=device_id,
            unique_id_suffix=unique_id_suffix,
        )

        if entity_description is not None:
            self.entity_description = entity_description

    @property
    def is_on(self) -> bool:
        """Binary sensor state value."""
        return (
            self.coordinator.data.devices[self.device_id].connectionState
            == DeviceConnectionState.Connected
        )


class MyUplinkSystemBinarySensor(MyUplinkSystemEntity, BinarySensorEntity):
    """Representation of a myUplink system bound binary sensor."""

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        system_id: str,
        device_id: str,
        entity_description: BinarySensorEntityDescription | None,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the binary_sensor."""
        super().__init__(
            coordinator=coordinator,
            system_id=system_id,
            device_id=device_id,
            unique_id_suffix=unique_id_suffix,
        )

        if entity_description is not None:
            self.entity_description = entity_description

    @property
    def is_on(self) -> bool | None:
        """Binary sensor state value."""
        retval = None
        for system in self.coordinator.data.systems:
            if system.id == self.system_id:
                retval = system.has_alarm
                break
        return retval
