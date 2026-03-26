"""Tests for the Aprilaire coordinator."""

from unittest.mock import MagicMock, patch

from pyaprilaire.const import Attribute

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import MOCK_MAC, setup_integration

from tests.common import MockConfigEntry


async def test_coordinator_listener_management(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test adding and removing listeners."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    callback_called = False

    def update_callback():
        nonlocal callback_called
        callback_called = True

    remove = coordinator.async_add_listener(update_callback)
    assert callable(remove)

    coordinator.async_update_listeners()
    assert callback_called

    # Remove the listener and verify it's not called again
    callback_called = False
    remove()
    coordinator.async_update_listeners()
    assert not callback_called


async def test_coordinator_set_updated_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test async_set_updated_data merges data and notifies listeners."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    listener_called = False

    def on_update():
        nonlocal listener_called
        listener_called = True

    coordinator.async_add_listener(on_update)

    coordinator.async_set_updated_data({Attribute.HEAT_SETPOINT: 22.0})

    assert listener_called
    assert coordinator.data[Attribute.HEAT_SETPOINT] == 22.0
    # Original data should still be present
    assert coordinator.data[Attribute.MAC_ADDRESS] == MOCK_MAC


async def test_coordinator_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test device info creation."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    device_info = coordinator.device_info

    assert device_info is not None
    assert device_info["name"] == "Test Thermostat"
    assert device_info["manufacturer"] == "Aprilaire"
    assert device_info["model"] == "8620W"
    assert device_info["hw_version"] == "Rev. B"
    assert device_info["sw_version"] == "4.05"


async def test_coordinator_device_info_none_when_no_mac(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test device info returns None when MAC is missing."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    result = coordinator.create_device_info({})
    assert result is None


async def test_coordinator_device_name_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test device name defaults to 'Aprilaire' when not set."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert coordinator.create_device_name({}) == "Aprilaire"
    assert coordinator.create_device_name(None) == "Aprilaire"


async def test_coordinator_device_name_from_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test device name comes from data when available."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert coordinator.device_name == "Test Thermostat"


async def test_coordinator_hw_version_numeric(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test hardware version returns numeric string for low revision values."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    # Hardware revision <= ord("A") should return numeric string
    assert coordinator.get_hw_version({Attribute.HARDWARE_REVISION: 5}) == "5"
    assert coordinator.get_hw_version({Attribute.HARDWARE_REVISION: ord("A")}) == "65"


async def test_coordinator_hw_version_letter(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test hardware version returns letter for high revision values."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert coordinator.get_hw_version({Attribute.HARDWARE_REVISION: ord("B")}) == "Rev. B"
    assert coordinator.get_hw_version({Attribute.HARDWARE_REVISION: ord("C")}) == "Rev. C"


async def test_coordinator_hw_version_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test hardware version returns 'Unknown' when not available."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert coordinator.get_hw_version({}) == "Unknown"


async def test_coordinator_device_info_firmware_major_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test device info with firmware major revision only."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    info = coordinator.create_device_info(
        {
            Attribute.MAC_ADDRESS: MOCK_MAC,
            Attribute.FIRMWARE_MAJOR_REVISION: 3,
        }
    )
    assert info is not None
    assert info["sw_version"] == "3"


async def test_coordinator_device_info_unknown_model(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test device info with unknown model number."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    info = coordinator.create_device_info(
        {
            Attribute.MAC_ADDRESS: MOCK_MAC,
            Attribute.MODEL_NUMBER: 999,
        }
    )
    assert info is not None
    assert info["model"] == "Unknown (999)"


async def test_coordinator_device_registry_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test device registry is updated when device info changes."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={("aprilaire", MOCK_MAC)}
    )
    assert device is not None
    assert device.name == "Test Thermostat"

    # Update device name through new data (must include MAC_ADDRESS for device_info)
    coordinator.async_set_updated_data(
        {Attribute.MAC_ADDRESS: MOCK_MAC, Attribute.NAME: "Updated Name"}
    )
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        identifiers={("aprilaire", MOCK_MAC)}
    )
    assert device is not None
    assert device.name == "Updated Name"


async def test_coordinator_start_stop_listen(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test start and stop listen delegates to client."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    mock_client.start_listen.assert_called()
    coordinator.stop_listen()
    mock_client.stop_listen.assert_called()
