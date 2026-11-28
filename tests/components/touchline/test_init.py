"""Tests for the Touchline integration setup."""

from dataclasses import replace
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator
from pytouchline_extended import TouchlineConnectionError, TouchlineResponseError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.touchline.const import DOMAIN
from homeassistant.components.touchline.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import CONTROLLER_STATUS, ROOM_STATUS, TEST_UNIQUE_ID, make_state


@pytest.mark.usefixtures("init_integration")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading and unloading the config entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        pytest.param(
            TouchlineConnectionError,
            "The Touchline controller at 1.2.3.4 cannot be reached",
            id="unreachable",
        ),
        pytest.param(
            TouchlineResponseError,
            "An error occurred while communicating with the Touchline controller"
            " at 1.2.3.4",
            id="invalid-response",
        ),
    ],
)
async def test_setup_retry_on_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchline_controller: MagicMock,
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test setup is retried with a translated reason when the controller fails."""
    mock_touchline_controller.fetch_async.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    # Home Assistant drops the final period of the message.
    assert mock_config_entry.reason == reason


@pytest.mark.parametrize(
    "field",
    [
        pytest.param("controller_id", id="controller-id"),
        pytest.param("device_id", id="device-id"),
    ],
)
async def test_setup_retry_on_missing_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchline_controller: MagicMock,
    field: str,
) -> None:
    """Test setup is retried when the controller returns no ID for a device."""
    mock_touchline_controller.fetch_async.return_value = make_state(
        replace(ROOM_STATUS, **{field: None})
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        mock_config_entry.reason
        == "The Touchline controller at 1.2.3.4 returned no ID for thermostat 0"
    )


@pytest.mark.usefixtures("init_integration")
async def test_devices(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the controller is a device, with its thermostats linked to it."""
    controller = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_UNIQUE_ID), mock_config_entry.entry_id
    )
    assert controller == snapshot

    assert controller is not None
    thermostat = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1_0"), mock_config_entry.entry_id
    )
    assert thermostat is not None
    assert thermostat.via_device_id == controller.id
    assert thermostat.model == "Thermostat"


async def test_controller_device_without_mac(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_touchline_controller: MagicMock,
) -> None:
    """Test the controller device has no connections when it reports no MAC."""
    mock_touchline_controller.fetch_async.return_value = make_state(
        ROOM_STATUS, controller=replace(CONTROLLER_STATUS, mac_address=None)
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    controller = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_UNIQUE_ID), mock_config_entry.entry_id
    )
    assert controller is not None
    assert controller.connections == set()


async def test_remove_stale_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    init_integration: MockConfigEntry,
    mock_touchline_controller: MagicMock,
) -> None:
    """Test a thermostat can only be removed once the controller stops reporting it."""
    assert await async_setup_component(hass, "config", {})
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1_0"), init_integration.entry_id
    )
    assert device is not None
    client = await hass_ws_client(hass)

    response = await client.remove_device(device.id)
    assert not response["success"]
    assert response["error"]["message"] == (
        "Failed to remove device entry, rejected by integration"
    )

    mock_touchline_controller.fetch_async.return_value = make_state()
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    response = await client.remove_device(device.id)
    assert response["success"]

    # The controller itself can never be removed.
    controller = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_UNIQUE_ID), init_integration.entry_id
    )
    assert controller is not None
    response = await client.remove_device(controller.id)
    assert not response["success"]
    assert response["error"]["message"] == (
        "Failed to remove device entry, rejected by integration"
    )
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "1_0"), init_integration.entry_id
        )
        is None
    )


async def test_remove_device_entry_not_loaded(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test a thermostat cannot be removed while the integration is not loaded."""
    assert await async_setup_component(hass, "config", {})
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1_0"), init_integration.entry_id
    )
    assert device is not None
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)

    response = await client.remove_device(device.id)

    assert not response["success"]
    assert response["error"]["message"] == (
        "Failed to remove device entry, rejected by integration"
    )
