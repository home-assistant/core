"""Test the UniFi Protect setup flow."""

from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from uiprotect import NvrError, ProtectApiClient
from uiprotect.api import DEVICE_UPDATE_INTERVAL
from uiprotect.data import NVR, Bootstrap, CloudAccount, Light, Version
from uiprotect.data.public_devices import PublicCamera
from uiprotect.exceptions import BadRequest, ClientError, NotAuthorized
from uiprotect.websocket import WebsocketState

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.unifiprotect import (
    SCAN_INTERVAL,
    async_remove_config_entry_device,
)
from homeassistant.components.unifiprotect.const import (
    AUTH_RETRIES,
    CONF_ALLOW_EA,
    DOMAIN,
    PLATFORMS,
    PUBLIC_ONLY_PLATFORMS,
)
from homeassistant.components.unifiprotect.data import (
    ProtectData,
    async_ufp_instance_for_config_entry_ids,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_API_KEY, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import _patch_discovery
from .conftest import PUBLIC_ONLY_ALARM_ENTITY_ID, UNIFI_MAC
from .utils import MockUFPFixture, init_entry, make_public_light, time_changed

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


def _reauth_flow_started(hass: HomeAssistant) -> bool:
    """Return whether a reauth flow is in progress."""
    return any(
        flow["context"]["source"] == SOURCE_REAUTH
        for flow in hass.config_entries.flow.async_progress()
    )


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


async def test_setup_creates_nvr_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    ufp: MockUFPFixture,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that setup creates the NVR device before loading platforms.

    This ensures that via_device references from camera/sensor entities
    to the NVR device work correctly.
    """
    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert ufp.entry.state is ConfigEntryState.LOADED

    # Verify NVR device was created
    nvr = ufp.api.bootstrap.nvr
    nvr_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, nvr.mac), ufp.entry.entry_id
    )
    assert nvr_device == snapshot


async def test_device_links_to_nvr_via_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    ufp: MockUFPFixture,
    light: Light,
) -> None:
    """Test that a standard Protect device's via_device_id points at the NVR device."""
    await init_entry(hass, ufp, [light])

    nvr = ufp.api.bootstrap.nvr
    nvr_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, nvr.mac), ufp.entry.entry_id
    )
    assert nvr_device is not None

    light_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, light.mac), ufp.entry.entry_id
    )
    assert light_device is not None
    assert light_device.via_device_id == nvr_device.id


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


async def test_remove_entry(hass: HomeAssistant, ufp: MockUFPFixture) -> None:
    """Test removal of unifiprotect entry clears session."""

    await init_entry(hass, ufp, [])
    assert ufp.entry.state is ConfigEntryState.LOADED

    # Mock clear_session method
    ufp.api.clear_session = AsyncMock()

    await hass.config_entries.async_remove(ufp.entry.entry_id)
    await hass.async_block_till_done()

    # Verify clear_session was called
    assert ufp.api.clear_session.called


