"""Tests for the Bluetooth integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from unittest.mock import MagicMock, patch

from home_assistant_bluetooth import BluetoothServiceInfo
import pytest

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.bluetooth import (
    DOMAIN,
    BluetoothChange,
    BluetoothScanningMode,
)
from homeassistant.components.bluetooth.const import UNAVAILABLE_TRACK_SECONDS
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorCoordinator,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import CoreState, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import patch_all_discovered_devices, patch_connectable_history, patch_history

from tests.common import MockEntityPlatform, async_fire_time_changed

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
    entity_names={
        PassiveBluetoothEntityKey("temperature", None): "Temperature",
        PassiveBluetoothEntityKey("pressure", None): "Pressure",
    },
    entity_descriptions={
        PassiveBluetoothEntityKey("temperature", None): SensorEntityDescription(
            key="temperature",
            native_unit_of_measurement=TEMP_CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        ),
        PassiveBluetoothEntityKey("pressure", None): SensorEntityDescription(
            key="pressure",
            native_unit_of_measurement="hPa",
            device_class=SensorDeviceClass.PRESSURE,
        ),
    },
)


async def test_basic_usage(hass, mock_bleak_scanner_start):
    """Test basic usage of the PassiveBluetoothProcessorCoordinator."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    @callback
    def _mock_update_method(
        service_info: BluetoothServiceInfo,
    ) -> dict[str, str]:
        return {"test": "data"}

    @callback
    def _async_generate_mock_data(
        data: dict[str, str],
    ) -> PassiveBluetoothDataUpdate:
        """Generate mock data."""
        assert data == {"test": "data"}
        return GENERIC_PASSIVE_BLUETOOTH_DATA_UPDATE

    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        "aa:bb:cc:dd:ee:ff",
        BluetoothScanningMode.ACTIVE,
        _mock_update_method,
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        unregister_processor = coordinator.async_register_processor(processor)
        cancel_coordinator = coordinator.async_start()

    entity_key = PassiveBluetoothEntityKey("temperature", None)
    entity_key_events = []
    all_events = []
    mock_entity = MagicMock()
    mock_add_entities = MagicMock()

    def _async_entity_key_listener(data: PassiveBluetoothDataUpdate | None) -> None:
        """Mock entity key listener."""
        entity_key_events.append(data)

    cancel_async_add_entity_key_listener = processor.async_add_entity_key_listener(
        _async_entity_key_listener,
        entity_key,
    )

    def _all_listener(data: PassiveBluetoothDataUpdate | None) -> None:
        """Mock an all listener."""
        all_events.append(data)

    cancel_listener = processor.async_add_listener(
        _all_listener,
    )

    cancel_async_add_entities_listener = processor.async_add_entities_listener(
        mock_entity,
        mock_add_entities,
    )

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)

    # Each listener should receive the same data
    # since both match
    assert len(entity_key_events) == 1
    assert len(all_events) == 1

    # There should be 4 calls to create entities
    assert len(mock_entity.mock_calls) == 2

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)

    # Each listener should receive the same data
    # since both match
    assert len(entity_key_events) == 2
    assert len(all_events) == 2

    # On the second, the entities should already be created
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
    assert coordinator.available is True

    unregister_processor()
    cancel_coordinator()


