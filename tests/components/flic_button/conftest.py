"""Flic Button test fixtures."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.flic_button.const import (
    CONF_BATTERY_LEVEL,
    CONF_DEVICE_TYPE,
    CONF_PAIRING_ID,
    CONF_PAIRING_KEY,
    CONF_SERIAL_NUMBER,
    CONF_SIG_BITS,
    DOMAIN,
    DeviceType,
)
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from . import (
    DUO_ADDRESS,
    DUO_SERIAL,
    FLIC2_ADDRESS,
    FLIC2_SERIAL,
    TEST_BATTERY_LEVEL,
    TEST_BUTTON_UUID,
    TEST_PAIRING_ID,
    TEST_PAIRING_KEY,
    TEST_SIG_BITS,
    TWIST_ADDRESS,
    TWIST_SERIAL,
    create_duo_service_info,
    create_flic2_service_info,
    create_twist_service_info,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock Flic Button config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic 2 ({FLIC2_SERIAL})",
        unique_id=FLIC2_ADDRESS,
        data={
            CONF_ADDRESS: FLIC2_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: FLIC2_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.FLIC2.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )


@pytest.fixture
def mock_flic_client() -> Generator[MagicMock]:
    """Mock FlicClient for testing."""
    with patch(
        "homeassistant.components.flic_button.FlicClient", autospec=True
    ) as mock_client_class:
        mock_client = mock_client_class.return_value

        # Basic properties
        mock_client.address = FLIC2_ADDRESS
        mock_client.is_connected = True
        mock_client.is_duo = False
        mock_client.is_twist = False
        mock_client.ble_device = create_flic2_service_info().device

        # Mock capabilities
        mock_capabilities = MagicMock()
        mock_capabilities.button_count = 1
        mock_capabilities.has_rotation = False
        mock_capabilities.has_selector = False
        mock_capabilities.has_frame_header = True
        mock_client.capabilities = mock_capabilities

        # Mock handler
        mock_handler = MagicMock()
        mock_handler.capabilities = mock_capabilities
        mock_client.handler = mock_handler

        # Async methods
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client.full_verify_pairing = AsyncMock(
            return_value=(
                TEST_PAIRING_ID,
                TEST_PAIRING_KEY,
                FLIC2_SERIAL,
                TEST_BATTERY_LEVEL,
                TEST_SIG_BITS,
                None,
                10,
            )
        )
        mock_client.quick_verify = AsyncMock()
        mock_client.init_button_events = AsyncMock()
        mock_client.get_firmware_version = AsyncMock(return_value=10)
        mock_client.get_battery_level = AsyncMock(return_value=TEST_BATTERY_LEVEL)
        mock_client.get_battery_voltage = AsyncMock(
            return_value=TEST_BATTERY_LEVEL * 3.6 / 1024.0
        )
        mock_client.get_name = AsyncMock(return_value=("", 0))
        mock_client.set_name = AsyncMock(return_value=("", 0))
        mock_client.device_type = DeviceType.FLIC2

        # Event callbacks
        mock_client.on_button_event = None
        mock_client.on_rotate_event = None
        mock_client.on_selector_change = None
        mock_client.on_disconnect = None

        yield mock_client


@pytest.fixture
def mock_coordinator(mock_flic_client: MagicMock) -> Generator[MagicMock]:
    """Mock FlicCoordinator for testing."""
    with patch(
        "homeassistant.components.flic_button.FlicCoordinator", autospec=True
    ) as mock_coord_class:
        mock_coordinator = mock_coord_class.return_value

        # Properties
        mock_coordinator.client = mock_flic_client
        mock_coordinator.connected = True
        mock_coordinator.serial_number = FLIC2_SERIAL
        mock_coordinator.is_duo = False
        mock_coordinator.is_twist = False
        mock_coordinator.model_name = "Flic 2"
        mock_coordinator.device_type = DeviceType.FLIC2
        mock_coordinator.device_id = None
        mock_coordinator.capabilities = mock_flic_client.capabilities
        mock_coordinator.handler = mock_flic_client.handler
        mock_coordinator.last_update_success = True

        # Data - battery voltage from pairing
        battery_voltage = TEST_BATTERY_LEVEL * 3.6 / 1024.0
        mock_coordinator.data = {"battery_voltage": battery_voltage}

        # Firmware version
        mock_coordinator.firmware_version = 10

        # Async methods
        mock_coordinator.async_connect = AsyncMock()
        mock_coordinator.async_disconnect = AsyncMock()
        mock_coordinator.async_reconnect_if_needed = AsyncMock()
        mock_coordinator.async_request_refresh = AsyncMock()
        mock_coordinator.async_add_listener = MagicMock(return_value=lambda: None)
        mock_coordinator.async_set_updated_data = MagicMock()

        yield mock_coordinator


@pytest.fixture
def mock_ble_device_from_address() -> Generator[MagicMock]:
    """Mock async_ble_device_from_address."""
    service_info = create_flic2_service_info()
    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=service_info.device,
    ) as mock:
        yield mock


@pytest.fixture
def platforms() -> list[Platform]:
    """Return list of platforms to test."""
    return [Platform.EVENT]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
    mock_ble_device_from_address: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Flic Button integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.flic_button.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_twist_config_entry() -> MockConfigEntry:
    """Return a mock Flic Twist config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic Twist ({TWIST_SERIAL})",
        unique_id=TWIST_ADDRESS,
        data={
            CONF_ADDRESS: TWIST_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: TWIST_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.TWIST.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )


