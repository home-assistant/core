"""Tests for the Bluetooth integration."""

from __future__ import annotations

from datetime import timedelta
import logging
import time
from typing import Any
from unittest.mock import MagicMock, patch

from home_assistant_bluetooth import BluetoothServiceInfo
import pytest

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.bluetooth import (
    DOMAIN,
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.const import UNAVAILABLE_TRACK_SECONDS
from homeassistant.components.bluetooth.passive_update_processor import (
    STORAGE_KEY,
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorCoordinator,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.config_entries import current_entry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import UNDEFINED
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    inject_bluetooth_service_info,
    inject_bluetooth_service_info_bleak,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)

from tests.common import (
    MockConfigEntry,
    MockEntityPlatform,
    async_fire_time_changed,
    async_test_home_assistant,
)

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
GENERIC_BLUETOOTH_SERVICE_INFO_2 = BluetoothServiceInfo(
    name="Generic",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-95,
    manufacturer_data={
        1: b"\x01\x01\x01\x01\x01\x01\x01\x01",
        2: b"\x02",
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
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        ),
        PassiveBluetoothEntityKey("pressure", None): SensorEntityDescription(
            key="pressure",
            native_unit_of_measurement="hPa",
            device_class=SensorDeviceClass.PRESSURE,
        ),
    },
)

GENERIC_PASSIVE_BLUETOOTH_DATA_UPDATE_WITH_TEMP_CHANGE = PassiveBluetoothDataUpdate(
    devices={
        None: DeviceInfo(
            name="Test Device", model="Test Model", manufacturer="Test Manufacturer"
        ),
    },
    entity_data={
        PassiveBluetoothEntityKey("temperature", None): 15.5,
        PassiveBluetoothEntityKey("pressure", None): 1234,
    },
    entity_names={
        PassiveBluetoothEntityKey("temperature", None): "Temperature",
        PassiveBluetoothEntityKey("pressure", None): "Pressure",
    },
    entity_descriptions={
        PassiveBluetoothEntityKey("temperature", None): SensorEntityDescription(
            key="temperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        ),
        PassiveBluetoothEntityKey("pressure", None): SensorEntityDescription(
            key="pressure",
            native_unit_of_measurement="hPa",
            device_class=SensorDeviceClass.PRESSURE,
        ),
    },
)


GENERIC_PASSIVE_BLUETOOTH_DATA_UPDATE_WITH_DEVICE_NAME_AND_TEMP_CHANGE = (
    PassiveBluetoothDataUpdate(
        devices={
            None: DeviceInfo(
                name="Changed", model="Test Model", manufacturer="Test Manufacturer"
            ),
        },
        entity_data={
            PassiveBluetoothEntityKey("temperature", None): 15.5,
            PassiveBluetoothEntityKey("pressure", None): 1234,
        },
        entity_names={
            PassiveBluetoothEntityKey("temperature", None): "Temperature",
            PassiveBluetoothEntityKey("pressure", None): "Pressure",
        },
        entity_descriptions={
            PassiveBluetoothEntityKey("temperature", None): SensorEntityDescription(
                key="temperature",
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
            ),
            PassiveBluetoothEntityKey("pressure", None): SensorEntityDescription(
                key="pressure",
                native_unit_of_measurement="hPa",
                device_class=SensorDeviceClass.PRESSURE,
            ),
        },
    )
)


@pytest.mark.usefixtures("mock_bleak_scanner_start", "mock_bluetooth_adapters")
async def test_basic_usage(hass: HomeAssistant) -> None:
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

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)

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

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)

    # Each listener should receive the same data
    # since both match
    assert len(entity_key_events) == 1
    assert len(all_events) == 1

    # There should be 4 calls to create entities
    assert len(mock_entity.mock_calls) == 2

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)

    # Only the all listener should receive the new data
    # since temperature is not in the new data
    assert len(entity_key_events) == 1
    assert len(all_events) == 2

    # On the second, the entities should already be created
    # so the mock should not be called again
    assert len(mock_entity.mock_calls) == 2

    cancel_async_add_entity_key_listener()
    cancel_listener()
    cancel_async_add_entities_listener()

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)

    # Each listener should not trigger any more now
    # that they were cancelled
    assert len(entity_key_events) == 1
    assert len(all_events) == 2
    assert len(mock_entity.mock_calls) == 2
    assert coordinator.available is True

    unregister_processor()
    cancel_coordinator()