async def test_remove_entry_not_loaded(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """Test removal of unloaded unifiprotect entry still clears session."""

    # Add entry but don't load it
    ufp.entry.add_to_hass(hass)

    # Mock clear_session method
    ufp.api.clear_session = AsyncMock()

    with patch(
        "homeassistant.components.unifiprotect.async_create_session_client",
        return_value=ufp.api,
    ):
        await hass.config_entries.async_remove(ufp.entry.entry_id)
        await hass.async_block_till_done()

    # Verify clear_session was called even though entry wasn't loaded
    assert ufp.api.clear_session.called


async def test_remove_entry_clear_session_fails(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """Test removal succeeds even when clear_session fails."""
    await init_entry(hass, ufp, [])
    assert ufp.entry.state is ConfigEntryState.LOADED

    # Mock clear_session to raise an exception
    ufp.api.clear_session = AsyncMock(side_effect=PermissionError("Permission denied"))

    # Should not raise - removal should succeed
    await hass.config_entries.async_remove(ufp.entry.entry_id)
    await hass.async_block_till_done()

    # Verify clear_session was attempted
    assert ufp.api.clear_session.called


async def test_remove_entry_not_loaded_clear_session_fails(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """Test removal succeeds when not loaded and clear_session fails."""
    # Don't initialize the integration - entry is not loaded
    ufp.entry.add_to_hass(hass)
    assert ufp.entry.state is not ConfigEntryState.LOADED

    # Mock clear_session to raise an exception for the temporary client
    with patch(
        "homeassistant.components.unifiprotect.async_create_session_client"
    ) as mock_create:
        mock_api = Mock(spec=ProtectApiClient)
        mock_api.clear_session = AsyncMock(side_effect=OSError("Read-only file system"))
        mock_create.return_value = mock_api

        # Should not raise - removal should succeed
        await hass.config_entries.async_remove(ufp.entry.entry_id)
        await hass.async_block_till_done()

        # Verify clear_session was attempted
        assert mock_api.clear_session.called


@pytest.mark.parametrize("version", ["1.19.0", "7.0.107"])
async def test_setup_too_old(
    hass: HomeAssistant, ufp: MockUFPFixture, old_nvr: NVR, version: str
) -> None:
    """Test setup of unifiprotect entry with too old of version of UniFi Protect.

    7.0.107 is the last release before the public API gained the camera and
    sensor fields the integration reads, so it has to be rejected too.
    """

    old_nvr.version = Version(version)
    old_bootstrap = ufp.api.bootstrap.model_copy()
    old_bootstrap.nvr = old_nvr
    ufp.api.update.return_value = old_bootstrap
    ufp.api.bootstrap = old_bootstrap

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()
    assert ufp.entry.state is ConfigEntryState.SETUP_ERROR
    assert ufp.entry.error_reason_translation_key == "protect_version"


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
    """Test setup of unifiprotect entry with unauthorized error after retries."""

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
    """Test setting up will start discovery via unifi_discovery dependency."""
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
        await hass.async_block_till_done(wait_background_tasks=True)
        assert ufp.entry.state is ConfigEntryState.LOADED
        # Discovery is now handled by unifi_discovery dependency
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
    response = await client.remove_device(live_device_entry.id)
    assert not response["success"]

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "e9:88:e7:b8:b4:40")},
    )
    response = await client.remove_device(dead_device_entry.id)
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

    live_device_entry = list(device_registry.devices)[0]
    client = await hass_ws_client(hass)
    response = await client.remove_device(live_device_entry.id)
    assert not response["success"]


async def test_remove_config_entry_device_rejects_child_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    ufp: MockUFPFixture,
    light: Light,
) -> None:
    """Test removing an unexpected child device is rejected."""
    await init_entry(hass, ufp, [light])
    assert await async_setup_component(hass, "config", {})
    parent_device = device_registry.async_get_or_create(
        config_entry_id=ufp.entry.entry_id,
        identifiers={(DOMAIN, "test_parent_device")},
    )
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=ufp.entry.entry_id,
        identifiers={(DOMAIN, "test_child_device")},
        parent_device_id=parent_device.id,
    )

    client = await hass_ws_client(hass)
    response = await client.remove_device(child_device.id)
    assert not response["success"]
    assert (
        response["error"]["message"]
        == "Failed to remove device entry, rejected by integration"
    )
    assert device_registry.async_get(child_device.id)


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
    """Test async_ufp_instance_for_config_entry_ids with various configs."""

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
    # Setup: API key is not set, user has write permissions,
    # but creation fails with BadRequest
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


