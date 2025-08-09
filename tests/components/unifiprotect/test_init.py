"""Test the UniFi Protect setup flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from uiprotect import NvrError, ProtectApiClient
from uiprotect.api import DEVICE_UPDATE_INTERVAL
from uiprotect.data import NVR, Bootstrap, CloudAccount, Light
from uiprotect.exceptions import BadRequest, NotAuthorized

from homeassistant.components.unifiprotect.const import (
    AUTH_RETRIES,
    CONF_ALLOW_EA,
    DOMAIN,
)
from homeassistant.components.unifiprotect.data import (
    async_ufp_instance_for_config_entry_ids,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import _patch_discovery
from .utils import MockUFPFixture, init_entry, time_changed

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


@pytest.fixture
def mock_user_can_write_nvr(request: pytest.FixtureRequest, ufp: MockUFPFixture):
    """Fixture to mock can_write method on NVR objects with indirect parametrization."""
    can_write_result = getattr(request, "param", True)
    original_can_write = ufp.api.bootstrap.nvr.can_write
    mock_can_write = Mock(return_value=can_write_result)
    object.__setattr__(ufp.api.bootstrap.nvr, "can_write", mock_can_write)
    try:
        yield mock_can_write
    finally:
        object.__setattr__(ufp.api.bootstrap.nvr, "can_write", original_can_write)


async def test_setup(hass: HomeAssistant, ufp: MockUFPFixture) -> None:
    """Test working setup of unifiprotect entry."""

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert ufp.entry.state is ConfigEntryState.LOADED
    assert ufp.api.update.called
    assert ufp.entry.unique_id == ufp.api.bootstrap.nvr.mac


async def test_setup_multiple(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    bootstrap: Bootstrap,
) -> None:
    """Test working setup of unifiprotect entry."""

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert ufp.entry.state is ConfigEntryState.LOADED
    assert ufp.api.update.called
    assert ufp.entry.unique_id == ufp.api.bootstrap.nvr.mac

    nvr = bootstrap.nvr
    nvr._api = ufp.api
    nvr.mac = "A1E00C826983"
    ufp.api.get_nvr = AsyncMock(return_value=nvr)

    with patch(
        "homeassistant.components.unifiprotect.utils.ProtectApiClient"
    ) as mock_api:
        mock_config = MockConfigEntry(
            domain=DOMAIN,
            data={
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                CONF_API_KEY: "test-api-key",
                "id": "UnifiProtect",
                "port": 443,
                "verify_ssl": False,
            },
            version=2,
        )
        mock_config.add_to_hass(hass)

        mock_api.return_value = ufp.api

        await hass.config_entries.async_setup(mock_config.entry_id)
        await hass.async_block_till_done()

        assert mock_config.state is ConfigEntryState.LOADED
        assert ufp.api.update.called
        assert mock_config.unique_id == ufp.api.bootstrap.nvr.mac


async def test_unload(hass: HomeAssistant, ufp: MockUFPFixture, light: Light) -> None:
    """Test unloading of unifiprotect entry."""

    await init_entry(hass, ufp, [light])
    assert ufp.entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(ufp.entry.entry_id)
    assert ufp.entry.state is ConfigEntryState.NOT_LOADED
    assert ufp.api.async_disconnect_ws.called


async def test_setup_too_old(
    hass: HomeAssistant, ufp: MockUFPFixture, old_nvr: NVR
) -> None:
    """Test setup of unifiprotect entry with too old of version of UniFi Protect."""

    old_bootstrap = ufp.api.bootstrap.model_copy()
    old_bootstrap.nvr = old_nvr
    ufp.api.update.return_value = old_bootstrap
    ufp.api.bootstrap = old_bootstrap

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_cloud_account(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    cloud_account: CloudAccount,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test setup of unifiprotect entry with cloud account."""

    bootstrap = ufp.api.bootstrap
    user = bootstrap.users[bootstrap.auth_user_id]
    user.cloud_account = cloud_account
    bootstrap.users[bootstrap.auth_user_id] = user
    ufp.api.get_bootstrap.return_value = bootstrap
    ws_client = await hass_ws_client(hass)

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state is ConfigEntryState.LOADED

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "cloud_user":
            issue = i
    assert issue is not None