@pytest.mark.usefixtures("mock_bleak_scanner_start", "mock_bluetooth_adapters")
async def test_async_set_updated_data_usage(hass: HomeAssistant) -> None:
    """Test async_set_updated_data of the PassiveBluetoothProcessorCoordinator."""
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

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)

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

    assert coordinator.available is False
    coordinator.async_set_updated_data({"test": "data"})
    assert coordinator.available is True

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)

    # Each listener should receive the same data
    # since both match, and an additional all_events
    # for the async_set_updated_data call
    assert len(entity_key_events) == 1
    assert len(all_events) == 2

    # There should be 4 calls to create entities
    assert len(mock_entity.mock_calls) == 2

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)

    # Only the all listener should receive the new data
    # since temperature is not in the new data, and an additional all_events
    # for the async_set_updated_data call
    assert len(entity_key_events) == 1
    assert len(all_events) == 3

    # On the second, the entities should already be created
    # so the mock should not be called again
    assert len(mock_entity.mock_calls) == 2

    cancel_async_add_entity_key_listener()
    cancel_listener()
    cancel_async_add_entities_listener()

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)

    # Each listener should not trigger any more now
    # that they were cancelled
    assert len(entity_key_events) == 1
    assert len(all_events) == 3
    assert len(mock_entity.mock_calls) == 2
    assert coordinator.available is True

    unregister_processor()
    cancel_coordinator()


@pytest.mark.usefixtures("mock_bleak_scanner_start", "mock_bluetooth_adapters")
async def test_entity_key_is_dispatched_on_entity_key_change(
    hass: HomeAssistant,
) -> None:
    """Test entity key listeners are only dispatched on change."""
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
        assert data == {"test": "data"}
        nonlocal update_count
        update_count += 1
        if update_count > 2:
            return (
                GENERIC_PASSIVE_BLUETOOTH_DATA_UPDATE_WITH_DEVICE_NAME_AND_TEMP_CHANGE
            )
        if update_count > 1:
            return GENERIC_PASSIVE_BLUETOOTH_DATA_UPDATE_WITH_TEMP_CHANGE
        return GENERIC_PASSIVE_BLUETOOTH_DATA_UPDATE

    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        "aa:bb:cc:dd:ee:ff",
        BluetoothScanningMode.ACTIVE,
        _mock_update_method,
    )
    assert coordinator.available is False  # no data yet

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)

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

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)

    # Each listener should receive the same data
    # since both match
    assert len(entity_key_events) == 1
    assert len(all_events) == 1

    # There should be 4 calls to create entities
    assert len(mock_entity.mock_calls) == 2

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)

    # Both listeners should receive the new data
    # since temperature IS in the new data
    assert len(entity_key_events) == 2
    assert len(all_events) == 2

    # On the second, the entities should already be created
    # so the mock should not be called again
    assert len(mock_entity.mock_calls) == 2

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)

    # All listeners should receive the data since
    # the device name changed
    assert len(entity_key_events) == 3
    assert len(all_events) == 3

    # On the second, the entities should already be created
    # so the mock should not be called again
    assert len(mock_entity.mock_calls) == 2

    cancel_async_add_entity_key_listener()
    cancel_listener()
    cancel_async_add_entities_listener()

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)

    # Each listener should not trigger any more now
    # that they were cancelled
    assert len(entity_key_events) == 3
    assert len(all_events) == 3
    assert len(mock_entity.mock_calls) == 2
    assert coordinator.available is True

    unregister_processor()
    cancel_coordinator()


