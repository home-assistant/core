"""Tests for the diagnostics data provided by the miele integration."""

from collections.abc import Generator
import http
from typing import Any
from unittest.mock import MagicMock, Mock

from aiohttp import ClientResponseError
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import paths

from homeassistant.components.miele.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry

from . import setup_integration

TEST_DEVICE = "Dummy_Appliance_1"


async def test_diagnostics_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_miele_client: Generator[MagicMock],
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""

    await setup_integration(hass, mock_config_entry)
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot(
        exclude=paths(
            "config_entry_data.token.expires_at",
            "miele_test.entry_id",
        )
    )


async def test_diagnostics_config_entry_without_aux_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry diagnostics when fillingLevels data is unavailable."""
    mock_miele_client.get_filling_levels.side_effect = ClientResponseError(
        Mock(), Mock(), status=http.HTTPStatus.SERVICE_UNAVAILABLE
    )
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["miele_data"]["devices"]
    assert result["miele_data"]["actions"]
    assert result["miele_data"]["filling_levels"] == {}


async def test_diagnostics_device(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: DeviceRegistry,
    mock_miele_client: Generator[MagicMock],
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for device."""

    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_DEVICE), mock_config_entry.entry_id
    )
    assert device_entry is not None

    result = await get_diagnostics_for_device(
        hass, hass_client, mock_config_entry, device_entry
    )
    assert result == snapshot(
        exclude=paths(
            "data.token.expires_at",
            "miele_test.entry_id",
        )
    )


async def test_diagnostics_device_without_aux_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: DeviceRegistry,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device diagnostics when fillingLevels data is unavailable."""
    mock_miele_client.get_filling_levels.side_effect = ClientResponseError(
        Mock(), Mock(), status=http.HTTPStatus.SERVICE_UNAVAILABLE
    )
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_DEVICE), mock_config_entry.entry_id
    )
    assert device_entry is not None

    result = await get_diagnostics_for_device(
        hass, hass_client, mock_config_entry, device_entry
    )

    assert result["miele_data"]["devices"]
    assert result["miele_data"]["actions"]
    assert result["miele_data"]["filling_levels"] == {}


async def test_diagnostics_device_filling_levels_omit_device(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: DeviceRegistry,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    filling_levels_fixture: list[dict[str, Any]],
) -> None:
    """Test device diagnostics when fillingLevels omits the requested device."""
    mock_miele_client.get_filling_levels.return_value = [
        item for item in filling_levels_fixture if item["deviceId"] != TEST_DEVICE
    ]
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_DEVICE), mock_config_entry.entry_id
    )
    assert device_entry is not None

    result = await get_diagnostics_for_device(
        hass, hass_client, mock_config_entry, device_entry
    )

    assert result["miele_data"]["devices"]
    assert result["miele_data"]["actions"]
    assert result["miele_data"]["filling_levels"] == {}
