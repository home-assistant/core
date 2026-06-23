"""Test the UniFi Protect camera platform."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from uiprotect.data import AiPort, Camera as ProtectCamera, StateType
from uiprotect.exceptions import ClientError, NotAuthorized

from homeassistant.components.camera import (
    CameraEntityFeature,
    async_get_image,
    async_get_stream_source,
)
from homeassistant.components.unifiprotect.const import CONF_DISABLE_RTSP, DOMAIN
from homeassistant.components.unifiprotect.utils import get_camera_base_name
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from . import patch_ufp_method
from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    enable_entity,
    init_entry,
    remove_entities,
)


def _channel_entity_id(camera_obj: ProtectCamera, channel_id: int) -> str:
    """Return the entity_id for a camera channel."""
    channel = camera_obj.channels[channel_id]
    base_name = get_camera_base_name(channel)
    return f"camera.{camera_obj.name}_{base_name}".replace(" ", "_").lower()


def _assert_entity(
    hass: HomeAssistant,
    camera_obj: ProtectCamera,
    channel_id: int,
    *,
    enabled: bool,
) -> str:
    """Assert a camera entity exists with the secure unique_id and no insecure twin."""
    entity_id = _channel_entity_id(camera_obj, channel_id)
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is not enabled
    assert entity.unique_id == f"{camera_obj.mac}_{camera_obj.channels[channel_id].id}"
    # The legacy insecure private-path entity must not exist anymore.
    assert (
        entity_registry.async_get(f"{entity_id}_insecure".replace(" ", "_").lower())
        is None
    )
    return entity_id


async def test_basic_setup(
    hass: HomeAssistant, ufp: MockUFPFixture, camera_all: ProtectCamera
) -> None:
    """One enabled high entity plus disabled medium/low, all secure."""
    await init_entry(hass, ufp, [camera_all])

    # high (enabled) + medium + low (disabled); no insecure entities
    assert_entity_counts(hass, Platform.CAMERA, 3, 1)

    high_id = _assert_entity(hass, camera_all, 0, enabled=True)
    assert (
        await async_get_stream_source(hass, high_id)
        == camera_all.channels[0].rtsps_no_srtp_url
    )

    # medium starts disabled; once enabled it streams from the public API
    medium_id = _assert_entity(hass, camera_all, 1, enabled=False)
    await enable_entity(hass, ufp.entry.entry_id, medium_id)
    assert (
        await async_get_stream_source(hass, medium_id)
        == camera_all.channels[1].rtsps_no_srtp_url
    )

    _assert_entity(hass, camera_all, 2, enabled=False)


async def test_doorbell_setup(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: ProtectCamera
) -> None:
    """Doorbell exposes its active qualities; the package channel is just one of them."""
    await init_entry(hass, ufp, [doorbell])

    # high (enabled) + package (active too, disabled by default); both stream
    assert_entity_counts(hass, Platform.CAMERA, 2, 1)

    high_id = _assert_entity(hass, doorbell, 0, enabled=True)
    assert (
        await async_get_stream_source(hass, high_id)
        == doorbell.channels[0].rtsps_no_srtp_url
    )

    # the package channel is not special-cased: it streams like any quality tier
    package_id = _assert_entity(hass, doorbell, 3, enabled=False)
    await enable_entity(hass, ufp.entry.entry_id, package_id)
    assert (
        await async_get_stream_source(hass, package_id)
        == doorbell.channels[3].rtsps_no_srtp_url
    )


async def test_first_active_quality_is_default(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera_all: ProtectCamera,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The first active quality is the default; inactive ones get no entity."""
    camera_all.channels = [c.model_copy() for c in camera_all.channels]
    camera_all.channels[0].is_rtsp_enabled = False  # high inactive
    camera_all.channels[1].is_rtsp_enabled = True  # medium active
    camera_all.channels[2].is_rtsp_enabled = False  # low inactive

    await init_entry(hass, ufp, [camera_all])

    # only medium exists, enabled by default, with a working stream
    assert_entity_counts(hass, Platform.CAMERA, 1, 1)
    medium_id = _assert_entity(hass, camera_all, 1, enabled=True)
    assert (
        await async_get_stream_source(hass, medium_id)
        == camera_all.channels[1].rtsps_no_srtp_url
    )

    entity_registry = er.async_get(hass)  # pylint: disable=home-assistant-tests-registry-fixtures
    assert entity_registry.async_get(_channel_entity_id(camera_all, 0)) is None
    assert entity_registry.async_get(_channel_entity_id(camera_all, 2)) is None
    assert (
        issue_registry.async_get_issue(DOMAIN, f"rtsp_disabled_{camera_all.id}") is None
    )