@pytest.mark.usefixtures("mock_bleak_scanner_start", "mock_bluetooth_adapters")
async def test_unavailable_after_no_data(hass: HomeAssistant) -> None:
    """Test that the coordinator is unavailable after no data for a while."""
    start_monotonic = time.monotonic()

    with patch(
        "bleak.BleakScanner.discovered_devices_and_advertisement_data",  # Must patch before we setup
        {"44:44:33:11:23:45": (MagicMock(address="44:44:33:11:23:45"), MagicMock())},
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

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)

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

    now = time.monotonic()
    service_info_at_time = BluetoothServiceInfoBleak(
        name="Generic",
        address="aa:bb:cc:dd:ee:ff",
        rssi=-95,
        manufacturer_data={
            1: b"\x01\x01\x01\x01\x01\x01\x01\x01",
        },
        service_data={},
        service_uuids=[],
        source="local",
        time=now,
        device=MagicMock(),
        advertisement=MagicMock(),
        connectable=True,
        tx_power=0,
    )

    inject_bluetooth_service_info_bleak(hass, service_info_at_time)
    assert len(mock_add_entities.mock_calls) == 1
    assert coordinator.available is True
    assert processor.available is True
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1

    with (
        patch_bluetooth_time(
            monotonic_now,
        ),
        patch_all_discovered_devices([MagicMock(address="44:44:33:11:23:45")]),
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()
    assert coordinator.available is False
    assert processor.available is False
    assert coordinator.last_seen == service_info_at_time.time

    inject_bluetooth_service_info_bleak(hass, service_info_at_time)
    assert len(mock_add_entities.mock_calls) == 1
    assert coordinator.available is True
    assert processor.available is True

    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 2

    with (
        patch_bluetooth_time(
            monotonic_now,
        ),
        patch_all_discovered_devices([MagicMock(address="44:44:33:11:23:45")]),
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()
    assert coordinator.available is False
    assert processor.available is False
    assert coordinator.last_seen == service_info_at_time.time

    unregister_processor()
    cancel_coordinator()


@pytest.mark.usefixtures("mock_bleak_scanner_start", "mock_bluetooth_adapters")
async def test_no_updates_once_stopping(hass: HomeAssistant) -> None:
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

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)

    unregister_processor = coordinator.async_register_processor(processor)
    cancel_coordinator = coordinator.async_start()

    all_events = []

    def _all_listener(data: PassiveBluetoothDataUpdate | None) -> None:
        """Mock an all listener."""
        all_events.append(data)

    processor.async_add_listener(
        _all_listener,
    )

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    assert len(all_events) == 1

    hass.set_state(CoreState.stopping)

    # We should stop processing events once hass is stopping
    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)
    assert len(all_events) == 1
    unregister_processor()
    cancel_coordinator()


@pytest.mark.usefixtures("mock_bleak_scanner_start", "mock_bluetooth_adapters")
async def test_exception_from_update_method(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
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
            raise Exception("Test exception")  # noqa: TRY002
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

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert processor.available is True

    # We should go unavailable once we get an exception
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO_2, BluetoothChange.ADVERTISEMENT)
    assert "Test exception" in caplog.text
    assert processor.available is False

    # We should go available again once we get data again
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert processor.available is True
    unregister_processor()
    cancel_coordinator()


@pytest.mark.usefixtures("mock_bleak_scanner_start", "mock_bluetooth_adapters")
async def test_bad_data_from_update_method(hass: HomeAssistant) -> None:
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

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert processor.available is True

    # We should go unavailable once we get bad data
    with pytest.raises(TypeError):
        saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO_2, BluetoothChange.ADVERTISEMENT)

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


