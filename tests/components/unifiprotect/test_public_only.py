"""Tests for the UniFi Protect public-API-only (API-key) mode."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

from uiprotect.data import (
    ModelType,
    NvrArmMode,
    NvrArmModeStatus,
    PublicBootstrap,
    Version,
)
from uiprotect.data.public_devices import PublicNVR
from uiprotect.exceptions import ClientError, NotAuthorized
from uiprotect.websocket import WebsocketState

from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

_UNIFI_MAC = "AABBCCDDEEFF"
_ALARM_ENTITY_ID = "alarm_control_panel.test_nvr_alarm_manager"


def _public_only_entry() -> MockConfigEntry:
    """Build a public-API-only config entry (no local user)."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 443,
            CONF_VERIFY_SSL: False,
            CONF_API_KEY: "test-api-key",
            "id": "1.1.1.1",
        },
        version=2,
        unique_id=_UNIFI_MAC,
    )


def _public_client() -> Mock:
    """Build a mock public-only ProtectApiClient for setup."""
    client = Mock()
    client.is_public_only = True
    client.has_public_bootstrap = True

    meta = Mock()
    meta.version = Version("7.1.83")
    client.get_meta_info = AsyncMock(return_value=meta)
    client.update_public = AsyncMock()
    client.async_disconnect_ws = AsyncMock()

    arm_mode = Mock(spec=NvrArmMode)
    arm_mode.status = NvrArmModeStatus.DISABLED
    nvr = Mock(spec=PublicNVR)
    # The library backfills the mac during update_public(); it is present here.
    nvr.mac = _UNIFI_MAC
    nvr.name = "Test NVR"
    nvr.device_type = "UNVR4"  # present on firmware newer than 7.1
    nvr.id = "nvr-id"
    nvr.model = ModelType.NVR
    pb = Mock(spec=PublicBootstrap)
    pb.nvr = nvr
    pb.arm_mode = arm_mode
    client.public_bootstrap = pb

    subs: dict[str, object] = {}

    def _sub_devices(cb: object) -> Mock:
        subs["devices"] = cb
        return Mock()

    def _sub_devices_state(cb: object) -> Mock:
        subs["devices_state"] = cb
        return Mock()

    def _sub_events(cb: object) -> Mock:
        subs["events"] = cb
        return Mock()

    client.subscribe_devices_websocket = Mock(side_effect=_sub_devices)
    client.subscribe_devices_websocket_state = Mock(side_effect=_sub_devices_state)
    client.subscribe_events = Mock(side_effect=_sub_events)
    client._subs = subs
    return client


