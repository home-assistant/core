"""Tests for the UniFi Protect public-API-only (API-key) mode."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import web
import pytest
from uiprotect.data import (
    Camera,
    ModelType,
    NvrArmMode,
    NvrArmModeStatus,
    PublicBootstrap,
    Version,
)
from uiprotect.data.public_devices import PublicNVR
from uiprotect.exceptions import (
    BadRequest,
    ClientError,
    NotAuthorized,
    PublicOnlyModeError,
)
from uiprotect.websocket import WebsocketState

from homeassistant.components.camera import async_get_stream_source
from homeassistant.components.unifiprotect import async_remove_config_entry_device
from homeassistant.components.unifiprotect.const import ATTR_MESSAGE, DOMAIN
from homeassistant.components.unifiprotect.data import async_get_data_for_nvr_id
from homeassistant.components.unifiprotect.media_source import async_get_media_source
from homeassistant.components.unifiprotect.services import SERVICE_ADD_DOORBELL_TEXT
from homeassistant.components.unifiprotect.views import ThumbnailProxyView
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .utils import make_public_camera, public_rtsps_for

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

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


class _PublicOnlyClientMock(Mock):
    """Mock client mirroring the real public-only contract.

    Reading ``bootstrap`` on an API-key-only client raises ``BadRequest`` in
    the library; mirroring that here makes every accidental private-bootstrap
    read in a public-only code path fail loudly in tests.
    """

    @property
    def bootstrap(self) -> None:
        raise BadRequest("Client not initialized, run `update` first")


def _public_client() -> Mock:
    """Build a mock public-only ProtectApiClient for setup."""
    client = _PublicOnlyClientMock()
    client.is_public_only = True
    client.has_public_bootstrap = True

    meta = Mock()
    meta.version = Version("7.1.83")
    client.get_meta_info = AsyncMock(return_value=meta)
    client.update_public = AsyncMock()
    client.update = AsyncMock(side_effect=PublicOnlyModeError("public-only"))
    client.get_bootstrap = AsyncMock(side_effect=PublicOnlyModeError("public-only"))
    client.async_disconnect_ws = AsyncMock()

    arm_mode = Mock(spec=NvrArmMode)
    arm_mode.status = NvrArmModeStatus.DISABLED
    nvr = Mock(spec=PublicNVR)
    # The library backfills the mac during update_public(); it is present here.
    nvr.mac = _UNIFI_MAC
    nvr.name = "Test NVR"
    nvr.display_name = "Test NVR"
    nvr.device_type = "UNVR4"  # present on firmware newer than 7.1
    nvr.type = "UNVR4"
    nvr.id = "nvr-id"
    nvr.model = ModelType.NVR
    pb = Mock(spec=PublicBootstrap)
    pb.nvr = nvr
    pb.arm_mode = arm_mode
    pb.cameras = {}
    pb.get = Mock(
        side_effect=lambda model, obj_id: (
            pb.cameras.get(obj_id) if model is ModelType.CAMERA else None
        )
    )
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


async def test_public_only_only_alarm_and_camera_platforms(
    hass: HomeAssistant,
) -> None:
    """Only the alarm panel and camera are forwarded in public-only mode."""
    await _setup_public_only(hass)

    # No sensors / etc. — those still need the private bootstrap.
    assert not hass.states.async_entity_ids(Platform.SENSOR)
    assert not hass.states.async_entity_ids(Platform.BINARY_SENSOR)
    assert len(hass.states.async_entity_ids(Platform.ALARM_CONTROL_PANEL)) == 1


async def test_public_only_camera_end_to_end(
    hass: HomeAssistant, camera: Camera
) -> None:
    """A public-only entry with a camera in the bootstrap creates a working entity.

    Exercises the real public-only setup path (not the generic ``ufp`` fixture
    used by camera.py's own tests), proving cameras and the alarm panel coexist
    under ``PUBLIC_ONLY_PLATFORMS``.
    """
    client = _public_client()
    client.base_url = "https://1.1.1.1"
    # The stream-building test helper reads the private ``rtsps_url`` property,
    # which needs a client with a bootstrap; keep that off the public client.
    channel_api = Mock()
    for channel in camera.channels:
        channel._api = channel_api
    public = make_public_camera(camera)
    public.rtsps_streams = public_rtsps_for(camera)
    client.public_bootstrap.cameras = {camera.id: public}
    client.get_public_api_camera_snapshot = AsyncMock()

    entry = _public_only_entry()
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.unifiprotect.async_create_api_client",
        return_value=client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    high_id = f"camera.{camera.name}_high_resolution_channel".replace(" ", "_").lower()
    state = hass.states.get(high_id)
    assert state is not None
    assert state.state != "unavailable"
    assert (
        await async_get_stream_source(hass, high_id)
        == camera.channels[0].rtsps_no_srtp_url
    )
    assert len(hass.states.async_entity_ids(Platform.ALARM_CONTROL_PANEL)) == 1


async def test_public_only_auth_failed_triggers_reauth(hass: HomeAssistant) -> None:
    """A revoked API key on the public websocket starts a reauth flow.

    The library always emits DISCONNECTED before AUTH_FAILED (uiprotect
    15.12.2+), so the stale public data is marked unavailable by the regular
    disconnect path before reauth is triggered.
    """
    entry, client = await _setup_public_only(hass)

    state_cb = client._subs["devices_state"]
    with patch.object(entry, "async_start_reauth") as mock_reauth:
        state_cb(WebsocketState.DISCONNECTED)
        state_cb(WebsocketState.AUTH_FAILED)
        await hass.async_block_till_done()

    assert mock_reauth.called
    assert hass.states.get(_ALARM_ENTITY_ID).state == "unavailable"


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
    hass: HomeAssistant,
    mutate: Callable[[Mock], None],
    expected_state: ConfigEntryState,
) -> None:
    """Each public-only setup failure lands in the right config-entry state."""
    entry = _public_only_entry()
    entry.add_to_hass(hass)
    client = _public_client()
    mutate(client)
    with patch(
        "homeassistant.components.unifiprotect.async_create_api_client",
        return_value=client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is expected_state


async def test_public_only_rejected_key_exhausts_to_reauth(
    hass: HomeAssistant,
) -> None:
    """Persistent 401s exhaust the retry buffer and abort to reauth."""
    entry = _public_only_entry()
    entry.add_to_hass(hass)
    client = _public_client()
    client.update_public = AsyncMock(side_effect=NotAuthorized)
    with (
        patch(
            "homeassistant.components.unifiprotect.async_create_api_client",
            return_value=client,
        ),
        patch("homeassistant.components.unifiprotect.AUTH_RETRIES", 0),
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


async def test_public_only_entry_skipped_by_media_and_nvr_lookup(
    hass: HomeAssistant,
) -> None:
    """A public-only entry must not break the private-bootstrap consumers.

    The media source map and the nvr-id lookup (thumbnail/video views) iterate
    every loaded entry and read the private bootstrap; a public-only entry has
    none and must be skipped, not raise.
    """
    await _setup_public_only(hass)

    source = await async_get_media_source(hass)
    assert source.data_sources == {}
    assert async_get_data_for_nvr_id(hass, "nvr-id") is None


async def test_public_only_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Diagnostics for a public-only entry dump the public cache."""
    entry, client = await _setup_public_only(hass)
    client.public_bootstrap.nvr.unifi_dict = Mock(return_value={"name": "Test NVR"})
    camera = Mock()
    camera.unifi_dict = Mock(
        return_value={
            "name": "Cam",
            "rtspsStreams": {"high": "rtsps://10.0.0.2:7441/secret?enableSrtp"},
        }
    )
    client.public_bootstrap.cameras = {"cam-id": camera}

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert "bootstrap" not in diag
    # anonymize_data scrambles values; assert the structure, not the content
    assert "name" in diag["public_bootstrap"]["nvr"]
    assert diag["public_bootstrap"]["arm_mode"] is True
    # the stream URLs carry the console host and a secret alias — never leak
    dumped_camera = diag["public_bootstrap"]["cameras"][0]
    assert dumped_camera["rtspsStreams"] == "**REDACTED**"


async def test_public_only_action_rejected(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Actions require full access; a public-only device raises cleanly."""
    await _setup_public_only(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, _UNIFI_MAC)})
    assert device is not None

    with pytest.raises(HomeAssistantError, match="requires full access"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_DOORBELL_TEXT,
            {ATTR_DEVICE_ID: device.id, ATTR_MESSAGE: "Test Message"},
            blocking=True,
        )


async def test_public_only_entry_id_view_lookup_404(hass: HomeAssistant) -> None:
    """The media proxy views reject a public-only entry id with a 404."""
    entry, _client = await _setup_public_only(hass)

    view = ThumbnailProxyView(hass)
    result = view._get_data_or_404(entry.entry_id)
    assert isinstance(result, web.Response)
    assert result.status == 404


async def test_public_only_device_removal(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Device removal works without a private bootstrap.

    The NVR (a live device) must refuse removal; a stale device unknown to
    the public cache must allow it.
    """
    entry, _client = await _setup_public_only(hass)

    nvr_device = device_registry.async_get_device(identifiers={(DOMAIN, _UNIFI_MAC)})
    assert nvr_device is not None
    assert not await async_remove_config_entry_device(hass, entry, nvr_device)

    stale = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "FFEEDDCCBB99")},
    )
    assert await async_remove_config_entry_device(hass, entry, stale)


async def test_public_only_manual_refresh(hass: HomeAssistant) -> None:
    """A manual refresh (update_entity action) runs publicly and stays healthy."""
    entry, client = await _setup_public_only(hass)
    client.update_public.reset_mock()

    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    client.update_public.assert_awaited_once()
    # The private update path must not run (it would poison the health flag).
    assert entry.runtime_data.last_update_success is True
    assert hass.states.get(_ALARM_ENTITY_ID).state == "disarmed"