async def test_no_active_stream(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: ProtectCamera,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A camera with no active stream is exposed for snapshots and raises a repair."""
    camera.channels = [c.model_copy() for c in camera.channels]
    for channel in camera.channels:
        channel.is_rtsp_enabled = False

    await init_entry(hass, ufp, [camera])

    high_id = _assert_entity(hass, camera, 0, enabled=True)
    assert await async_get_stream_source(hass, high_id) is None
    state = hass.states.get(high_id)
    assert state
    assert state.attributes["supported_features"] == CameraEntityFeature(0)
    assert (
        issue_registry.async_get_issue(DOMAIN, f"rtsp_disabled_{camera.id}") is not None
    )


async def test_offline_camera_no_repair(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: ProtectCamera,
    issue_registry: ir.IssueRegistry,
) -> None:
    """An offline camera with no stream gets no repair (offline, not disabled)."""
    camera.state = StateType.DISCONNECTED

    await init_entry(hass, ufp, [camera])

    _assert_entity(hass, camera, 0, enabled=True)
    assert issue_registry.async_get_issue(DOMAIN, f"rtsp_disabled_{camera.id}") is None


@pytest.mark.parametrize("ufp_options", [{CONF_DISABLE_RTSP: True}], indirect=True)
async def test_disable_rtsp(
    hass: HomeAssistant, ufp: MockUFPFixture, camera_all: ProtectCamera
) -> None:
    """Disabling RTSP globally removes the stream source."""
    await init_entry(hass, ufp, [camera_all])

    high_id = _assert_entity(hass, camera_all, 0, enabled=True)
    assert await async_get_stream_source(hass, high_id) is None


async def test_camera_image(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """Main snapshot is fetched from the public API."""
    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.CAMERA, 1, 1)

    ufp.api.get_public_api_camera_snapshot = AsyncMock()
    await async_get_image(hass, _channel_entity_id(camera, 0))
    ufp.api.get_public_api_camera_snapshot.assert_called_once()
    assert ufp.api.get_public_api_camera_snapshot.call_args.kwargs["package"] is False


async def test_package_camera_image(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: ProtectCamera
) -> None:
    """Package snapshot is fetched from the public API with package=True."""
    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.CAMERA, 2, 1)

    package_id = _channel_entity_id(doorbell, 3)
    await enable_entity(hass, ufp.entry.entry_id, package_id)
    ufp.api.get_public_api_camera_snapshot = AsyncMock()
    await async_get_image(hass, package_id)
    ufp.api.get_public_api_camera_snapshot.assert_called_once()
    assert ufp.api.get_public_api_camera_snapshot.call_args.kwargs["package"] is True


async def test_package_camera_without_stream(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: ProtectCamera
) -> None:
    """The package camera stays available for snapshots when its stream is off."""
    doorbell.channels = [c.model_copy() for c in doorbell.channels]
    doorbell.channels[3].is_rtsp_enabled = False  # package stream off (the default)

    await init_entry(hass, ufp, [doorbell])

    # high (enabled, streaming) + package (disabled, snapshot-only) still present
    assert_entity_counts(hass, Platform.CAMERA, 2, 1)

    package_id = _assert_entity(hass, doorbell, 3, enabled=False)
    await enable_entity(hass, ufp.entry.entry_id, package_id)
    assert await async_get_stream_source(hass, package_id) is None
    state = hass.states.get(package_id)
    assert state
    assert state.attributes["supported_features"] == CameraEntityFeature(0)

    # snapshots still work, fetched with package=True
    ufp.api.get_public_api_camera_snapshot = AsyncMock()
    await async_get_image(hass, package_id)
    assert ufp.api.get_public_api_camera_snapshot.call_args.kwargs["package"] is True


async def test_package_only_camera(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: ProtectCamera,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A camera with only a package channel still exposes a snapshot entity."""
    package = camera.channels[0].model_copy()
    package.id = 3
    package.fps = 2
    package.is_rtsp_enabled = False
    camera.channels = [package]

    await init_entry(hass, ufp, [camera])

    # only the package snapshot entity (disabled by default); no main fallback, no repair
    assert_entity_counts(hass, Platform.CAMERA, 1, 0)
    _assert_entity(hass, camera, 0, enabled=False)
    assert issue_registry.async_get_issue(DOMAIN, f"rtsp_disabled_{camera.id}") is None


async def test_no_channels(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """A camera without channels yet creates no entities."""
    camera.channels = []

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.CAMERA, 0, 0)


async def test_streams_unavailable(
    hass: HomeAssistant, ufp: MockUFPFixture, camera_all: ProtectCamera
) -> None:
    """A camera the library leaves unprimed (no streams) has no stream source."""

    async def _prime_streamless() -> Any:
        pb = ufp.api.public_bootstrap
        pb.cameras = {
            camera_all.id: SimpleNamespace(
                id=camera_all.id, state=camera_all.state, rtsps_streams=None
            )
        }
        return pb

    ufp.api.update_public = AsyncMock(side_effect=_prime_streamless)

    await init_entry(hass, ufp, [camera_all])

    high_id = _channel_entity_id(camera_all, 0)
    assert await async_get_stream_source(hass, high_id) is None


async def test_public_bootstrap_failure_not_ready(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """A failed public bootstrap prime leaves the entry in setup-retry.

    The websockets/poll subscriptions opened during setup must be torn down so
    a retry does not leak another set.
    """
    ufp.api.update_public = AsyncMock(side_effect=ClientError("boom"))

    await init_entry(hass, ufp, [camera])

    assert ufp.entry.state is ConfigEntryState.SETUP_RETRY
    ufp.api.async_disconnect_ws.assert_called()


async def test_public_bootstrap_revoked_key_reauth(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """A revoked API key (public 401) triggers reauth, not an endless retry."""
    ufp.api.update_public = AsyncMock(side_effect=NotAuthorized("revoked"))

    await init_entry(hass, ufp, [camera])

    assert ufp.entry.state is ConfigEntryState.SETUP_ERROR
    ufp.api.async_disconnect_ws.assert_called()
    assert any(ufp.entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_adopt(
    hass: HomeAssistant, ufp: MockUFPFixture, camera_all: ProtectCamera
) -> None:
    """A camera adopted at runtime loads its public streams before entities."""
    await init_entry(hass, ufp, [camera_all])
    assert_entity_counts(hass, Platform.CAMERA, 3, 1)

    await remove_entities(hass, ufp, [camera_all])
    assert_entity_counts(hass, Platform.CAMERA, 0, 0)

    await adopt_devices(hass, ufp, [camera_all])
    assert_entity_counts(hass, Platform.CAMERA, 3, 1)

    high_id = _assert_entity(hass, camera_all, 0, enabled=True)
    assert (
        await async_get_stream_source(hass, high_id)
        == camera_all.channels[0].rtsps_no_srtp_url
    )


@pytest.mark.parametrize(
    ("service", "expected_value"),
    [
        ("enable_motion_detection", True),
        ("disable_motion_detection", False),
    ],
)
async def test_camera_motion_detection(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: ProtectCamera,
    service: str,
    expected_value: bool,
) -> None:
    """Test enabling/disabling motion detection on a camera."""
    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.CAMERA, 1, 1)
    entity_id = _channel_entity_id(camera, 0)

    with patch_ufp_method(
        camera, "set_motion_detection", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "camera",
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_method.assert_called_once_with(expected_value)


async def test_aiport_no_camera_entities(
    hass: HomeAssistant, ufp: MockUFPFixture, aiport: AiPort
) -> None:
    """AI Port devices do not create camera entities."""
    await init_entry(hass, ufp, [aiport])
    assert_entity_counts(hass, Platform.CAMERA, 0, 0)


async def test_aiport_stream_issue_cleanup(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    aiport: AiPort,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Stale public-stream issues for AI Ports are cleaned up on setup."""
    await init_entry(hass, ufp, [aiport])

    issue_id = f"rtsp_disabled_{aiport.id}"
    # Simulate a legacy issue created directly (bypass translation validation).
    issue_registry.issues[(DOMAIN, issue_id)] = ir.IssueEntry(
        active=True,
        breaks_in_ha_version=None,
        created=None,
        data=None,
        dismissed_version=None,
        domain=DOMAIN,
        is_fixable=True,
        is_persistent=False,
        issue_domain=None,
        issue_id=issue_id,
        learn_more_url=None,
        severity=ir.IssueSeverity.WARNING,
        translation_key="rtsp_disabled",
        translation_placeholders=None,
    )
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    await hass.config_entries.async_reload(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    assert_entity_counts(hass, Platform.CAMERA, 0, 0)


async def test_snapshot_low_quality_without_stream(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """Without a live stream, snapshots are requested at low quality."""
    camera.channels = [c.model_copy() for c in camera.channels]
    for channel in camera.channels:
        channel.is_rtsp_enabled = False

    await init_entry(hass, ufp, [camera])

    ufp.api.get_public_api_camera_snapshot = AsyncMock()
    await async_get_image(hass, _channel_entity_id(camera, 0))
    ufp.api.get_public_api_camera_snapshot.assert_called_once()
    assert (
        ufp.api.get_public_api_camera_snapshot.call_args.kwargs["high_quality"] is False
    )
