"""Tests for the Bluetooth integration."""

import logging
from unittest.mock import MagicMock, patch

from home_assistant_bluetooth import BluetoothServiceInfo

from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdate,
    PassiveBluetoothDataUpdateCoordinator,
    PassiveBluetoothEntityKey,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo

_LOGGER = logging.getLogger(__name__)


GENERIC_BLUETOOTH_SERVICE_INFO = BluetoothServiceInfo(
    name="Generic",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-95,
    manufacturer_data={
        1: b"\x01\x01\x01\x01\x01\x01\x01\x01",
    },
    service_data={},
    service_uuids=[],
    source="local",
)
GENERIC_PASSIVE_BLUETOOTH_DATA_UPDATE = PassiveBluetoothDataUpdate(
    devices={
        None: DeviceInfo(
            name="Test Device", model="Test Model", manufacturer="Test Manufacturer"
        ),
    },
    entity_data={
        PassiveBluetoothEntityKey("temperature", None): 14.5,
        PassiveBluetoothEntityKey("pressure", None): 1234,
    },
    entity_descriptions={
        PassiveBluetoothEntityKey("temperature", None): SensorEntityDescription(
            key="temperature",
            name="Test Temperature",
            native_unit_of_measurement=TEMP_CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        ),
        PassiveBluetoothEntityKey("pressure", None): SensorEntityDescription(
            key="pressure",
            name="Test Pressure",
            native_unit_of_measurement="hPa",
            device_class=SensorDeviceClass.PRESSURE,
        ),
    },
)


async def test_basic_usage(hass):
    """Test basic usage of the PassiveBluetoothDataUpdateCoordinator."""

    @callback
    def _async_generate_mock_data(
        service_info: BluetoothServiceInfo,
    ) -> PassiveBluetoothDataUpdate:
        """Generate mock data."""
        return GENERIC_PASSIVE_BLUETOOTH_DATA_UPDATE

    coordinator = PassiveBluetoothDataUpdateCoordinator(
        hass, _LOGGER, "aa:bb:cc:dd:ee:ff", _async_generate_mock_data
    )
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.passive_update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        cancel_coordinator = coordinator.async_setup()

    entity_key = PassiveBluetoothEntityKey("temperature", None)
    entity_key_events = []
    all_events = []
    mock_entity = MagicMock()
    mock_add_entities = MagicMock()

    def _async_entity_key_listener(data: PassiveBluetoothDataUpdate | None):
        """Mock entity key listener."""
        entity_key_events.append(data)

    cancel_async_add_entity_key_listener = coordinator.async_add_entity_key_listener(
        _async_entity_key_listener,
        entity_key,
    )

    def _all_listener(data: PassiveBluetoothDataUpdate | None):
        """Mock an all listener."""
        all_events.append(data)

    cancel_listener = coordinator.async_add_listener(
        _all_listener,
    )

    cancel_async_add_entities_listener = coordinator.async_add_entities_listener(
        mock_entity,
        mock_add_entities,
    )

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)

    # Each listener should receive the same data
    # since both match
    assert len(entity_key_events) == 1
    assert len(all_events) == 1

    # There should be 2 calls to create entities
    assert len(mock_entity.mock_calls) == 2

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)

    # Each listener should receive the same data
    # since both match
    assert len(entity_key_events) == 2
    assert len(all_events) == 2

    # On the second, the entties should already be created
    # so the mock should not be called again
    assert len(mock_entity.mock_calls) == 2

    cancel_async_add_entity_key_listener()
    cancel_listener()
    cancel_async_add_entities_listener()

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)

    # Each listener should not trigger any more now
    # that they were cancelled
    assert len(entity_key_events) == 2
    assert len(all_events) == 2
    assert len(mock_entity.mock_calls) == 2

    cancel_coordinator()


GOVEE_B5178_REMOTE_SERVICE_INFO = BluetoothServiceInfo(
    name="B5178D6FB",
    address="749A17CB-F7A9-D466-C29F-AABE601938A0",
    rssi=-95,
    manufacturer_data={
        1: b"\x01\x01\x01\x04\xb5\xa2d\x00\x06L\x00\x02\x15INTELLI_ROCKS_HWPu\xf2\xff\xc2"
    },
    service_data={},
    service_uuids=["0000ec88-0000-1000-8000-00805f9b34fb"],
    source="local",
)
GOVEE_B5178_PRIMARY_SERVICE_INFO = BluetoothServiceInfo(
    name="B5178D6FB",
    address="749A17CB-F7A9-D466-C29F-AABE601938A0",
    rssi=-92,
    manufacturer_data={
        1: b"\x01\x01\x00\x03\x07Xd\x00\x00L\x00\x02\x15INTELLI_ROCKS_HWPu\xf2\xff\xc2"
    },
    service_data={},
    service_uuids=["0000ec88-0000-1000-8000-00805f9b34fb"],
    source="local",
)