async def test_unavailable_after_no_data(hass, mock_bleak_scanner_start):
    """Test that the coordinator is unavailable after no data for a while."""
    with patch(
        "bleak.BleakScanner.discovered_devices",  # Must patch before we setup
        [MagicMock(address="44:44:33:11:23:45")],
    ):
        await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

    @callback
    def _mock_update_method(
        service_info: BluetoothServiceInfo,
    ) -> dict[str, str]:
        return {"test": "data"}

    @callback
    def _async_generate_mock_data(
        data: dict[str, str],
    ) -> PassiveBluetoothDataUpdate:
        """Generate mock data."""
        return GENERIC_PASSIVE_BLUETOOTH_DATA_UPDATE

    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        "aa:bb:cc:dd:ee:ff",
        BluetoothScanningMode.ACTIVE,
        _mock_update_method,
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)
    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        unregister_processor = coordinator.async_register_processor(processor)
        cancel_coordinator = coordinator.async_start()

    mock_entity = MagicMock()
    mock_add_entities = MagicMock()
    processor.async_add_entities_listener(
        mock_entity,
        mock_add_entities,
    )

    assert coordinator.available is False
    assert processor.available is False

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert len(mock_add_entities.mock_calls) == 1
    assert coordinator.available is True
    assert processor.available is True
    with patch_all_discovered_devices(
        [MagicMock(address="44:44:33:11:23:45")]
    ), patch_history({"aa:bb:cc:dd:ee:ff": MagicMock()}), patch_connectable_history(
        {"aa:bb:cc:dd:ee:ff": MagicMock()},
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()
    assert coordinator.available is False
    assert processor.available is False

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert len(mock_add_entities.mock_calls) == 1
    assert coordinator.available is True
    assert processor.available is True

    with patch_all_discovered_devices(
        [MagicMock(address="44:44:33:11:23:45")]
    ), patch_history({"aa:bb:cc:dd:ee:ff": MagicMock()}), patch_connectable_history(
        {"aa:bb:cc:dd:ee:ff": MagicMock()},
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()
    assert coordinator.available is False
    assert processor.available is False

    unregister_processor()
    cancel_coordinator()


async def test_no_updates_once_stopping(hass, mock_bleak_scanner_start):
    """Test updates are ignored once hass is stopping."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    @callback
    def _mock_update_method(
        service_info: BluetoothServiceInfo,
    ) -> dict[str, str]:
        return {"test": "data"}

    @callback
    def _async_generate_mock_data(
        data: dict[str, str],
    ) -> PassiveBluetoothDataUpdate:
        """Generate mock data."""
        return GENERIC_PASSIVE_BLUETOOTH_DATA_UPDATE

    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        "aa:bb:cc:dd:ee:ff",
        BluetoothScanningMode.ACTIVE,
        _mock_update_method,
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        unregister_processor = coordinator.async_register_processor(processor)
        cancel_coordinator = coordinator.async_start()

    all_events = []

    def _all_listener(data: PassiveBluetoothDataUpdate | None) -> None:
        """Mock an all listener."""
        all_events.append(data)

    processor.async_add_listener(
        _all_listener,
    )

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert len(all_events) == 1

    hass.state = CoreState.stopping

    # We should stop processing events once hass is stopping
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert len(all_events) == 1
    unregister_processor()
    cancel_coordinator()


async def test_exception_from_update_method(hass, caplog, mock_bleak_scanner_start):
    """Test we handle exceptions from the update method."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    run_count = 0

    @callback
    def _mock_update_method(
        service_info: BluetoothServiceInfo,
    ) -> dict[str, str]:
        return {"test": "data"}

    @callback
    def _async_generate_mock_data(
        data: dict[str, str],
    ) -> PassiveBluetoothDataUpdate:
        """Generate mock data."""
        nonlocal run_count
        run_count += 1
        if run_count == 2:
            raise Exception("Test exception")
        return GENERIC_PASSIVE_BLUETOOTH_DATA_UPDATE

    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        "aa:bb:cc:dd:ee:ff",
        BluetoothScanningMode.ACTIVE,
        _mock_update_method,
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)
    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        unregister_processor = coordinator.async_register_processor(processor)
        cancel_coordinator = coordinator.async_start()

    processor.async_add_listener(MagicMock())

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert processor.available is True

    # We should go unavailable once we get an exception
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert "Test exception" in caplog.text
    assert processor.available is False

    # We should go available again once we get data again
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert processor.available is True
    unregister_processor()
    cancel_coordinator()


async def test_bad_data_from_update_method(hass, mock_bleak_scanner_start):
    """Test we handle bad data from the update method."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    run_count = 0

    @callback
    def _mock_update_method(
        service_info: BluetoothServiceInfo,
    ) -> dict[str, str]:
        return {"test": "data"}

    @callback
    def _async_generate_mock_data(
        data: dict[str, str],
    ) -> PassiveBluetoothDataUpdate:
        """Generate mock data."""
        nonlocal run_count
        run_count += 1
        if run_count == 2:
            return "bad_data"
        return GENERIC_PASSIVE_BLUETOOTH_DATA_UPDATE

    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        "aa:bb:cc:dd:ee:ff",
        BluetoothScanningMode.ACTIVE,
        _mock_update_method,
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)
    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        unregister_processor = coordinator.async_register_processor(processor)
        cancel_coordinator = coordinator.async_start()

    processor.async_add_listener(MagicMock())

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert processor.available is True

    # We should go unavailable once we get bad data
    with pytest.raises(ValueError):
        saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)

    assert processor.available is False

    # We should go available again once we get good data again
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert processor.available is True
    unregister_processor()
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
            unit_of_measurement=None,
            last_reset=None,
            native_unit_of_measurement="dBm",
            state_class=None,
        ),
    },
    entity_names={
        PassiveBluetoothEntityKey(key="temperature", device_id="remote"): "Temperature",
        PassiveBluetoothEntityKey(key="humidity", device_id="remote"): "Humidity",
        PassiveBluetoothEntityKey(key="battery", device_id="remote"): "Battery",
        PassiveBluetoothEntityKey(
            key="signal_strength", device_id="remote"
        ): "Signal Strength",
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
                unit_of_measurement=None,
                last_reset=None,
                native_unit_of_measurement="dBm",
                state_class=None,
            ),
        },
        entity_names={
            PassiveBluetoothEntityKey(
                key="temperature", device_id="remote"
            ): "Temperature",
            PassiveBluetoothEntityKey(key="humidity", device_id="remote"): "Humidity",
            PassiveBluetoothEntityKey(key="battery", device_id="remote"): "Battery",
            PassiveBluetoothEntityKey(
                key="signal_strength", device_id="remote"
            ): "Signal Strength",
            PassiveBluetoothEntityKey(
                key="temperature", device_id="primary"
            ): "Temperature",
            PassiveBluetoothEntityKey(key="humidity", device_id="primary"): "Humidity",
            PassiveBluetoothEntityKey(key="battery", device_id="primary"): "Battery",
            PassiveBluetoothEntityKey(
                key="signal_strength", device_id="primary"
            ): "Signal Strength",
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


async def test_integration_with_entity(hass, mock_bleak_scanner_start):
    """Test integration of PassiveBluetoothProcessorCoordinator with PassiveBluetoothCoordinatorEntity."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    update_count = 0

    @callback
    def _mock_update_method(
        service_info: BluetoothServiceInfo,
    ) -> dict[str, str]:
        return {"test": "data"}

    @callback
    def _async_generate_mock_data(
        data: dict[str, str],
    ) -> PassiveBluetoothDataUpdate:
        """Generate mock data."""
        nonlocal update_count
        update_count += 1
        if update_count > 2:
            return GOVEE_B5178_PRIMARY_AND_REMOTE_PASSIVE_BLUETOOTH_DATA_UPDATE
        return GOVEE_B5178_REMOTE_PASSIVE_BLUETOOTH_DATA_UPDATE

    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        "aa:bb:cc:dd:ee:ff",
        BluetoothScanningMode.ACTIVE,
        _mock_update_method,
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)
    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        coordinator.async_register_processor(processor)
        cancel_coordinator = coordinator.async_start()

    processor.async_add_listener(MagicMock())

    mock_add_entities = MagicMock()

    processor.async_add_entities_listener(
        PassiveBluetoothProcessorEntity,
        mock_add_entities,
    )

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    # First call with just the remote sensor entities results in them being added
    assert len(mock_add_entities.mock_calls) == 1

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    # Second call with just the remote sensor entities does not add them again
    assert len(mock_add_entities.mock_calls) == 1

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    # Third call with primary and remote sensor entities adds the primary sensor entities
    assert len(mock_add_entities.mock_calls) == 2

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    # Forth call with both primary and remote sensor entities does not add them again
    assert len(mock_add_entities.mock_calls) == 2

    entities = [
        *mock_add_entities.mock_calls[0][1][0],
        *mock_add_entities.mock_calls[1][1][0],
    ]

    entity_one: PassiveBluetoothProcessorEntity = entities[0]
    entity_one.hass = hass
    assert entity_one.available is True
    assert entity_one.unique_id == "aa:bb:cc:dd:ee:ff-temperature-remote"
    assert entity_one.device_info == {
        "identifiers": {("bluetooth", "aa:bb:cc:dd:ee:ff-remote")},
        "manufacturer": "Govee",
        "model": "H5178-REMOTE",
        "name": "B5178D6FB Remote",
    }
    assert entity_one.entity_key == PassiveBluetoothEntityKey(
        key="temperature", device_id="remote"
    )
    cancel_coordinator()