@pytest.mark.usefixtures("mock_bleak_scanner_start", "mock_bluetooth_adapters")
async def test_integration_with_entity(hass: HomeAssistant) -> None:
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

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)

    coordinator.async_register_processor(processor)
    cancel_coordinator = coordinator.async_start()

    processor.async_add_listener(MagicMock())

    mock_add_entities = MagicMock()

    processor.async_add_entities_listener(
        PassiveBluetoothProcessorEntity,
        mock_add_entities,
    )

    entity_key_events = []

    def _async_entity_key_listener(data: PassiveBluetoothDataUpdate | None) -> None:
        """Mock entity key listener."""
        entity_key_events.append(data)

    cancel_async_add_entity_key_listener = processor.async_add_entity_key_listener(
        _async_entity_key_listener,
        PassiveBluetoothEntityKey(key="humidity", device_id="primary"),
    )

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    # First call with just the remote sensor entities results in them being added
    assert len(mock_add_entities.mock_calls) == 1

    # should have triggered the entity key listener since the
    # the device is becoming available
    assert len(entity_key_events) == 1

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)
    # Second call with just the remote sensor entities does not add them again
    assert len(mock_add_entities.mock_calls) == 1

    # should not have triggered the entity key listener since there
    # there is no update with the entity key
    assert len(entity_key_events) == 1

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    # Third call with primary and remote sensor entities adds the primary sensor entities
    assert len(mock_add_entities.mock_calls) == 2

    # should not have triggered the entity key listener since there
    # there is an update with the entity key
    assert len(entity_key_events) == 2

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)
    # Forth call with both primary and remote sensor entities does not add them again
    assert len(mock_add_entities.mock_calls) == 2

    # should not have triggered the entity key listener humidity
    # is not in the update
    assert len(entity_key_events) == 2

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
    cancel_async_add_entity_key_listener()
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

NO_DEVICES_BLUETOOTH_SERVICE_INFO_2 = BluetoothServiceInfo(
    name="Generic",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-95,
    manufacturer_data={
        1: b"\x01\x01\x01\x01\x01\x01\x01\x01",
        2: b"\x02",
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
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
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


@pytest.mark.usefixtures("mock_bleak_scanner_start", "mock_bluetooth_adapters")
async def test_integration_with_entity_without_a_device(hass: HomeAssistant) -> None:
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

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)

    coordinator.async_register_processor(processor)
    cancel_coordinator = coordinator.async_start()

    mock_add_entities = MagicMock()

    processor.async_add_entities_listener(
        PassiveBluetoothProcessorEntity,
        mock_add_entities,
    )

    inject_bluetooth_service_info(hass, NO_DEVICES_BLUETOOTH_SERVICE_INFO)
    # First call with just the remote sensor entities results in them being added
    assert len(mock_add_entities.mock_calls) == 1

    inject_bluetooth_service_info(hass, NO_DEVICES_BLUETOOTH_SERVICE_INFO_2)
    # Second call with just the remote sensor entities does not add them again
    assert len(mock_add_entities.mock_calls) == 1

    entities = mock_add_entities.mock_calls[0][1][0]
    entity_one: PassiveBluetoothProcessorEntity = entities[0]
    entity_one.hass = hass
    assert entity_one.available is True
    assert entity_one.unique_id == "aa:bb:cc:dd:ee:ff-temperature"
    assert entity_one.device_info == {
        "identifiers": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "connections": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "name": "Generic",
    }
    assert entity_one.entity_key == PassiveBluetoothEntityKey(
        key="temperature", device_id=None
    )
    cancel_coordinator()


@pytest.mark.usefixtures("mock_bleak_scanner_start", "mock_bluetooth_adapters")
async def test_passive_bluetooth_entity_with_entity_platform(
    hass: HomeAssistant,
) -> None:
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

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)

    coordinator.async_register_processor(processor)
    cancel_coordinator = coordinator.async_start()

    processor.async_add_entities_listener(
        PassiveBluetoothProcessorEntity,
        lambda entities: hass.async_create_task(
            entity_platform.async_add_entities(entities)
        ),
    )
    inject_bluetooth_service_info(hass, NO_DEVICES_BLUETOOTH_SERVICE_INFO)
    await hass.async_block_till_done()
    inject_bluetooth_service_info(hass, NO_DEVICES_BLUETOOTH_SERVICE_INFO_2)
    await hass.async_block_till_done()
    assert hass.states.get("test_domain.temperature") is not None
    assert hass.states.get("test_domain.pressure") is not None
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


DEVICE_ONLY_PASSIVE_BLUETOOTH_DATA_UPDATE = PassiveBluetoothDataUpdate(
    devices={
        None: DeviceInfo(
            name="Test Device", model="Test Model", manufacturer="Test Manufacturer"
        ),
    },
    entity_data={},
    entity_names={},
    entity_descriptions={},
)