async def test_setup_failed_update(hass: HomeAssistant, ufp: MockUFPFixture) -> None:
    """Test setup of unifiprotect entry with failed update."""

    ufp.api.update = AsyncMock(side_effect=NvrError)

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state is ConfigEntryState.SETUP_RETRY
    assert ufp.api.update.called


async def test_setup_failed_update_reauth(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """Test setup of unifiprotect entry with update that gives unauthroized error."""

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state is ConfigEntryState.LOADED

    # reauth should not be triggered until there are 10 auth failures in a row
    # to verify it is not transient
    ufp.api.update = AsyncMock(side_effect=NotAuthorized)
    for _ in range(AUTH_RETRIES):
        await time_changed(hass, DEVICE_UPDATE_INTERVAL)
        assert len(hass.config_entries.flow._progress) == 0

    assert ufp.api.update.call_count == AUTH_RETRIES
    assert ufp.entry.state is ConfigEntryState.LOADED

    await time_changed(hass, DEVICE_UPDATE_INTERVAL)
    assert ufp.api.update.call_count == AUTH_RETRIES + 1
    assert len(hass.config_entries.flow._progress) == 1


async def test_setup_failed_error(hass: HomeAssistant, ufp: MockUFPFixture) -> None:
    """Test setup of unifiprotect entry with generic error."""

    ufp.api.update = AsyncMock(side_effect=NvrError)

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_failed_auth(hass: HomeAssistant, ufp: MockUFPFixture) -> None:
    """Test setup of unifiprotect entry with unauthorized error after multiple retries."""

    ufp.api.update = AsyncMock(side_effect=NotAuthorized)

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    assert ufp.entry.state is ConfigEntryState.SETUP_RETRY

    for _ in range(AUTH_RETRIES - 1):
        await hass.config_entries.async_reload(ufp.entry.entry_id)
        assert ufp.entry.state is ConfigEntryState.SETUP_RETRY

    await hass.config_entries.async_reload(ufp.entry.entry_id)
    assert ufp.entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_starts_discovery(
    hass: HomeAssistant, ufp_config_entry: ConfigEntry, ufp_client: ProtectApiClient
) -> None:
    """Test setting up will start discovery."""
    with (
        _patch_discovery(),
        patch(
            "homeassistant.components.unifiprotect.utils.ProtectApiClient"
        ) as mock_api,
    ):
        ufp_config_entry.add_to_hass(hass)
        mock_api.return_value = ufp_client
        ufp = MockUFPFixture(ufp_config_entry, ufp_client)

        await hass.config_entries.async_setup(ufp.entry.entry_id)
        await hass.async_block_till_done()
        assert ufp.entry.state is ConfigEntryState.LOADED
        await hass.async_block_till_done()
        assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1


async def test_device_remove_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    light: Light,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can only remove a device that no longer exists."""

    await init_entry(hass, ufp, [light])
    assert await async_setup_component(hass, "config", {})
    entity_id = "light.test_light"
    entry_id = ufp.entry.entry_id

    entity = entity_registry.async_get(entity_id)
    assert entity is not None

    live_device_entry = device_registry.async_get(entity.device_id)
    client = await hass_ws_client(hass)
    response = await client.remove_device(live_device_entry.id, entry_id)
    assert not response["success"]

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "e9:88:e7:b8:b4:40")},
    )
    response = await client.remove_device(dead_device_entry.id, entry_id)
    assert response["success"]


async def test_device_remove_devices_nvr(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    ufp: MockUFPFixture,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can only remove a NVR device that no longer exists."""
    assert await async_setup_component(hass, "config", {})

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    entry_id = ufp.entry.entry_id

    live_device_entry = list(device_registry.devices.values())[0]
    client = await hass_ws_client(hass)
    response = await client.remove_device(live_device_entry.id, entry_id)
    assert not response["success"]


@pytest.mark.parametrize(
    ("mock_entries", "expected_result"),
    [
        pytest.param(
            [
                MockConfigEntry(
                    domain=DOMAIN,
                    entry_id="1",
                    data={},
                ),
                MockConfigEntry(
                    domain="other_domain",
                    entry_id="2",
                    data={},
                ),
            ],
            "mock_api_instance_1",
            id="one_matching_domain",
        ),
        pytest.param(
            [
                MockConfigEntry(
                    domain="other_domain",
                    entry_id="1",
                    data={},
                ),
                MockConfigEntry(
                    domain="other_domain",
                    entry_id="2",
                    data={},
                ),
            ],
            None,
            id="no_matching_domain",
        ),
    ],
)
async def test_async_ufp_instance_for_config_entry_ids(
    hass: HomeAssistant,
    mock_entries: list[MockConfigEntry],
    expected_result: str | None,
) -> None:
    """Test async_ufp_instance_for_config_entry_ids with various entry configurations."""

    for index, entry in enumerate(mock_entries):
        entry.add_to_hass(hass)
        entry.runtime_data = Mock(api=f"mock_api_instance_{index + 1}")

    entry_ids = {entry.entry_id for entry in mock_entries}

    result = async_ufp_instance_for_config_entry_ids(hass, entry_ids)

    assert result == expected_result


@pytest.mark.parametrize("mock_user_can_write_nvr", [True], indirect=True)
async def test_setup_creates_api_key_when_missing(
    hass: HomeAssistant, ufp: MockUFPFixture, mock_user_can_write_nvr: Mock
) -> None:
    """Test that API key is created when missing and user has write permissions."""
    # Setup: API key is not set initially, user has write permissions
    ufp.api.is_api_key_set.return_value = False
    ufp.api.create_api_key = AsyncMock(return_value="new-api-key-123")

    # Mock set_api_key to update is_api_key_set return value when called
    def set_api_key_side_effect(key):
        ufp.api.is_api_key_set.return_value = True

    ufp.api.set_api_key.side_effect = set_api_key_side_effect

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    # Verify API key was created and set
    ufp.api.create_api_key.assert_called_once_with(name="Home Assistant (test home)")
    ufp.api.set_api_key.assert_called_once_with("new-api-key-123")

    # Verify config entry was updated with new API key
    assert ufp.entry.data[CONF_API_KEY] == "new-api-key-123"
    assert ufp.entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize("mock_user_can_write_nvr", [False], indirect=True)
async def test_setup_skips_api_key_creation_when_no_write_permission(
    hass: HomeAssistant, ufp: MockUFPFixture, mock_user_can_write_nvr: Mock
) -> None:
    """Test that API key creation is skipped when user has no write permissions."""
    # Setup: API key is not set, user has no write permissions
    ufp.api.is_api_key_set.return_value = False

    # Should fail with auth error since no API key and can't create one
    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert ufp.entry.state is ConfigEntryState.SETUP_ERROR

    # Verify API key creation was not attempted
    ufp.api.create_api_key.assert_not_called()
    ufp.api.set_api_key.assert_not_called()


@pytest.mark.parametrize("mock_user_can_write_nvr", [True], indirect=True)
async def test_setup_handles_api_key_creation_failure(
    hass: HomeAssistant, ufp: MockUFPFixture, mock_user_can_write_nvr: Mock
) -> None:
    """Test handling of API key creation failure."""
    # Setup: API key is not set, user has write permissions, but creation fails
    ufp.api.is_api_key_set.return_value = False
    ufp.api.create_api_key = AsyncMock(
        side_effect=NotAuthorized("Failed to create API key")
    )

    # Should fail with auth error due to API key creation failure
    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert ufp.entry.state is ConfigEntryState.SETUP_ERROR

    # Verify API key creation was attempted but set_api_key was not called
    ufp.api.create_api_key.assert_called_once_with(name="Home Assistant (test home)")
    ufp.api.set_api_key.assert_not_called()


@pytest.mark.parametrize("mock_user_can_write_nvr", [True], indirect=True)
async def test_setup_handles_api_key_creation_bad_request(
    hass: HomeAssistant, ufp: MockUFPFixture, mock_user_can_write_nvr: Mock
) -> None:
    """Test handling of API key creation BadRequest error."""
    # Setup: API key is not set, user has write permissions, but creation fails with BadRequest
    ufp.api.is_api_key_set.return_value = False
    ufp.api.create_api_key = AsyncMock(
        side_effect=BadRequest("Invalid API key creation request")
    )

    # Should fail with auth error due to API key creation failure
    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert ufp.entry.state is ConfigEntryState.SETUP_ERROR

    # Verify API key creation was attempted but set_api_key was not called
    ufp.api.create_api_key.assert_called_once_with(name="Home Assistant (test home)")
    ufp.api.set_api_key.assert_not_called()


async def test_setup_with_existing_api_key(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """Test setup when API key is already set."""
    # Setup: API key is already set
    ufp.api.is_api_key_set.return_value = True

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert ufp.entry.state is ConfigEntryState.LOADED

    # Verify API key creation was not attempted
    ufp.api.create_api_key.assert_not_called()
    ufp.api.set_api_key.assert_not_called()


@pytest.mark.parametrize("mock_user_can_write_nvr", [True], indirect=True)
async def test_setup_api_key_creation_returns_none(
    hass: HomeAssistant, ufp: MockUFPFixture, mock_user_can_write_nvr: Mock
) -> None:
    """Test handling when API key creation returns None."""
    # Setup: API key is not set, creation returns None (empty response)
    # set_api_key will be called with None but is_api_key_set will still be False
    ufp.api.is_api_key_set.return_value = False
    ufp.api.create_api_key = AsyncMock(return_value=None)

    # Should fail with auth error since API key creation returned None
    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert ufp.entry.state is ConfigEntryState.SETUP_ERROR

    # Verify API key creation was attempted and set_api_key was called with None
    ufp.api.create_api_key.assert_called_once_with(name="Home Assistant (test home)")
    ufp.api.set_api_key.assert_called_once_with(None)


async def test_migrate_entry_version_2(hass: HomeAssistant) -> None:
    """Test remove CONF_ALLOW_EA from options while migrating a 1 config entry to 2."""
    with (
        patch(
            "homeassistant.components.unifiprotect.async_setup_entry", return_value=True
        ),
        patch("homeassistant.components.unifiprotect.async_start_discovery"),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"test": "1", "test2": "2", CONF_ALLOW_EA: "True"},
            version=1,
            unique_id="123456",
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert entry.version == 2
        assert entry.options.get(CONF_ALLOW_EA) is None
        assert entry.unique_id == "123456"


async def test_setup_skips_api_key_creation_when_no_auth_user(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """Test that API key creation is skipped when auth_user is None."""
    # Setup: API key is not set, auth_user is None
    ufp.api.is_api_key_set.return_value = False

    # Mock the users dictionary to return None for any user ID
    with patch.dict(ufp.api.bootstrap.users, {}, clear=True):
        # Should fail with auth error since no API key and no auth user to create one
        await hass.config_entries.async_setup(ufp.entry.entry_id)
        await hass.async_block_till_done()

        assert ufp.entry.state is ConfigEntryState.SETUP_ERROR

        # Verify API key creation was not attempted
        ufp.api.create_api_key.assert_not_called()
        ufp.api.set_api_key.assert_not_called()


@pytest.mark.parametrize("mock_user_can_write_nvr", [True], indirect=True)
async def test_setup_fails_when_api_key_still_missing_after_creation(
    hass: HomeAssistant, ufp: MockUFPFixture, mock_user_can_write_nvr: Mock
) -> None:
    """Test that setup fails when API key is still missing after creation attempts."""
    # Setup: API key is not set and remains not set even after attempts
    ufp.api.is_api_key_set.return_value = False  # type: ignore[attr-defined]
    ufp.api.create_api_key = AsyncMock(return_value="new-api-key-123")  # type: ignore[method-assign]
    ufp.api.set_api_key = Mock()  # type: ignore[method-assign] # Mock this but API key still won't be "set"

    # Setup should fail since API key is still not set after creation
    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    # Verify entry is in setup error state (which will trigger reauth automatically)
    assert ufp.entry.state is ConfigEntryState.SETUP_ERROR

    # Verify API key creation was attempted
    ufp.api.create_api_key.assert_called_once_with(  # type: ignore[attr-defined]
        name="Home Assistant (test home)"
    )
    ufp.api.set_api_key.assert_called_once_with("new-api-key-123")  # type: ignore[attr-defined]