NO_DEVICES_BLUETOOTH_SERVICE_INFO = BluetoothServiceInfo(
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
NO_DEVICES_PASSIVE_BLUETOOTH_DATA_UPDATE = PassiveBluetoothDataUpdate(
    devices={},
    entity_data={
        PassiveBluetoothEntityKey("temperature", None): 14.5,
        PassiveBluetoothEntityKey("pressure", None): 1234,
    },
    entity_descriptions={
        PassiveBluetoothEntityKey("temperature", None): SensorEntityDescription(
            key="temperature",
            name="Temperature",
            native_unit_of_measurement=TEMP_CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        ),
        PassiveBluetoothEntityKey("pressure", None): SensorEntityDescription(
            key="pressure",
            name="Pressure",
            native_unit_of_measurement="hPa",
            device_class=SensorDeviceClass.PRESSURE,
        ),
    },
)


async def test_integration_with_entity_without_a_device(hass, mock_bleak_scanner_start):
    """Test integration with PassiveBluetoothCoordinatorEntity with no device."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    @callback
    def _mock_update_method(
        service_info: BluetoothServiceInfo,
    ) -> dict[str, str]:
        return {"test": "data"}

    @callback
    def _async_generate_mock_data(
        data: dict[str, str],
    ) -> PassiveBluetoothDataUpdate:
        """Generate mock data."""
        return NO_DEVICES_PASSIVE_BLUETOOTH_DATA_UPDATE

    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        "aa:bb:cc:dd:ee:ff",
        BluetoothScanningMode.ACTIVE,
        _mock_update_method,
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)
    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        coordinator.async_register_processor(processor)
        cancel_coordinator = coordinator.async_start()

    mock_add_entities = MagicMock()

    processor.async_add_entities_listener(
        PassiveBluetoothProcessorEntity,
        mock_add_entities,
    )

    saved_callback(NO_DEVICES_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    # First call with just the remote sensor entities results in them being added
    assert len(mock_add_entities.mock_calls) == 1

    saved_callback(NO_DEVICES_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    # Second call with just the remote sensor entities does not add them again
    assert len(mock_add_entities.mock_calls) == 1

    entities = mock_add_entities.mock_calls[0][1][0]
    entity_one: PassiveBluetoothProcessorEntity = entities[0]
    entity_one.hass = hass
    assert entity_one.available is True
    assert entity_one.unique_id == "aa:bb:cc:dd:ee:ff-temperature"
    assert entity_one.device_info == {
        "identifiers": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "name": "Generic",
    }
    assert entity_one.entity_key == PassiveBluetoothEntityKey(
        key="temperature", device_id=None
    )
    cancel_coordinator()


async def test_passive_bluetooth_entity_with_entity_platform(
    hass, mock_bleak_scanner_start
):
    """Test with a mock entity platform."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    entity_platform = MockEntityPlatform(hass)

    @callback
    def _mock_update_method(
        service_info: BluetoothServiceInfo,
    ) -> dict[str, str]:
        return {"test": "data"}

    @callback
    def _async_generate_mock_data(
        data: dict[str, str],
    ) -> PassiveBluetoothDataUpdate:
        """Generate mock data."""
        return NO_DEVICES_PASSIVE_BLUETOOTH_DATA_UPDATE

    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        "aa:bb:cc:dd:ee:ff",
        BluetoothScanningMode.ACTIVE,
        _mock_update_method,
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)
    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        coordinator.async_register_processor(processor)
        cancel_coordinator = coordinator.async_start()

    processor.async_add_entities_listener(
        PassiveBluetoothProcessorEntity,
        lambda entities: hass.async_create_task(
            entity_platform.async_add_entities(entities)
        ),
    )
    saved_callback(NO_DEVICES_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    saved_callback(NO_DEVICES_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    assert (
        hass.states.get("test_domain.test_platform_aa_bb_cc_dd_ee_ff_temperature")
        is not None
    )
    assert (
        hass.states.get("test_domain.test_platform_aa_bb_cc_dd_ee_ff_pressure")
        is not None
    )
    cancel_coordinator()


SENSOR_PASSIVE_BLUETOOTH_DATA_UPDATE = PassiveBluetoothDataUpdate(
    devices={
        None: DeviceInfo(
            name="Test Device", model="Test Model", manufacturer="Test Manufacturer"
        ),
    },
    entity_data={
        PassiveBluetoothEntityKey("pressure", None): 1234,
    },
    entity_names={
        PassiveBluetoothEntityKey("pressure", None): "Pressure",
    },
    entity_descriptions={
        PassiveBluetoothEntityKey("pressure", None): SensorEntityDescription(
            key="pressure",
            native_unit_of_measurement="hPa",
            device_class=SensorDeviceClass.PRESSURE,
        ),
    },
)


BINARY_SENSOR_PASSIVE_BLUETOOTH_DATA_UPDATE = PassiveBluetoothDataUpdate(
    devices={
        None: DeviceInfo(
            name="Test Device", model="Test Model", manufacturer="Test Manufacturer"
        ),
    },
    entity_data={
        PassiveBluetoothEntityKey("motion", None): True,
    },
    entity_names={
        PassiveBluetoothEntityKey("motion", None): "Motion",
    },
    entity_descriptions={
        PassiveBluetoothEntityKey("motion", None): BinarySensorEntityDescription(
            key="motion",
            device_class=BinarySensorDeviceClass.MOTION,
        ),
    },
)


async def test_integration_multiple_entity_platforms(hass, mock_bleak_scanner_start):
    """Test integration of PassiveBluetoothProcessorCoordinator with multiple platforms."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    @callback
    def _mock_update_method(
        service_info: BluetoothServiceInfo,
    ) -> dict[str, str]:
        return {"test": "data"}

    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        "aa:bb:cc:dd:ee:ff",
        BluetoothScanningMode.ACTIVE,
        _mock_update_method,
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    binary_sensor_processor = PassiveBluetoothDataProcessor(
        lambda service_info: BINARY_SENSOR_PASSIVE_BLUETOOTH_DATA_UPDATE
    )
    sesnor_processor = PassiveBluetoothDataProcessor(
        lambda service_info: SENSOR_PASSIVE_BLUETOOTH_DATA_UPDATE
    )

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        coordinator.async_register_processor(binary_sensor_processor)
        coordinator.async_register_processor(sesnor_processor)
        cancel_coordinator = coordinator.async_start()

    binary_sensor_processor.async_add_listener(MagicMock())
    sesnor_processor.async_add_listener(MagicMock())

    mock_add_sensor_entities = MagicMock()
    mock_add_binary_sensor_entities = MagicMock()

    sesnor_processor.async_add_entities_listener(
        PassiveBluetoothProcessorEntity,
        mock_add_sensor_entities,
    )
    binary_sensor_processor.async_add_entities_listener(
        PassiveBluetoothProcessorEntity,
        mock_add_binary_sensor_entities,
    )

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    # First call with just the remote sensor entities results in them being added
    assert len(mock_add_binary_sensor_entities.mock_calls) == 1
    assert len(mock_add_sensor_entities.mock_calls) == 1

    binary_sesnor_entities = [
        *mock_add_binary_sensor_entities.mock_calls[0][1][0],
    ]
    sesnor_entities = [
        *mock_add_sensor_entities.mock_calls[0][1][0],
    ]

    sensor_entity_one: PassiveBluetoothProcessorEntity = sesnor_entities[0]
    sensor_entity_one.hass = hass
    assert sensor_entity_one.available is True
    assert sensor_entity_one.unique_id == "aa:bb:cc:dd:ee:ff-pressure"
    assert sensor_entity_one.device_info == {
        "identifiers": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "manufacturer": "Test Manufacturer",
        "model": "Test Model",
        "name": "Test Device",
    }
    assert sensor_entity_one.entity_key == PassiveBluetoothEntityKey(
        key="pressure", device_id=None
    )

    binary_sensor_entity_one: PassiveBluetoothProcessorEntity = binary_sesnor_entities[
        0
    ]
    binary_sensor_entity_one.hass = hass
    assert binary_sensor_entity_one.available is True
    assert binary_sensor_entity_one.unique_id == "aa:bb:cc:dd:ee:ff-motion"
    assert binary_sensor_entity_one.device_info == {
        "identifiers": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "manufacturer": "Test Manufacturer",
        "model": "Test Model",
        "name": "Test Device",
    }
    assert binary_sensor_entity_one.entity_key == PassiveBluetoothEntityKey(
        key="motion", device_id=None
    )
    cancel_coordinator()


async def test_exception_from_coordinator_update_method(
    hass, caplog, mock_bleak_scanner_start
):
    """Test we handle exceptions from the update method."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    run_count = 0

    @callback
    def _mock_update_method(
        service_info: BluetoothServiceInfo,
    ) -> dict[str, str]:
        nonlocal run_count
        run_count += 1
        if run_count == 2:
            raise Exception("Test exception")
        return {"test": "data"}

    @callback
    def _async_generate_mock_data(
        data: dict[str, str],
    ) -> PassiveBluetoothDataUpdate:
        """Generate mock data."""
        return GENERIC_PASSIVE_BLUETOOTH_DATA_UPDATE

    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        "aa:bb:cc:dd:ee:ff",
        BluetoothScanningMode.ACTIVE,
        _mock_update_method,
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)
    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        unregister_processor = coordinator.async_register_processor(processor)
        cancel_coordinator = coordinator.async_start()

    processor.async_add_listener(MagicMock())

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert processor.available is True

    # We should go unavailable once we get an exception
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert "Test exception" in caplog.text
    assert processor.available is False

    # We should go available again once we get data again
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert processor.available is True
    unregister_processor()
    cancel_coordinator()
