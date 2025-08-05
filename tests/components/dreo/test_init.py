"""Test dreo integration initialization."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pydreo.exceptions import DreoBusinessException, DreoException
import pytest

from homeassistant.components.dreo.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_setup_success(hass: HomeAssistant, mock_config_entry) -> None:
    """Test successful setup of the integration."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.dreo.DreoClient") as mock_client_class,
        patch(
            "homeassistant.components.dreo.config_flow.DreoClient"
        ) as mock_config_flow_client,
    ):
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-device-id",
                "model": "DR-HTF001S",
                "deviceName": "Test Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": True,
            "connected": True,
        }

        mock_config_flow_client.return_value.login = MagicMock()
        mock_config_flow_client.return_value.get_devices = mock_client.get_devices

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.LOADED
        assert mock_config_entry.runtime_data is not None

        device_registry = dr.async_get(hass)
        device = device_registry.async_get_device(
            identifiers={("dreo", "test-device-id")}
        )
        assert device is not None
        assert device.name == "Test Fan"
        assert device.model == "DR-HTF001S"

        assert hass.states.get("fan.test_fan") is not None


async def test_setup_connection_error(hass: HomeAssistant) -> None:
    """Test setup with connection error."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login.side_effect = DreoException("Connection failed")

        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_authentication_error(hass: HomeAssistant) -> None:
    """Test setup with authentication error."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.dreo.DreoClient") as mock_client_class,
        patch(
            "homeassistant.components.dreo.config_flow.DreoClient"
        ) as mock_config_flow_client,
    ):
        mock_client = mock_client_class.return_value
        mock_client.login.side_effect = DreoBusinessException("Invalid credentials")

        mock_config_flow_client.return_value.login.side_effect = DreoBusinessException(
            "Invalid credentials"
        )

        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state == ConfigEntryState.SETUP_ERROR


async def test_setup_with_multiple_devices(hass: HomeAssistant) -> None:
    """Test setup with multiple devices."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "device1",
                "model": "DR-HTF001S",
                "deviceName": "Fan 1",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            },
            {
                "deviceSn": "device2",
                "model": "UNKNOWN-MODEL",
                "deviceName": "Unknown",
                "deviceType": "heater",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            },
            {
                "deviceSn": "device3",
                "model": "DR-HTF001S",
                "deviceName": "Fan 3",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            },
        ]
        mock_client.get_status.return_value = {
            "power_switch": True,
            "connected": True,
        }

        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state == ConfigEntryState.LOADED

    assert hass.states.get("fan.fan_1") is not None
    assert hass.states.get("fan.unknown") is None
    assert hass.states.get("fan.fan_3") is not None

    device_registry = dr.async_get(hass)
    assert (
        device_registry.async_get_device(identifiers={("dreo", "device1")}) is not None
    )
    assert (
        device_registry.async_get_device(identifiers={("dreo", "device3")}) is not None
    )


async def test_unload_config_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test unloading the config entry."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.dreo.DreoClient") as mock_client_class,
        patch(
            "homeassistant.components.dreo.config_flow.DreoClient"
        ) as mock_config_flow_client,
    ):
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "test-device-unload",
                "model": "DR-HTF001S",
                "deviceName": "Unload Test Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]
        mock_client.get_status.return_value = {
            "power_switch": True,
            "connected": True,
        }

        mock_config_flow_client.return_value.login = MagicMock()
        mock_config_flow_client.return_value.get_devices = mock_client.get_devices

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state == ConfigEntryState.LOADED

        assert hass.states.get("fan.unload_test_fan") is not None

        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.NOT_LOADED


async def test_setup_with_no_devices(hass: HomeAssistant) -> None:
    """Test setup when no devices are returned."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = []

        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state == ConfigEntryState.LOADED

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, mock_entry.entry_id)
    assert len(entities) == 0


async def test_setup_with_invalid_device_data(hass: HomeAssistant) -> None:
    """Test setup with invalid device data."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {"model": "DR-HTF001S"},
            {
                "deviceSn": "valid-id",
                "model": "DR-HTF001S",
                "deviceName": "Valid Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            },
        ]
        mock_client.get_status.return_value = {
            "power_switch": True,
            "connected": True,
        }

        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state == ConfigEntryState.LOADED

    assert hass.states.get("fan.valid_fan") is not None

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, mock_entry.entry_id)
    assert len(entities) == 1


async def test_coordinator_setup_and_refresh(hass: HomeAssistant) -> None:
    """Test coordinator setup and data refresh."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "coordinator-test",
                "model": "DR-HTF001S",
                "deviceName": "Coordinator Test Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]

        mock_client.get_status.side_effect = [
            {"power_switch": False, "connected": True},
            {"power_switch": True, "connected": True, "speed": 3},
        ]

        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("fan.coordinator_test_fan")
    assert state is not None
    assert state.state == "off"

    coordinator = mock_entry.runtime_data.coordinators["coordinator-test"]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("fan.coordinator_test_fan")
    assert state is not None
    assert state.state == "on"


async def test_coordinator_api_none_response_handling(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test coordinator handling when API returns None."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "none-response-device",
                "model": "DR-HTF001S",
                "deviceName": "None Response Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]

        mock_client.get_status.side_effect = [
            {"power_switch": True, "connected": True, "speed": 3},
            None,
        ]

        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = mock_entry.runtime_data.coordinators["none-response-device"]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert "No status available for device" in caplog.text
    assert "none-response-device" in caplog.text


async def test_coordinator_api_exception_handling(hass: HomeAssistant) -> None:
    """Test coordinator handling of API exceptions."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "exception-device",
                "model": "DR-HTF001S",
                "deviceName": "Exception Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]

        mock_client.get_status.side_effect = [
            {"power_switch": True, "connected": True, "speed": 3},
            DreoException("API Error"),
        ]

        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = mock_entry.runtime_data.coordinators["exception-device"]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("fan.exception_fan")
    assert state is not None
    assert state.state == "unavailable"


async def test_coordinator_generic_exception_handling(hass: HomeAssistant) -> None:
    """Test coordinator handling of generic exceptions."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.dreo.DreoClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()
        mock_client.get_devices.return_value = [
            {
                "deviceSn": "generic-error-device",
                "model": "DR-HTF001S",
                "deviceName": "Generic Error Fan",
                "deviceType": "fan",
                "config": {
                    "preset_modes": ["Sleep", "Auto", "Natural", "Normal"],
                    "speed_range": [1, 6],
                },
            }
        ]

        mock_client.get_status.side_effect = [
            {"power_switch": True, "connected": True, "speed": 3},
            ValueError("Generic error"),
        ]

        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = mock_entry.runtime_data.coordinators["generic-error-device"]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("fan.generic_error_fan")
    assert state is not None
    assert state.state == "unavailable"