@pytest.fixture
def mock_twist_flic_client() -> Generator[MagicMock]:
    """Mock FlicClient for Twist device testing."""
    with patch(
        "homeassistant.components.flic_button.FlicClient", autospec=True
    ) as mock_client_class:
        mock_client = mock_client_class.return_value

        # Basic properties
        mock_client.address = TWIST_ADDRESS
        mock_client.is_connected = True
        mock_client.is_duo = False
        mock_client.is_twist = True
        mock_client.ble_device = create_twist_service_info().device
        mock_client.device_type = DeviceType.TWIST

        # Mock capabilities
        mock_capabilities = MagicMock()
        mock_capabilities.button_count = 1
        mock_capabilities.has_rotation = True
        mock_capabilities.has_selector = True
        mock_capabilities.has_frame_header = False
        mock_client.capabilities = mock_capabilities

        # Mock handler
        mock_handler = MagicMock()
        mock_handler.capabilities = mock_capabilities
        mock_client.handler = mock_handler

        # Async methods
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client.full_verify_pairing = AsyncMock(
            return_value=(
                TEST_PAIRING_ID,
                TEST_PAIRING_KEY,
                TWIST_SERIAL,
                TEST_BATTERY_LEVEL,
                TEST_SIG_BITS,
                TEST_BUTTON_UUID,
                10,
            )
        )
        mock_client.quick_verify = AsyncMock()
        mock_client.init_button_events = AsyncMock()
        mock_client.get_firmware_version = AsyncMock(return_value=10)
        mock_client.get_battery_level = AsyncMock(return_value=2800)
        mock_client.get_battery_voltage = AsyncMock(return_value=2.8)
        mock_client.get_name = AsyncMock(return_value=("", 0))
        mock_client.set_name = AsyncMock(return_value=("", 0))
        # Event callbacks
        mock_client.on_button_event = None
        mock_client.on_rotate_event = None
        mock_client.on_selector_change = None
        mock_client.on_disconnect = None

        yield mock_client


@pytest.fixture
def mock_twist_coordinator(mock_twist_flic_client: MagicMock) -> Generator[MagicMock]:
    """Mock FlicCoordinator for Twist testing."""
    with patch(
        "homeassistant.components.flic_button.FlicCoordinator", autospec=True
    ) as mock_coord_class:
        mock_coordinator = mock_coord_class.return_value

        # Properties
        mock_coordinator.client = mock_twist_flic_client
        mock_coordinator.connected = True
        mock_coordinator.serial_number = TWIST_SERIAL
        mock_coordinator.is_duo = False
        mock_coordinator.is_twist = True
        mock_coordinator.model_name = "Flic Twist"
        mock_coordinator.device_type = DeviceType.TWIST
        mock_coordinator.device_id = None
        mock_coordinator.capabilities = mock_twist_flic_client.capabilities
        mock_coordinator.handler = mock_twist_flic_client.handler
        mock_coordinator.last_update_success = True

        # Data - battery voltage for Twist (millivolts / 1000)
        mock_coordinator.data = {"battery_voltage": 2.8}

        # Firmware version
        mock_coordinator.firmware_version = 10

        # Async methods
        mock_coordinator.async_connect = AsyncMock()
        mock_coordinator.async_disconnect = AsyncMock()
        mock_coordinator.async_reconnect_if_needed = AsyncMock()
        mock_coordinator.async_request_refresh = AsyncMock()
        mock_coordinator.async_add_listener = MagicMock(return_value=lambda: None)
        mock_coordinator.async_set_updated_data = MagicMock()

        yield mock_coordinator


@pytest.fixture
def mock_twist_ble_device_from_address() -> Generator[MagicMock]:
    """Mock async_ble_device_from_address for Twist."""
    service_info = create_twist_service_info()
    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=service_info.device,
    ) as mock:
        yield mock


