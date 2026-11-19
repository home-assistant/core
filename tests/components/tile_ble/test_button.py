"""Tests for the Tile BLE button."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info
from syrupy.assertion import SnapshotAssertion
from tile_ble import TileBleAuthenticationError, TileBleConnectionError, TileBleError

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import AUTH_KEY, TILE_ADDRESS, TILE_SERVICE_INFO, setup_integration

ENTITY_ID = "button.tile_ring"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Only set up the button platform."""
    with patch("homeassistant.components.tile_ble.PLATFORMS", [Platform.BUTTON]):
        yield


async def _press(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the ring button."""
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_unavailable_out_of_range(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the ring button is unavailable while the Tile is not seen."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


async def test_ring(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tile_ble_device: MagicMock,
) -> None:
    """Test pressing the button rings the Tile with its key."""
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)
    await setup_integration(hass, mock_config_entry)

    await _press(hass)

    ble_device, auth_key = mock_tile_ble_device.call_args.args
    assert ble_device.address == TILE_ADDRESS
    assert auth_key == AUTH_KEY
    mock_tile_ble_device.return_value.async_ring.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        pytest.param(TileBleConnectionError, "cannot_connect", id="cannot_connect"),
        pytest.param(TileBleAuthenticationError, "ring_failed", id="wrong_key"),
        pytest.param(TileBleError, "ring_failed", id="ring_failed"),
    ],
)
async def test_ring_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tile_ble_device: MagicMock,
    exception: type[Exception],
    translation_key: str,
) -> None:
    """Test errors while ringing the Tile are raised as translated errors."""
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)
    await setup_integration(hass, mock_config_entry)
    mock_tile_ble_device.return_value.async_ring.side_effect = exception

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press(hass)
    assert exc_info.value.translation_key == translation_key


async def test_ring_not_connectable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tile_ble_device: MagicMock,
) -> None:
    """Test ringing fails when no adapter can connect to the Tile."""
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)
    await setup_integration(hass, mock_config_entry)

    with (
        patch(
            "homeassistant.components.tile_ble.button.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await _press(hass)
    assert exc_info.value.translation_key == "not_connectable"
    mock_tile_ble_device.assert_not_called()