GOVEE_B5178_REMOTE_PASSIVE_BLUETOOTH_DATA_UPDATE = PassiveBluetoothDataUpdate(
    devices={
        "remote": {
            "name": "B5178D6FB Remote",
            "manufacturer": "Govee",
            "model": "H5178-REMOTE",
        },
    },
    entity_descriptions={
        PassiveBluetoothEntityKey(
            key="temperature", device_id="remote"
        ): SensorEntityDescription(
            key="temperature_remote",
            device_class=SensorDeviceClass.TEMPERATURE,
            entity_category=None,
            entity_registry_enabled_default=True,
            entity_registry_visible_default=True,
            force_update=False,
            icon=None,
            has_entity_name=False,
            name="B5178D6FB Remote Temperature",
            unit_of_measurement=None,
            last_reset=None,
            native_unit_of_measurement="°C",
            state_class=None,
        ),
        PassiveBluetoothEntityKey(
            key="humidity", device_id="remote"
        ): SensorEntityDescription(
            key="humidity_remote",
            device_class=SensorDeviceClass.HUMIDITY,
            entity_category=None,
            entity_registry_enabled_default=True,
            entity_registry_visible_default=True,
            force_update=False,
            icon=None,
            has_entity_name=False,
            name="B5178D6FB Remote Humidity",
            unit_of_measurement=None,
            last_reset=None,
            native_unit_of_measurement="%",
            state_class=None,
        ),
        PassiveBluetoothEntityKey(
            key="battery", device_id="remote"
        ): SensorEntityDescription(
            key="battery_remote",
            device_class=SensorDeviceClass.BATTERY,
            entity_category=None,
            entity_registry_enabled_default=True,
            entity_registry_visible_default=True,
            force_update=False,
            icon=None,
            has_entity_name=False,
            name="B5178D6FB Remote Battery",
            unit_of_measurement=None,
            last_reset=None,
            native_unit_of_measurement="%",
            state_class=None,
        ),
        PassiveBluetoothEntityKey(
            key="signal_strength", device_id="remote"
        ): SensorEntityDescription(
            key="signal_strength_remote",
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            entity_category=None,
            entity_registry_enabled_default=False,
            entity_registry_visible_default=True,
            force_update=False,
            icon=None,
            has_entity_name=False,
            name="B5178D6FB Remote Signal_Strength",
            unit_of_measurement=None,
            last_reset=None,
            native_unit_of_measurement="dBm",
            state_class=None,
        ),
    },
    entity_data={
        PassiveBluetoothEntityKey(key="temperature", device_id="remote"): 30.8642,
        PassiveBluetoothEntityKey(key="humidity", device_id="remote"): 64.2,
        PassiveBluetoothEntityKey(key="battery", device_id="remote"): 100,
        PassiveBluetoothEntityKey(key="signal_strength", device_id="remote"): -95,
    },
)
GOVEE_B5178_PRIMARY_AND_REMOTE_PASSIVE_BLUETOOTH_DATA_UPDATE = (
    PassiveBluetoothDataUpdate(
        devices={
            "remote": {
                "name": "B5178D6FB Remote",
                "manufacturer": "Govee",
                "model": "H5178-REMOTE",
            },
            "primary": {
                "name": "B5178D6FB Primary",
                "manufacturer": "Govee",
                "model": "H5178",
            },
        },
        entity_descriptions={
            PassiveBluetoothEntityKey(
                key="temperature", device_id="remote"
            ): SensorEntityDescription(
                key="temperature_remote",
                device_class=SensorDeviceClass.TEMPERATURE,
                entity_category=None,
                entity_registry_enabled_default=True,
                entity_registry_visible_default=True,
                force_update=False,
                icon=None,
                has_entity_name=False,
                name="B5178D6FB Remote Temperature",
                unit_of_measurement=None,
                last_reset=None,
                native_unit_of_measurement="°C",
                state_class=None,
            ),
            PassiveBluetoothEntityKey(
                key="humidity", device_id="remote"
            ): SensorEntityDescription(
                key="humidity_remote",
                device_class=SensorDeviceClass.HUMIDITY,
                entity_category=None,
                entity_registry_enabled_default=True,
                entity_registry_visible_default=True,
                force_update=False,
                icon=None,
                has_entity_name=False,
                name="B5178D6FB Remote Humidity",
                unit_of_measurement=None,
                last_reset=None,
                native_unit_of_measurement="%",
                state_class=None,
            ),
            PassiveBluetoothEntityKey(
                key="battery", device_id="remote"
            ): SensorEntityDescription(
                key="battery_remote",
                device_class=SensorDeviceClass.BATTERY,
                entity_category=None,
                entity_registry_enabled_default=True,
                entity_registry_visible_default=True,
                force_update=False,
                icon=None,
                has_entity_name=False,
                name="B5178D6FB Remote Battery",
                unit_of_measurement=None,
                last_reset=None,
                native_unit_of_measurement="%",
                state_class=None,
            ),
            PassiveBluetoothEntityKey(
                key="signal_strength", device_id="remote"
            ): SensorEntityDescription(
                key="signal_strength_remote",
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                entity_category=None,
                entity_registry_enabled_default=False,
                entity_registry_visible_default=True,
                force_update=False,
                icon=None,
                has_entity_name=False,
                name="B5178D6FB Remote Signal_Strength",
                unit_of_measurement=None,
                last_reset=None,
                native_unit_of_measurement="dBm",
                state_class=None,
            ),
            PassiveBluetoothEntityKey(
                key="temperature", device_id="primary"
            ): SensorEntityDescription(
                key="temperature_primary",
                device_class=SensorDeviceClass.TEMPERATURE,
                entity_category=None,
                entity_registry_enabled_default=True,
                entity_registry_visible_default=True,
                force_update=False,
                icon=None,
                has_entity_name=False,
                name="B5178D6FB Primary Temperature",
                unit_of_measurement=None,
                last_reset=None,
                native_unit_of_measurement="°C",
                state_class=None,
            ),
            PassiveBluetoothEntityKey(
                key="humidity", device_id="primary"
            ): SensorEntityDescription(
                key="humidity_primary",
                device_class=SensorDeviceClass.HUMIDITY,
                entity_category=None,
                entity_registry_enabled_default=True,
                entity_registry_visible_default=True,
                force_update=False,
                icon=None,
                has_entity_name=False,
                name="B5178D6FB Primary Humidity",
                unit_of_measurement=None,
                last_reset=None,
                native_unit_of_measurement="%",
                state_class=None,
            ),
            PassiveBluetoothEntityKey(
                key="battery", device_id="primary"
            ): SensorEntityDescription(
                key="battery_primary",
                device_class=SensorDeviceClass.BATTERY,
                entity_category=None,
                entity_registry_enabled_default=True,
                entity_registry_visible_default=True,
                force_update=False,
                icon=None,
                has_entity_name=False,
                name="B5178D6FB Primary Battery",
                unit_of_measurement=None,
                last_reset=None,
                native_unit_of_measurement="%",
                state_class=None,
            ),
            PassiveBluetoothEntityKey(
                key="signal_strength", device_id="primary"
            ): SensorEntityDescription(
                key="signal_strength_primary",
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                entity_category=None,
                entity_registry_enabled_default=False,
                entity_registry_visible_default=True,
                force_update=False,
                icon=None,
                has_entity_name=False,
                name="B5178D6FB Primary Signal_Strength",
                unit_of_measurement=None,
                last_reset=None,
                native_unit_of_measurement="dBm",
                state_class=None,
            ),
        },
        entity_data={
            PassiveBluetoothEntityKey(key="temperature", device_id="remote"): 30.8642,
            PassiveBluetoothEntityKey(key="humidity", device_id="remote"): 64.2,
            PassiveBluetoothEntityKey(key="battery", device_id="remote"): 100,
            PassiveBluetoothEntityKey(key="signal_strength", device_id="remote"): -92,
            PassiveBluetoothEntityKey(key="temperature", device_id="primary"): 19.8488,
            PassiveBluetoothEntityKey(key="humidity", device_id="primary"): 48.8,
            PassiveBluetoothEntityKey(key="battery", device_id="primary"): 100,
            PassiveBluetoothEntityKey(key="signal_strength", device_id="primary"): -92,
        },
    )
)