@pytest.fixture
async def init_twist_integration(
    hass: HomeAssistant,
    mock_twist_config_entry: MockConfigEntry,
    mock_twist_coordinator: MagicMock,
    mock_twist_ble_device_from_address: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Flic Button integration with Twist device for testing."""
    mock_twist_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.flic_button.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_twist_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_twist_config_entry


@pytest.fixture
def mock_duo_config_entry() -> MockConfigEntry:
    """Return a mock Flic Duo config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic Duo ({DUO_SERIAL})",
        unique_id=DUO_ADDRESS,
        data={
            CONF_ADDRESS: DUO_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: DUO_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.DUO.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )


@pytest.fixture
def mock_duo_flic_client() -> Generator[MagicMock]:
    """Mock FlicClient for Duo device testing."""
    with patch(
        "homeassistant.components.flic_button.FlicClient", autospec=True
    ) as mock_client_class:
        mock_client = mock_client_class.return_value

        # Basic properties
        mock_client.address = DUO_ADDRESS
        mock_client.is_connected = True
        mock_client.is_duo = True
        mock_client.is_twist = False
        mock_client.ble_device = create_duo_service_info().device
        mock_client.device_type = DeviceType.DUO

        # Mock capabilities
        mock_capabilities = MagicMock()
        mock_capabilities.button_count = 2
        mock_capabilities.has_rotation = True
        mock_capabilities.has_selector = False
        mock_capabilities.has_gestures = True
        mock_capabilities.has_frame_header = True
        mock_client.capabilities = mock_capabilities

        # Mock handler
        mock_handler = MagicMock()
        mock_handler.capabilities = mock_capabilities
        mock_client.handler = mock_handler

        # Async methods
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client.full_verify_pairing = AsyncMock(
            return_value=(
                TEST_PAIRING_ID,
                TEST_PAIRING_KEY,
                DUO_SERIAL,
                TEST_BATTERY_LEVEL,
                TEST_SIG_BITS,
                TEST_BUTTON_UUID,
                10,
            )
        )
        mock_client.quick_verify = AsyncMock()
        mock_client.init_button_events = AsyncMock()
        mock_client.get_firmware_version = AsyncMock(return_value=10)
        mock_client.get_battery_level = AsyncMock(return_value=TEST_BATTERY_LEVEL)
        mock_client.get_battery_voltage = AsyncMock(
            return_value=TEST_BATTERY_LEVEL * 3.6 / 1024.0
        )
        mock_client.get_name = AsyncMock(return_value=("", 0))
        mock_client.set_name = AsyncMock(return_value=("", 0))
        # Event callbacks
        mock_client.on_button_event = None
        mock_client.on_rotate_event = None
        mock_client.on_selector_change = None
        mock_client.on_disconnect = None

        yield mock_client


@pytest.fixture
def mock_duo_coordinator(mock_duo_flic_client: MagicMock) -> Generator[MagicMock]:
    """Mock FlicCoordinator for Duo testing."""
    with patch(
        "homeassistant.components.flic_button.FlicCoordinator", autospec=True
    ) as mock_coord_class:
        mock_coordinator = mock_coord_class.return_value

        # Properties
        mock_coordinator.client = mock_duo_flic_client
        mock_coordinator.connected = True
        mock_coordinator.serial_number = DUO_SERIAL
        mock_coordinator.is_duo = True
        mock_coordinator.is_twist = False
        mock_coordinator.model_name = "Flic Duo"
        mock_coordinator.device_type = DeviceType.DUO
        mock_coordinator.device_id = None
        mock_coordinator.capabilities = mock_duo_flic_client.capabilities
        mock_coordinator.handler = mock_duo_flic_client.handler
        mock_coordinator.last_update_success = True

        # Data - battery voltage from pairing
        battery_voltage = TEST_BATTERY_LEVEL * 3.6 / 1024.0
        mock_coordinator.data = {"battery_voltage": battery_voltage}

        # Firmware version
        mock_coordinator.firmware_version = 10

        # Async methods
        mock_coordinator.async_connect = AsyncMock()
        mock_coordinator.async_disconnect = AsyncMock()
        mock_coordinator.async_reconnect_if_needed = AsyncMock()
        mock_coordinator.async_request_refresh = AsyncMock()
        mock_coordinator.async_add_listener = MagicMock(return_value=lambda: None)
        mock_coordinator.async_set_updated_data = MagicMock()

        yield mock_coordinator


@pytest.fixture
def mock_duo_ble_device_from_address() -> Generator[MagicMock]:
    """Mock async_ble_device_from_address for Duo."""
    service_info = create_duo_service_info()
    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=service_info.device,
    ) as mock:
        yield mock


@pytest.fixture
async def init_duo_integration(
    hass: HomeAssistant,
    mock_duo_config_entry: MockConfigEntry,
    mock_duo_coordinator: MagicMock,
    mock_duo_ble_device_from_address: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Flic Button integration with Duo device for testing."""
    mock_duo_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.flic_button.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_duo_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_duo_config_entry