async def test_hybrid_auth_failed_triggers_reauth(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """A revoked API key on the public websocket starts reauth in hybrid mode too."""

    await init_entry(hass, ufp, [])
    assert ufp.entry.state is ConfigEntryState.LOADED

    ufp.devices_ws_state_subscription(WebsocketState.AUTH_FAILED)
    await hass.async_block_till_done()

    assert _reauth_flow_started(hass)


async def test_public_only_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """A public-only entry loads, creates the NVR device, and the alarm panel."""
    await setup_public_only()

    assert ufp_public_only.entry.state is ConfigEntryState.LOADED
    # The private bootstrap is never fetched in this mode.
    ufp_public_only.api.get_bootstrap.assert_not_called()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, UNIFI_MAC), ufp_public_only.entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "7.2.105"
    # Name always, model on firmware newer than 7.1.
    assert device.name == "Test NVR"
    assert device.model == "UNVR4"
    # Degraded identity: no market name / console url.
    assert device.configuration_url is None

    state = hass.states.get(PUBLIC_ONLY_ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == AlarmControlPanelState.DISARMED


async def test_public_only_forwards_only_public_platforms(
    hass: HomeAssistant,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Only ``PUBLIC_ONLY_PLATFORMS`` are forwarded in public-only mode.

    Every other platform enumerates from the private bootstrap, which an
    API-key-only entry never has.
    """
    await setup_public_only()

    private_platforms = [p for p in PLATFORMS if p not in PUBLIC_ONLY_PLATFORMS]
    for platform in private_platforms:
        assert not hass.states.async_entity_ids(platform.value)
    # entity_platform turns a failing platform into a log line, so a forwarded
    # platform can break without failing any assertion above.
    assert "Error while setting up" not in caplog.text


async def test_public_only_auth_failed_triggers_reauth(
    hass: HomeAssistant,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """A revoked API key on the public websocket starts a reauth flow.

    The library always emits DISCONNECTED before AUTH_FAILED (uiprotect
    15.12.2+), so the stale public data is marked unavailable by the regular
    disconnect path before reauth is triggered.
    """
    await setup_public_only()

    ufp_public_only.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    ufp_public_only.devices_ws_state_subscription(WebsocketState.AUTH_FAILED)
    await hass.async_block_till_done()

    assert _reauth_flow_started(hass)
    assert hass.states.get(PUBLIC_ONLY_ALARM_ENTITY_ID).state == STATE_UNAVAILABLE


def _mutate_backfill_missing(client: Mock) -> None:
    client.public_bootstrap.nvr.mac = None


def _mutate_prime_unauthorized(client: Mock) -> None:
    client.update_public = AsyncMock(side_effect=NotAuthorized)


def _mutate_old_version(client: Mock) -> None:
    meta = Mock()
    meta.version = Version("1.0.0")
    client.get_meta_info = AsyncMock(return_value=meta)


def _mutate_prime_transport_error(client: Mock) -> None:
    client.update_public = AsyncMock(side_effect=ClientError)


def _mutate_no_public_nvr(client: Mock) -> None:
    client.public_bootstrap.nvr = None


@pytest.mark.parametrize(
    ("mutate", "expected_state"),
    [
        pytest.param(
            _mutate_backfill_missing,
            ConfigEntryState.SETUP_RETRY,
            id="unresolved_mac_retries",
        ),
        pytest.param(
            _mutate_prime_unauthorized,
            ConfigEntryState.SETUP_RETRY,
            id="rejected_key_buffered_like_private",
        ),
        pytest.param(
            _mutate_old_version,
            ConfigEntryState.SETUP_ERROR,
            id="old_version_aborts",
        ),
        pytest.param(
            _mutate_prime_transport_error,
            ConfigEntryState.SETUP_RETRY,
            id="transport_error_retries",
        ),
        pytest.param(
            _mutate_no_public_nvr,
            ConfigEntryState.SETUP_RETRY,
            id="missing_public_nvr_retries",
        ),
    ],
)
async def test_public_only_setup_failures(
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
    mutate: Callable[[Mock], None],
    expected_state: ConfigEntryState,
) -> None:
    """Each public-only setup failure lands in the right config-entry state."""
    mutate(ufp_public_only.api)

    await setup_public_only()

    assert ufp_public_only.entry.state is expected_state


async def test_public_only_rejected_key_exhausts_to_reauth(
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """Persistent 401s exhaust the retry buffer and abort to reauth."""
    ufp_public_only.api.update_public = AsyncMock(side_effect=NotAuthorized)

    with patch("homeassistant.components.unifiprotect.AUTH_RETRIES", 0):
        await setup_public_only()

    assert ufp_public_only.entry.state is ConfigEntryState.SETUP_ERROR


async def test_public_only_sets_unique_id_when_missing(
    hass: HomeAssistant,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """Setup resolves and stores the unique id when the entry lacks one."""
    hass.config_entries.async_update_entry(ufp_public_only.entry, unique_id=None)

    await setup_public_only()

    assert ufp_public_only.entry.state is ConfigEntryState.LOADED
    assert ufp_public_only.entry.unique_id == UNIFI_MAC


async def test_public_only_device_removal(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """Device removal works without a private bootstrap.

    The NVR (a live device) must refuse removal; a stale device unknown to
    the public cache must allow it.
    """
    await setup_public_only()

    nvr_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, UNIFI_MAC), ufp_public_only.entry.entry_id
    )
    assert nvr_device is not None
    assert not await async_remove_config_entry_device(
        hass, ufp_public_only.entry, nvr_device
    )

    stale = device_registry.async_get_or_create(
        config_entry_id=ufp_public_only.entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "FFEEDDCCBB99")},
    )
    assert await async_remove_config_entry_device(hass, ufp_public_only.entry, stale)

    # A live camera must refuse removal even if its public mac is not in the
    # registry's normalized (uppercase, no separator) format.
    camera = Mock(spec=PublicCamera)
    camera.mac = "aa:bb:cc:dd:ee:01"
    ufp_public_only.api.public_bootstrap.cameras = {"cam-id": camera}
    camera_device = device_registry.async_get_or_create(
        config_entry_id=ufp_public_only.entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "AABBCCDDEE01")},
    )
    assert not await async_remove_config_entry_device(
        hass, ufp_public_only.entry, camera_device
    )


async def test_public_only_manual_refresh(
    hass: HomeAssistant,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """A manual refresh (update_entity action) runs publicly and stays healthy."""
    await setup_public_only()
    ufp_public_only.api.update_public.reset_mock()

    await ufp_public_only.entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    ufp_public_only.api.update_public.assert_awaited_once()
    # The private update path must not run (it would poison the health flag).
    assert ufp_public_only.entry.runtime_data.last_update_success is True
    assert (
        hass.states.get(PUBLIC_ONLY_ALARM_ENTITY_ID).state
        == AlarmControlPanelState.DISARMED
    )


async def test_public_only_manual_refresh_revoked_key_triggers_reauth(
    hass: HomeAssistant,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """Persistent 401s on manual refresh buffer like the private path, then reauth."""
    await setup_public_only()
    ufp_public_only.api.update_public = AsyncMock(side_effect=NotAuthorized)

    for _ in range(AUTH_RETRIES):
        await ufp_public_only.entry.runtime_data.async_refresh()
        assert not _reauth_flow_started(hass)

    await ufp_public_only.entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert _reauth_flow_started(hass)


async def test_public_only_setup_retakes_add_baseline(
    hass: HomeAssistant,
    light: Light,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A ProtectData kept from an earlier attempt retakes the add baseline.

    HA only drops ``runtime_data`` after a successful unload, so an entry that
    never loaded keeps its ProtectData across a mode switch. Its baseline was
    taken in full-access mode, where the mac set stays empty on purpose, and
    reusing it would re-offer every enumerated device on the first reconnect.
    """
    api = ufp_public_only.api
    api.public_bootstrap.lights = {light.id: make_public_light(light)}

    # The object a full-access attempt leaves behind: baseline taken, no macs.
    stale = ProtectData(hass, api, SCAN_INTERVAL, ufp_public_only.entry)
    api.is_public_only = False
    await stale.async_update_public()
    api.is_public_only = True
    ufp_public_only.entry.runtime_data = stale

    await setup_public_only()
    assert len(hass.states.async_entity_ids(Platform.LIGHT.value)) == 1

    ufp_public_only.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    ufp_public_only.devices_ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(Platform.LIGHT.value)) == 1
    assert "already exists" not in caplog.text
