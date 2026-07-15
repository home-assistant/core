"""Test the Bosch Smart Home Camera image platform."""

from http import HTTPStatus
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bosch_shc_camera.const import CLOUD_API
from homeassistant.components.bosch_shc_camera.snapshot_store import save_snapshot
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CAM_ID = "aabbccdd-1122-3344-5566-778899001122"
ENTITY_ID = "image.bosch_terrasse_last_snapshot"
FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"x" * 200  # padded past the 100 B min-size gate


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Use a per-test tmp config dir.

    `snapshot_store.py` writes real files via

    raw filesystem paths (`hass.config.path(".storage")`), bypassing HA's
    Store abstraction. The default `hass_config_dir` fixture points at the
    shared `tests/testing_config/` directory, so without this override a
    saved snapshot leaks onto real disk and pollutes subsequent test runs
    (reproduced: a stray `tests/testing_config/.storage/bosch_shc_camera/
    snapshots/AABBCCDD-....jpg` survived a prior run of this file and was
    served back as a false-positive by `test_image_returns_none_when_no_source_available`).
    """
    return hass_tmp_config_dir


def _mock_video_inputs(aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(
        f"{CLOUD_API}/v11/video_inputs",
        json=[
            {
                "id": CAM_ID,
                "title": "Terrasse",
                "hardwareVersion": "HOME_Eyes_Outdoor",
                "firmwareVersion": "9.40.104",
                "privacyMode": "OFF",
                "featureSupport": {},
            }
        ],
    )
    aioclient_mock.get(f"{CLOUD_API}/v11/feature_flags", json={})
    aioclient_mock.get(f"{CLOUD_API}/protocol_support", json={"state": "SUPPORTED"})


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """One image entity per configured camera, snapshotted."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, options={**config_entry.options, "enable_binary_sensors": False}
    )
    _mock_video_inputs(aioclient_mock)

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.ALL_PLATFORMS",
            [Platform.IMAGE],
        ),
        # Pin the randomly-generated access_token so the snapshot is stable
        # across runs (same pattern as tests/components/tplink/test_camera.py).
        patch("random.SystemRandom.getrandbits", return_value=123123123123),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_enable_snapshots_false_skips_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`enable_snapshots=False` skips the image platform entirely (matches camera.py's gate)."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, options={**config_entry.options, "enable_snapshots": False}
    )
    _mock_video_inputs(aioclient_mock)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(ENTITY_ID) is None


async def test_image_serves_disk_snapshot(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """After a persisted snapshot + notify_refreshed, the entity serves it via the image proxy.

    `async_notify_refreshed()` is the documented public hook `BoschCamera`
    calls after persisting a fresh snapshot (see `image.py`'s class
    docstring) — calling it directly here reproduces that production call
    site without poking at the entity's private `_cached_bytes`.
    """
    _mock_video_inputs(aioclient_mock)
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data

    await save_snapshot(hass, CAM_ID, FAKE_JPEG)
    image_entity = coordinator.image_entities[CAM_ID]
    await image_entity.async_notify_refreshed()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == image_entity.image_last_updated.isoformat()

    client = await hass_client()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    assert (await resp.read()) == FAKE_JPEG


async def test_image_falls_back_to_camera_ram_cache(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """With nothing persisted to disk yet, the image entity serves the camera entity's RAM cache."""
    _mock_video_inputs(aioclient_mock)
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data

    camera_entity = coordinator.camera_entities[CAM_ID]
    camera_entity.cached_image = FAKE_JPEG
    image_entity = coordinator.image_entities[CAM_ID]
    await image_entity.async_notify_refreshed()

    state = hass.states.get(ENTITY_ID)
    client = await hass_client()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    assert (await resp.read()) == FAKE_JPEG


async def test_image_returns_none_when_no_source_available(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """`async_image()` returns None when neither disk nor RAM cache has real data yet.

    The camera entity's own placeholder JPEG (~180 B, under the image
    entity's 200 B "real snapshot" floor) must not be served as a real
    snapshot.
    """
    _mock_video_inputs(aioclient_mock)
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data

    image_entity = coordinator.image_entities[CAM_ID]
    assert await image_entity.async_image() is None


async def test_unload_unregisters_image_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """On removal, the image entity unregisters itself from `coordinator.image_entities`."""
    _mock_video_inputs(aioclient_mock)
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data
    assert CAM_ID in coordinator.image_entities

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert CAM_ID not in coordinator.image_entities
