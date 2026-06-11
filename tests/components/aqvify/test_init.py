"""Test the Aqvify init."""

from unittest.mock import MagicMock

from pyaqvify import AqvifyAuthException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.aqvify.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_aqvify_client: MagicMock,
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
    ("error", "expected_state"),
    [
        (None, ConfigEntryState.LOADED),
        (AqvifyAuthException, ConfigEntryState.SETUP_ERROR),
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
    ],
    ids=["no_error", "auth_error", "timeout_error"],
)
async def test_setup_entry_with_error(
    hass: HomeAssistant,
    mock_aqvify_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    error: Exception | None,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup entry with error."""
    mock_aqvify_client.async_get_account_id.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


async def test_device_registry_integration(
    hass: HomeAssistant,
    mock_aqvify_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device registry integration creates correct devices."""
    await setup_integration(hass, mock_config_entry)

    # Get all devices created for this config entry
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    # Snapshot the devices to ensure they have the correct structure
    assert device_entries == snapshot


async def test_setup_entry_auth_error_triggers_reauth(
    hass: HomeAssistant,
    mock_aqvify_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup with auth error triggers reauth flow."""
    mock_config_entry.add_to_hass(hass)

    mock_aqvify_client.async_get_account_id.side_effect = AqvifyAuthException(
        "Authentication failed"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_device_remove_devices(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_aqvify_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test we can only remove a device that no longer exists."""
    assert await async_setup_component(hass, "config", {})

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    device_entry = device_registry.async_get_device(
        identifiers={
            (
                DOMAIN,
                "test_account_id_DeviceKey_1",
            )
        },
    )
    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id, mock_config_entry.entry_id)
    assert not response["success"]

    old_device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "STALE-DEVICE-UUID")},
    )
    response = await client.remove_device(
        old_device_entry.id, mock_config_entry.entry_id
    )

    assert response["success"]
