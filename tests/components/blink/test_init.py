"""Test the Blink init."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError
from blinkpy.auth import LoginError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.blink.const import DOMAIN
from homeassistant.components.blink.coordinator import SCAN_INTERVAL
from homeassistant.components.blink.services import SERVICE_SAVE_VIDEO
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

CAMERA_NAME = "Camera 1"
FILENAME = "blah"
PIN = "1234"


@pytest.mark.parametrize(
    ("the_error", "available"),
    [(ClientError, False), (TimeoutError, False), (None, False)],
)
async def test_setup_not_ready(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    the_error,
    available,
) -> None:
    """Test setup failed because we can't connect to the Blink system."""

    mock_blink_api.start = AsyncMock(side_effect=the_error)
    mock_blink_api.available = available

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_not_ready_authkey_required(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup failed because 2FA is needed to connect to the Blink system."""

    mock_blink_api.start = AsyncMock(side_effect=LoginError)

    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unload doesn't un-register services."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.services.has_service(DOMAIN, SERVICE_SAVE_VIDEO)


async def test_scheduled_refresh_is_not_forced(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a scheduled poll does not force a cache refresh.

    BlinkPy propagates a forced refresh as ``force_cache=True`` to the sync
    modules, which re-downloads media that is already cached. See #182552.
    """
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_blink_api.refresh.reset_mock()
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_blink_api.refresh.assert_awaited_once_with()


async def test_migrate_V0(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration script version 0."""
    mock_config_entry.add_to_hass(hass)

    hass.config_entries.async_update_entry(mock_config_entry, version=0)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(("version"), [1, 2])
async def test_migrate(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    version,
) -> None:
    """Test migration scripts."""
    mock_config_entry.add_to_hass(hass)

    hass.config_entries.async_update_entry(
        mock_config_entry,
        version=version,
        data={**mock_config_entry.data, "login_response": "Blah"},
    )

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert entry.reason == (
        f"Cannot migrate configuration entry from version {version},"
        " re-authentication is required"
    )


async def test_migrate_v3_to_v5(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration from version 3 to 5.

    device_id is renamed to hardware_id (v3->v4), then the legacy
    "Home Assistant" value carried over from device_id is dropped (v4->v5)
    since Blink's OAuth endpoint rejects it.
    """
    mock_config_entry.add_to_hass(hass)

    # Set up v3 config entry with device_id set to the legacy literal
    data = {**mock_config_entry.data}
    data.pop("hardware_id", None)
    data["device_id"] = "Home Assistant"
    hass.config_entries.async_update_entry(
        mock_config_entry,
        version=3,
        data=data,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 5
    assert "device_id" not in entry.data
    assert "hardware_id" not in entry.data


async def test_migrate_v4_drops_legacy_hardware_id(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migrating a v4 entry whose hardware_id is the rejected legacy value."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        version=4,
        data={**mock_config_entry.data, "hardware_id": "Home Assistant"},
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 5
    assert "hardware_id" not in entry.data


async def test_migrate_v4_keeps_valid_hardware_id(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a v4 entry with an already-valid hardware_id is left untouched."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        version=4,
        data={**mock_config_entry.data, "hardware_id": "some-valid-uuid"},
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 5
    assert entry.data["hardware_id"] == "some-valid-uuid"


@pytest.mark.usefixtures("mock_blink_auth_api")
@pytest.mark.parametrize(
    ("serial", "removed"),
    [
        pytest.param("12345", False, id="camera_on_account"),
        pytest.param("54321", False, id="sync_module_on_account"),
        pytest.param("67890", True, id="camera_removed_from_account"),
    ],
)
async def test_remove_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    mock_blink_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    serial: str,
    removed: bool,
) -> None:
    """Test only devices no longer on the Blink account can be removed."""
    mock_blink_api.sync = {
        "Sync module": MagicMock(
            serial="54321", version="1.0", attributes={}, cameras={}, arm=True
        )
    }
    assert await async_setup_component(hass, "config", {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, serial)},
    )
    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id)

    assert response["success"] is removed
    assert (device_registry.async_get(device_entry.id) is None) is removed