@pytest.mark.usefixtures("mock_bleak_scanner_start", "mock_bluetooth_adapters")
async def test_integration_multiple_entity_platforms(hass: HomeAssistant) -> None:
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

    binary_sensor_processor = PassiveBluetoothDataProcessor(
        lambda service_info: BINARY_SENSOR_PASSIVE_BLUETOOTH_DATA_UPDATE
    )
    sensor_processor = PassiveBluetoothDataProcessor(
        lambda service_info: SENSOR_PASSIVE_BLUETOOTH_DATA_UPDATE
    )

    coordinator.async_register_processor(binary_sensor_processor)
    coordinator.async_register_processor(sensor_processor)
    cancel_coordinator = coordinator.async_start()

    binary_sensor_processor.async_add_listener(MagicMock())
    sensor_processor.async_add_listener(MagicMock())

    mock_add_sensor_entities = MagicMock()
    mock_add_binary_sensor_entities = MagicMock()

    sensor_processor.async_add_entities_listener(
        PassiveBluetoothProcessorEntity,
        mock_add_sensor_entities,
    )
    binary_sensor_processor.async_add_entities_listener(
        PassiveBluetoothProcessorEntity,
        mock_add_binary_sensor_entities,
    )

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    # First call with just the remote sensor entities results in them being added
    assert len(mock_add_binary_sensor_entities.mock_calls) == 1
    assert len(mock_add_sensor_entities.mock_calls) == 1

    binary_sensor_entities = [
        *mock_add_binary_sensor_entities.mock_calls[0][1][0],
    ]
    sensor_entities = [
        *mock_add_sensor_entities.mock_calls[0][1][0],
    ]

    sensor_entity_one: PassiveBluetoothProcessorEntity = sensor_entities[0]
    sensor_entity_one.hass = hass
    assert sensor_entity_one.available is True
    assert sensor_entity_one.unique_id == "aa:bb:cc:dd:ee:ff-pressure"
    assert sensor_entity_one.device_info == {
        "identifiers": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "connections": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "manufacturer": "Test Manufacturer",
        "model": "Test Model",
        "name": "Test Device",
    }
    assert sensor_entity_one.entity_key == PassiveBluetoothEntityKey(
        key="pressure", device_id=None
    )

    binary_sensor_entity_one: PassiveBluetoothProcessorEntity = binary_sensor_entities[
        0
    ]
    binary_sensor_entity_one.hass = hass
    assert binary_sensor_entity_one.available is True
    assert binary_sensor_entity_one.unique_id == "aa:bb:cc:dd:ee:ff-motion"
    assert binary_sensor_entity_one.device_info == {
        "identifiers": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "connections": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "manufacturer": "Test Manufacturer",
        "model": "Test Model",
        "name": "Test Device",
    }
    assert binary_sensor_entity_one.entity_key == PassiveBluetoothEntityKey(
        key="motion", device_id=None
    )
    cancel_coordinator()


@pytest.mark.usefixtures("mock_bleak_scanner_start", "mock_bluetooth_adapters")
async def test_exception_from_coordinator_update_method(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
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
            raise Exception("Test exception")  # noqa: TRY002
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

    processor = PassiveBluetoothDataProcessor(_async_generate_mock_data)

    unregister_processor = coordinator.async_register_processor(processor)
    cancel_coordinator = coordinator.async_start()

    processor.async_add_listener(MagicMock())

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    assert processor.available is True

    # We should go unavailable once we get an exception
    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)
    assert "Test exception" in caplog.text
    assert processor.available is False

    # We should go available again once we get data again
    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    assert processor.available is True
    unregister_processor()
    cancel_coordinator()