async def _setup_public_only(hass: HomeAssistant) -> tuple[MockConfigEntry, Mock]:
    """Set up a public-only entry and return (entry, client)."""
    entry = _public_only_entry()
    entry.add_to_hass(hass)
    client = _public_client()
    with patch(
        "homeassistant.components.unifiprotect.async_create_api_client",
        return_value=client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry, client


async def test_public_only_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A public-only entry loads, creates the NVR device, and the alarm panel."""
    entry, client = await _setup_public_only(hass)

    assert entry.state is ConfigEntryState.LOADED
    # The private bootstrap is never fetched in this mode.
    client.get_bootstrap.assert_not_called()

    device = device_registry.async_get_device(identifiers={(DOMAIN, _UNIFI_MAC)})
    assert device is not None
    assert device.sw_version == "7.1.83"
    # Name always, model on firmware newer than 7.1.
    assert device.name == "Test NVR"
    assert device.model == "UNVR4"
    # Degraded identity: no market name / console url.
    assert device.configuration_url is None

    state = hass.states.get(_ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == "disarmed"


async def test_public_only_only_alarm_platform(hass: HomeAssistant) -> None:
    """Only the alarm panel is forwarded in public-only mode."""
    await _setup_public_only(hass)

    # No cameras / sensors / etc. — those need the private bootstrap.
    assert not hass.states.async_entity_ids(Platform.CAMERA)
    assert not hass.states.async_entity_ids(Platform.SENSOR)
    assert not hass.states.async_entity_ids(Platform.BINARY_SENSOR)
    assert len(hass.states.async_entity_ids(Platform.ALARM_CONTROL_PANEL)) == 1


async def test_public_only_auth_failed_triggers_reauth(hass: HomeAssistant) -> None:
    """A revoked API key on the public websocket starts a reauth flow."""
    entry, client = await _setup_public_only(hass)

    state_cb = client._subs["devices_state"]
    with patch.object(entry, "async_start_reauth") as mock_reauth:
        state_cb(WebsocketState.AUTH_FAILED)
        await hass.async_block_till_done()

    assert mock_reauth.called
    # AUTH_FAILED arrives instead of DISCONNECTED: the stale public data must
    # not keep rendering as live while the reauth is pending.
    assert hass.states.get(_ALARM_ENTITY_ID).state == "unavailable"


async def test_public_only_unresolved_mac_not_ready(hass: HomeAssistant) -> None:
    """An NVR mac the library could not backfill leaves the entry retrying."""
    entry = _public_only_entry()
    entry.add_to_hass(hass)
    client = _public_client()
    client.public_bootstrap.nvr.mac = None
    with patch(
        "homeassistant.components.unifiprotect.async_create_api_client",
        return_value=client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_public_only_auth_failed_on_prime(hass: HomeAssistant) -> None:
    """A rejected API key while priming aborts to reauth."""

    entry = _public_only_entry()
    entry.add_to_hass(hass)
    client = _public_client()
    client.update_public = AsyncMock(side_effect=NotAuthorized)
    with patch(
        "homeassistant.components.unifiprotect.async_create_api_client",
        return_value=client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_public_only_version_too_old(hass: HomeAssistant) -> None:
    """An NVR below the minimum version aborts setup."""
    entry = _public_only_entry()
    entry.add_to_hass(hass)
    client = _public_client()
    meta = Mock()
    meta.version = Version("1.0.0")
    client.get_meta_info = AsyncMock(return_value=meta)
    with patch(
        "homeassistant.components.unifiprotect.async_create_api_client",
        return_value=client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_public_only_sets_unique_id_when_missing(hass: HomeAssistant) -> None:
    """Setup resolves and stores the unique id when the entry lacks one."""
    entry = _public_only_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, unique_id=None)
    client = _public_client()
    with patch(
        "homeassistant.components.unifiprotect.async_create_api_client",
        return_value=client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == _UNIFI_MAC


async def test_public_only_nvr_websocket_updates_alarm(hass: HomeAssistant) -> None:
    """An NVR devices-websocket frame re-renders the alarm from the public arm mode."""
    _entry, client = await _setup_public_only(hass)

    # Flip the public arm mode, then deliver an NVR frame over the devices WS.
    client.public_bootstrap.arm_mode.status = NvrArmModeStatus.ARMED
    devices_cb = client._subs["devices"]
    msg = Mock()
    msg.new_obj = client.public_bootstrap.nvr  # model == NVR
    msg.old_obj = None
    devices_cb(msg)
    await hass.async_block_till_done()

    state = hass.states.get(_ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == "armed_away"


async def test_public_only_ws_state_refreshes_alarm(hass: HomeAssistant) -> None:
    """A public devices-websocket reconnect re-signals the NVR alarm panel."""
    _entry, client = await _setup_public_only(hass)

    state_cb = client._subs["devices_state"]
    # Drop then restore: the restore re-signals the NVR (public branch).
    state_cb(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get(_ALARM_ENTITY_ID).state == "unavailable"

    state_cb(WebsocketState.CONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get(_ALARM_ENTITY_ID).state == "disarmed"


async def test_public_only_prime_client_error_not_ready(hass: HomeAssistant) -> None:
    """A transport error while priming leaves the entry in a retry state."""

    entry = _public_only_entry()
    entry.add_to_hass(hass)
    client = _public_client()
    client.update_public = AsyncMock(side_effect=ClientError)
    with patch(
        "homeassistant.components.unifiprotect.async_create_api_client",
        return_value=client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_public_only_no_public_nvr_not_ready(hass: HomeAssistant) -> None:
    """A missing public NVR (fetch failed) leaves the entry retrying."""
    entry = _public_only_entry()
    entry.add_to_hass(hass)
    client = _public_client()
    client.public_bootstrap.nvr = None
    with patch(
        "homeassistant.components.unifiprotect.async_create_api_client",
        return_value=client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
