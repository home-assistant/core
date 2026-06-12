"""Test the UniFi Protect camera platform with public-API streams."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from uiprotect.data import Camera as ProtectCamera, StateType

from homeassistant.components.camera import (
    CameraEntityFeature,
    async_get_image,
    async_get_stream_source,
)
from homeassistant.components.unifiprotect.const import (
    CONF_DISABLE_RTSP,
    CONF_USE_PUBLIC_API_STREAMS,
    DOMAIN,
)
from homeassistant.components.unifiprotect.utils import get_camera_base_name
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    enable_entity,
    init_entry,
    remove_entities,
)


@pytest.fixture(name="ufp_options")
def _public_stream_options(request: pytest.FixtureRequest) -> dict[str, Any]:
    """Use the public-API stream path (plus any per-test overrides)."""
    options: dict[str, Any] = {CONF_USE_PUBLIC_API_STREAMS: True}
    if hasattr(request, "param"):
        options.update(request.param)
    return options


@pytest.fixture(autouse=True)
def _primed_public_bootstrap(ufp: MockUFPFixture) -> None:
    """The public stream path reads streams from a primed public bootstrap."""
    ufp.api.has_public_bootstrap = True


def _channel_entity_id(camera_obj: ProtectCamera, channel_id: int) -> str:
    """Return the entity_id for a camera channel in public stream mode."""
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
    """Assert a public-mode camera entity exists with the secure unique_id."""
    entity_id = _channel_entity_id(camera_obj, channel_id)
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is not enabled
    assert entity.unique_id == f"{camera_obj.mac}_{camera_obj.channels[channel_id].id}"
    # The insecure private-path entity must not exist in public mode.
    assert (
        entity_registry.async_get(f"{entity_id}_insecure".replace(" ", "_").lower())
        is None
    )
    return entity_id


async def test_public_basic_setup(
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


async def test_public_doorbell_setup(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: ProtectCamera
) -> None:
    """Doorbell adds a package entity (snapshot only) enabled by default."""
    await init_entry(hass, ufp, [doorbell])

    # only the active high quality + the package camera (mirrors private path)
    assert_entity_counts(hass, Platform.CAMERA, 2, 2)

    high_id = _assert_entity(hass, doorbell, 0, enabled=True)
    assert (
        await async_get_stream_source(hass, high_id)
        == doorbell.channels[0].rtsps_no_srtp_url
    )

    # package camera is enabled but provides snapshots only (no stream)
    package_id = _assert_entity(hass, doorbell, 3, enabled=True)
    assert await async_get_stream_source(hass, package_id) is None
    state = hass.states.get(package_id)
    assert state
    assert state.attributes["supported_features"] == CameraEntityFeature(0)


async def test_public_first_active_is_default(
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

    # inactive high/low get no entity, and no repair is raised (a quality streams)
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(_channel_entity_id(camera_all, 0)) is None
    assert entity_registry.async_get(_channel_entity_id(camera_all, 2)) is None
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"public_stream_disabled_{camera_all.id}"
        )
        is None
    )


async def test_public_no_active_stream(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """An enabled entity with no created RTSPS stream has no source."""
    camera.channels = [c.model_copy() for c in camera.channels]
    for channel in camera.channels:
        channel.is_rtsp_enabled = False

    await init_entry(hass, ufp, [camera])

    high_id = _assert_entity(hass, camera, 0, enabled=True)
    assert await async_get_stream_source(hass, high_id) is None
    state = hass.states.get(high_id)
    assert state
    assert state.attributes["supported_features"] == CameraEntityFeature(0)


async def test_public_offline_camera_no_repair(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: ProtectCamera,
    issue_registry: ir.IssueRegistry,
) -> None:
    """An offline camera with no stream gets no repair (offline, not disabled)."""
    camera.state = StateType.DISCONNECTED

    await init_entry(hass, ufp, [camera])

    # the camera is still exposed, but no public_stream_disabled repair is raised
    _assert_entity(hass, camera, 0, enabled=True)
    assert (
        issue_registry.async_get_issue(DOMAIN, f"public_stream_disabled_{camera.id}")
        is None
    )


@pytest.mark.parametrize("ufp_options", [{CONF_DISABLE_RTSP: True}], indirect=True)
async def test_public_disable_rtsp(
    hass: HomeAssistant, ufp: MockUFPFixture, camera_all: ProtectCamera
) -> None:
    """Disabling RTSP globally removes the stream in public mode too."""
    await init_entry(hass, ufp, [camera_all])

    high_id = _assert_entity(hass, camera_all, 0, enabled=True)
    assert await async_get_stream_source(hass, high_id) is None


async def test_public_camera_image(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """Main snapshot is fetched from the public API."""
    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.CAMERA, 1, 1)

    ufp.api.get_public_api_camera_snapshot = AsyncMock()
    await async_get_image(hass, _channel_entity_id(camera, 0))
    ufp.api.get_public_api_camera_snapshot.assert_called_once()
    assert ufp.api.get_public_api_camera_snapshot.call_args.kwargs["package"] is False


async def test_public_package_camera_image(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: ProtectCamera
) -> None:
    """Package snapshot is fetched from the public API with package=True."""
    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.CAMERA, 2, 2)

    ufp.api.get_public_api_camera_snapshot = AsyncMock()
    await async_get_image(hass, _channel_entity_id(doorbell, 3))
    ufp.api.get_public_api_camera_snapshot.assert_called_once()
    assert ufp.api.get_public_api_camera_snapshot.call_args.kwargs["package"] is True


async def test_public_no_channels(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: ProtectCamera
) -> None:
    """A camera without channels yet creates no entities."""
    camera.channels = []

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.CAMERA, 0, 0)


async def test_public_streams_unavailable(
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


async def test_public_adopt(
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