@pytest.mark.usefixtures("mock_bleak_scanner_start", "mock_bluetooth_adapters")
async def test_integration_multiple_entity_platforms_with_reload_and_restart(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test integration of PassiveBluetoothProcessorCoordinator with multiple platforms with reload."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    entry = MockConfigEntry(domain=DOMAIN, data={})

    @callback
    def _mock_update_method(
        service_info: BluetoothServiceInfo,
    ) -> dict[str, str]:
        return {"test": "data"}

    current_entry.set(entry)
    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        "aa:bb:cc:dd:ee:ff",
        BluetoothScanningMode.ACTIVE,
        _mock_update_method,
    )
    assert coordinator.available is False  # no data yet

    binary_sensor_processor = PassiveBluetoothDataProcessor(
        lambda service_info: BINARY_SENSOR_PASSIVE_BLUETOOTH_DATA_UPDATE,
        BINARY_SENSOR_DOMAIN,
    )
    sensor_processor = PassiveBluetoothDataProcessor(
        lambda service_info: SENSOR_PASSIVE_BLUETOOTH_DATA_UPDATE, SENSOR_DOMAIN
    )

    unregister_binary_sensor_processor = coordinator.async_register_processor(
        binary_sensor_processor, BinarySensorEntityDescription
    )
    unregister_sensor_processor = coordinator.async_register_processor(
        sensor_processor, SensorEntityDescription
    )
    cancel_coordinator = coordinator.async_start()

    binary_sensor_processor.async_add_listener(MagicMock())
    sensor_processor.async_add_listener(MagicMock())

    mock_add_sensor_entities = MagicMock()
    mock_add_binary_sensor_entities = MagicMock()

    sensor_processor.async_add_entities_listener(
        PassiveBluetoothProcessorEntity,
        mock_add_sensor_entities,
    )
    binary_sensor_processor.async_add_entities_listener(
        PassiveBluetoothProcessorEntity,
        mock_add_binary_sensor_entities,
    )

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    # First call with just the remote sensor entities results in them being added
    assert len(mock_add_binary_sensor_entities.mock_calls) == 1
    assert len(mock_add_sensor_entities.mock_calls) == 1

    binary_sensor_entities = [
        *mock_add_binary_sensor_entities.mock_calls[0][1][0],
    ]
    sensor_entities = [
        *mock_add_sensor_entities.mock_calls[0][1][0],
    ]

    sensor_entity_one: PassiveBluetoothProcessorEntity = sensor_entities[0]
    sensor_entity_one.hass = hass
    assert sensor_entity_one.available is True
    assert sensor_entity_one.unique_id == "aa:bb:cc:dd:ee:ff-pressure"
    assert sensor_entity_one.device_info == {
        "identifiers": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "connections": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "manufacturer": "Test Manufacturer",
        "model": "Test Model",
        "name": "Test Device",
    }
    assert sensor_entity_one.entity_key == PassiveBluetoothEntityKey(
        key="pressure", device_id=None
    )

    binary_sensor_entity_one: PassiveBluetoothProcessorEntity = binary_sensor_entities[
        0
    ]
    binary_sensor_entity_one.hass = hass
    assert binary_sensor_entity_one.available is True
    assert binary_sensor_entity_one.unique_id == "aa:bb:cc:dd:ee:ff-motion"
    assert binary_sensor_entity_one.device_info == {
        "identifiers": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "connections": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "manufacturer": "Test Manufacturer",
        "model": "Test Model",
        "name": "Test Device",
    }
    assert binary_sensor_entity_one.entity_key == PassiveBluetoothEntityKey(
        key="motion", device_id=None
    )
    cancel_coordinator()
    unregister_binary_sensor_processor()
    unregister_sensor_processor()

    mock_add_sensor_entities = MagicMock()
    mock_add_binary_sensor_entities = MagicMock()

    current_entry.set(entry)
    coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        "aa:bb:cc:dd:ee:ff",
        BluetoothScanningMode.ACTIVE,
        _mock_update_method,
    )
    binary_sensor_processor = PassiveBluetoothDataProcessor(
        lambda service_info: DEVICE_ONLY_PASSIVE_BLUETOOTH_DATA_UPDATE,
        BINARY_SENSOR_DOMAIN,
    )
    sensor_processor = PassiveBluetoothDataProcessor(
        lambda service_info: DEVICE_ONLY_PASSIVE_BLUETOOTH_DATA_UPDATE,
        SENSOR_DOMAIN,
    )

    sensor_processor.async_add_entities_listener(
        PassiveBluetoothProcessorEntity,
        mock_add_sensor_entities,
    )
    binary_sensor_processor.async_add_entities_listener(
        PassiveBluetoothProcessorEntity,
        mock_add_binary_sensor_entities,
    )

    unregister_binary_sensor_processor = coordinator.async_register_processor(
        binary_sensor_processor, BinarySensorEntityDescription
    )
    unregister_sensor_processor = coordinator.async_register_processor(
        sensor_processor, SensorEntityDescription
    )
    cancel_coordinator = coordinator.async_start()

    assert len(mock_add_binary_sensor_entities.mock_calls) == 1
    assert len(mock_add_sensor_entities.mock_calls) == 1

    binary_sensor_entities = [
        *mock_add_binary_sensor_entities.mock_calls[0][1][0],
    ]
    sensor_entities = [
        *mock_add_sensor_entities.mock_calls[0][1][0],
    ]

    sensor_entity_one: PassiveBluetoothProcessorEntity = sensor_entities[0]
    sensor_entity_one.hass = hass
    assert sensor_entity_one.available is True
    assert sensor_entity_one.unique_id == "aa:bb:cc:dd:ee:ff-pressure"
    assert sensor_entity_one.device_info == {
        "identifiers": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "connections": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "manufacturer": "Test Manufacturer",
        "model": "Test Model",
        "name": "Test Device",
    }
    assert sensor_entity_one.entity_key == PassiveBluetoothEntityKey(
        key="pressure", device_id=None
    )

    binary_sensor_entity_one: PassiveBluetoothProcessorEntity = binary_sensor_entities[
        0
    ]
    binary_sensor_entity_one.hass = hass
    assert binary_sensor_entity_one.available is True
    assert binary_sensor_entity_one.unique_id == "aa:bb:cc:dd:ee:ff-motion"
    assert binary_sensor_entity_one.device_info == {
        "identifiers": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "connections": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
        "manufacturer": "Test Manufacturer",
        "model": "Test Model",
        "name": "Test Device",
    }
    assert binary_sensor_entity_one.entity_key == PassiveBluetoothEntityKey(
        key="motion", device_id=None
    )

    await hass.async_stop()
    await hass.async_block_till_done()

    assert SENSOR_DOMAIN in hass_storage[STORAGE_KEY]["data"][entry.entry_id]
    assert BINARY_SENSOR_DOMAIN in hass_storage[STORAGE_KEY]["data"][entry.entry_id]

    # We don't normally cancel or unregister these at stop,
    # but since we are mocking a restart we need to cleanup
    cancel_coordinator()
    unregister_binary_sensor_processor()
    unregister_sensor_processor()

    async with async_test_home_assistant() as test_hass:
        await async_setup_component(test_hass, DOMAIN, {DOMAIN: {}})

        current_entry.set(entry)
        coordinator = PassiveBluetoothProcessorCoordinator(
            test_hass,
            _LOGGER,
            "aa:bb:cc:dd:ee:ff",
            BluetoothScanningMode.ACTIVE,
            _mock_update_method,
        )
        assert coordinator.available is False  # no data yet

        mock_add_sensor_entities = MagicMock()
        mock_add_binary_sensor_entities = MagicMock()

        binary_sensor_processor = PassiveBluetoothDataProcessor(
            lambda service_info: DEVICE_ONLY_PASSIVE_BLUETOOTH_DATA_UPDATE,
            BINARY_SENSOR_DOMAIN,
        )
        sensor_processor = PassiveBluetoothDataProcessor(
            lambda service_info: DEVICE_ONLY_PASSIVE_BLUETOOTH_DATA_UPDATE,
            SENSOR_DOMAIN,
        )

        sensor_processor.async_add_entities_listener(
            PassiveBluetoothProcessorEntity,
            mock_add_sensor_entities,
        )
        binary_sensor_processor.async_add_entities_listener(
            PassiveBluetoothProcessorEntity,
            mock_add_binary_sensor_entities,
        )

        unregister_binary_sensor_processor = coordinator.async_register_processor(
            binary_sensor_processor, BinarySensorEntityDescription
        )
        unregister_sensor_processor = coordinator.async_register_processor(
            sensor_processor, SensorEntityDescription
        )
        cancel_coordinator = coordinator.async_start()

        assert len(mock_add_binary_sensor_entities.mock_calls) == 1
        assert len(mock_add_sensor_entities.mock_calls) == 1

        binary_sensor_entities = [
            *mock_add_binary_sensor_entities.mock_calls[0][1][0],
        ]
        sensor_entities = [
            *mock_add_sensor_entities.mock_calls[0][1][0],
        ]

        sensor_entity_one: PassiveBluetoothProcessorEntity = sensor_entities[0]
        sensor_entity_one.hass = test_hass
        assert sensor_entity_one.available is False  # service data not injected
        assert sensor_entity_one.unique_id == "aa:bb:cc:dd:ee:ff-pressure"
        assert sensor_entity_one.device_info == {
            "identifiers": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
            "connections": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
            "manufacturer": "Test Manufacturer",
            "model": "Test Model",
            "name": "Test Device",
        }
        assert sensor_entity_one.entity_key == PassiveBluetoothEntityKey(
            key="pressure", device_id=None
        )

        binary_sensor_entity_one: PassiveBluetoothProcessorEntity = (
            binary_sensor_entities[0]
        )
        binary_sensor_entity_one.hass = test_hass
        assert binary_sensor_entity_one.available is False  # service data not injected
        assert binary_sensor_entity_one.unique_id == "aa:bb:cc:dd:ee:ff-motion"
        assert binary_sensor_entity_one.device_info == {
            "identifiers": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
            "connections": {("bluetooth", "aa:bb:cc:dd:ee:ff")},
            "manufacturer": "Test Manufacturer",
            "model": "Test Model",
            "name": "Test Device",
        }
        assert binary_sensor_entity_one.entity_key == PassiveBluetoothEntityKey(
            key="motion", device_id=None
        )
        cancel_coordinator()
        unregister_binary_sensor_processor()
        unregister_sensor_processor()
        await test_hass.async_stop()


