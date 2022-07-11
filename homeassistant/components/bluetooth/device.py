"""Support for bluetooth devices."""
from __future__ import annotations

from abc import abstractmethod
from datetime import date, datetime
from decimal import Decimal

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.helpers.typing import StateType

from . import BluetoothServiceInfo
from .binary_sensor import (
    BINARY_SENSOR_TYPE_TO_DEVICE_CLASS,
    BluetoothBinarySensorEntityDescription,
    BluetoothBinarySensorType,
)
from .entity import BluetoothDeviceKey
from .sensor import (
    SENSOR_TYPE_TO_DEVICE_CLASS,
    BluetoothSensorEntityDescription,
    BluetoothSensorType,
)


class BluetoothDeviceData:
    """A simple bluetooth device."""

    def __init__(self) -> None:
        """Init a bluetooth device."""
        self._software_version: str | None = None
        self._device_id_to_name: dict[str | None, str] = {}
        self._device_id_to_type: dict[str | None, str] = {}
        self._entity_descriptions: dict[
            BluetoothDeviceKey,
            BluetoothSensorEntityDescription | BluetoothBinarySensorEntityDescription,
        ] = {}
        self._entity_descriptions_updates: dict[
            BluetoothDeviceKey,
            BluetoothSensorEntityDescription | BluetoothBinarySensorEntityDescription,
        ] = {}

    def supported(self, service_info: BluetoothServiceInfo) -> bool:
        """Return True if the device is supported."""
        self.generate_update(service_info)
        return bool(self._device_id_to_type)

    @property
    def entity_descriptions(
        self,
    ) -> dict[
        BluetoothDeviceKey,
        BluetoothSensorEntityDescription | BluetoothBinarySensorEntityDescription,
    ]:
        """Return the data."""
        return self._entity_descriptions

    def set_device_name(self, name: str, device_id: str | None = None) -> None:
        """Set the device name."""
        self._device_id_to_name[device_id] = name

    def set_device_type(self, device_type: str, device_id: str | None = None) -> None:
        """Set the device type."""
        self._device_id_to_type[device_id] = device_type

    def generate_update(
        self, service_info: BluetoothServiceInfo
    ) -> dict[
        BluetoothDeviceKey,
        BluetoothSensorEntityDescription | BluetoothBinarySensorEntityDescription,
    ]:
        """Update a bluetooth device."""
        self.update(service_info)
        self.update_rssi(service_info.rssi)
        self._entity_descriptions.update(self._entity_descriptions_updates)
        return self._entity_descriptions_updates

    @abstractmethod
    def update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BluetoothServiceInfo."""
        raise NotImplementedError()

    def update_predefined_sensor(
        self,
        key: BluetoothSensorType,
        native_unit_of_measurement: str,
        native_value: int | float,
        name: str | None = None,
        device_id: str | None = None,
    ) -> None:
        """Update a sensor by type."""
        self.update_sensor(
            key=key.value,
            name=name,
            native_unit_of_measurement=native_unit_of_measurement,
            native_value=native_value,
            device_class=SENSOR_TYPE_TO_DEVICE_CLASS[key],
            state_class=SensorStateClass.MEASUREMENT,
            device_id=device_id,
        )

    def update_predefined_binary_sensor(
        self,
        key: BluetoothBinarySensorType,
        is_on: bool | None,
        name: str | None = None,
        device_id: str | None = None,
    ) -> None:
        """Update a binary sensor by type."""
        self.update_binary_sensor(
            name=name,
            key=key.value,
            is_on=is_on,
            device_class=BINARY_SENSOR_TYPE_TO_DEVICE_CLASS[key],
            device_id=device_id,
        )

    def update_rssi(self, native_value: int | float) -> None:
        """Quick update for an rssi sensor."""
        self.update_sensor(
            key="rssi",
            native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            native_value=native_value,
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        )

    def _get_key_name(self, key: str, device_id: str | None = None) -> str:
        """Set the device name."""
        if device_name := self.get_device_name(device_id):
            return f"{device_name} {key.title()}"
        return key.title()

    def get_device_name(self, device_id: str | None = None) -> str | None:
        """Get the device name."""
        return self._device_id_to_name.get(device_id) or self._device_id_to_type.get(
            device_id
        )

    def update_sensor(
        self,
        key: str,
        native_unit_of_measurement: str,
        native_value: StateType | date | datetime | Decimal,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
        name: str | None = None,
        device_id: str | None = None,
        entity_registry_enabled_default: bool = True,
    ) -> None:
        """Update a sensor."""
        device_key = BluetoothDeviceKey(device_id, key)
        self._entity_descriptions_updates[
            device_key
        ] = BluetoothSensorEntityDescription(
            key=key,
            device_key=device_key,
            name=name or self._get_key_name(key, device_id),
            native_unit_of_measurement=native_unit_of_measurement,
            device_class=device_class,
            state_class=state_class,
            native_value=native_value,
            entity_registry_enabled_default=entity_registry_enabled_default,
        )

    def update_binary_sensor(
        self,
        key: str,
        is_on: bool | None,
        device_class: BinarySensorDeviceClass | None,
        name: str | None = None,
        device_id: str | None = None,
        entity_registry_enabled_default: bool = True,
    ) -> None:
        """Update a binary_sensor."""
        device_key = BluetoothDeviceKey(device_id, key)
        self._entity_descriptions_updates[
            device_key
        ] = BluetoothBinarySensorEntityDescription(
            key=key,
            device_key=device_key,
            name=name or self._get_key_name(key, device_id),
            device_class=device_class,
            is_on=is_on,
            entity_registry_enabled_default=entity_registry_enabled_default,
        )
