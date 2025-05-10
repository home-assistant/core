"""Tests for init module."""

from datetime import timedelta
import http
import time
from unittest.mock import MagicMock

from aiohttp import ClientConnectionError
from freezegun.api import FrozenDateTimeFactory
from pymiele import OAUTH2_TOKEN
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.miele.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
)
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)
    entry = mock_config_entry

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("expires_at", "status", "expected_state"),
    [
        (
            time.time() - 3600,
            http.HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            time.time() - 3600,
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=["unauthorized", "internal_server_error"],
)
async def test_expired_token_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test failure while refreshing token with a transient error."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        status=status,
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_expired_token_refresh_connection_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test failure while refreshing token with a ClientError."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        exc=ClientConnectionError(),
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_devices_multiple_created_count(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that multiple devices are created."""
    await setup_integration(hass, mock_config_entry)

    assert len(device_registry.devices) == 6


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "Dummy_Appliance_1")}
    )
    assert device_entry is not None
    assert device_entry == snapshot


async def test_device_remove_devices(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_miele_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test we can only remove a device that no longer exists."""
    assert await async_setup_component(hass, "config", {})

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        identifiers={
            (
                DOMAIN,
                "Dummy_Appliance_1",
            )
        },
    )
    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id, mock_config_entry.entry_id)
    assert not response["success"]

    old_device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "OLD-DEVICE-UUID")},
    )
    response = await client.remove_device(
        old_device_entry.id, mock_config_entry.entry_id
    )
    assert response["success"]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_all_platforms(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    load_device_file: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that all platforms can be set up."""

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.freezer_door").state == "off"
    assert hass.states.get("binary_sensor.hood_problem").state == "off"

    assert (
        hass.states.get("button.washing_machine_start").object_id
        == "washing_machine_start"
    )

    assert hass.states.get("climate.freezer").state == "cool"
    assert hass.states.get("light.hood_light").state == "on"

    assert hass.states.get("sensor.freezer_temperature").state == "-18.0"
    assert hass.states.get("sensor.washing_machine").state == "off"

    assert hass.states.get("switch.washing_machine_power").state == "off"

    # Add two devices and let the clock tick for 130 seconds
    freezer.tick(timedelta(seconds=130))
    mock_miele_client.get_devices.return_value = load_json_object_fixture(
        "5_devices.json", DOMAIN
    )

    prev_devices = len(device_registry.devices)

    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(device_registry.devices) == prev_devices + 2

    # Check a sample sensor for each new device
    assert hass.states.get("sensor.dishwasher").state == "in_use"
    assert hass.states.get("sensor.oven_temperature_2").state == "175.0"