NAMING_PASSIVE_BLUETOOTH_DATA_UPDATE = PassiveBluetoothDataUpdate(
    devices={
        None: DeviceInfo(
            name="Test Device", model="Test Model", manufacturer="Test Manufacturer"
        ),
    },
    entity_data={
        PassiveBluetoothEntityKey("temperature", None): 14.5,
    },
    entity_names={
        PassiveBluetoothEntityKey("temperature", None): None,
    },
    entity_descriptions={
        PassiveBluetoothEntityKey("temperature", None): SensorEntityDescription(
            key="temperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        ),
    },
)


@pytest.mark.usefixtures("mock_bleak_scanner_start", "mock_bluetooth_adapters")
async def test_naming(hass: HomeAssistant) -> None:
    """Test basic usage of the PassiveBluetoothProcessorCoordinator."""
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

    sensor_processor = PassiveBluetoothDataProcessor(
        lambda service_info: NAMING_PASSIVE_BLUETOOTH_DATA_UPDATE
    )

    coordinator.async_register_processor(sensor_processor)
    cancel_coordinator = coordinator.async_start()

    sensor_processor.async_add_listener(MagicMock())

    mock_add_sensor_entities = MagicMock()

    sensor_processor.async_add_entities_listener(
        PassiveBluetoothProcessorEntity,
        mock_add_sensor_entities,
    )

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    # First call with just the remote sensor entities results in them being added
    assert len(mock_add_sensor_entities.mock_calls) == 1

    sensor_entities = [
        *mock_add_sensor_entities.mock_calls[0][1][0],
    ]

    sensor_entity: PassiveBluetoothProcessorEntity = sensor_entities[0]
    sensor_entity.hass = hass
    sensor_entity.platform = MockEntityPlatform(hass)
    assert sensor_entity.available is True
    assert sensor_entity.name is UNDEFINED
    assert sensor_entity.device_class is SensorDeviceClass.TEMPERATURE
    assert sensor_entity.translation_key is None

    cancel_coordinator()
