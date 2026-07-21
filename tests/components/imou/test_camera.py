"""Tests for Imou camera platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyimouapi.const import PARAM_HD, PARAM_MOTION_DETECT, PARAM_STATE
from pyimouapi.exceptions import ImouException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import async_get_image, async_get_stream_source
from homeassistant.components.imou.camera import (
    CAMERA_STREAM_RESOLUTION_SD,
    PYIMOUAPI_LIVE_PROTOCOL,
    PYIMOUAPI_SNAPSHOT_WAIT_SECONDS,
)
from homeassistant.components.imou.const import PARAM_HEADER_DETECT
from homeassistant.components.imou.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import create_online_device

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

TEST_STREAM_URL = "https://example.com/live.m3u8"
TEST_IMAGE_BYTES = b"fake-image-bytes"


def _camera_entity_id(
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    *,
    device_key: str = "d1_1",
    camera_key: str = "camera_sd",
) -> str:
    """Return the entity id for a channel camera."""
    entry = next(
        registry_entry
        for registry_entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if registry_entry.unique_id == f"{device_key}${camera_key}"
    )
    return entry.entity_id


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "d1",
                "Device 1",
                channel_id="1",
                button_keys=(),
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.parametrize("platforms", [[Platform.CAMERA]], indirect=True)
@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default",
    "mock_camera_access_token",
    "init_integration",
)
async def test_camera_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot camera entities and states for a channel device."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "d1",
                "Device 1",
                button_keys=(),
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_no_camera_without_channel(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Devices without a channel do not get a camera entity."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    assert not any(entry.domain == "camera" for entry in entries)


@pytest.mark.parametrize(
    ("camera_key", "expected_resolution"),
    [
        ("camera_sd", CAMERA_STREAM_RESOLUTION_SD),
        ("camera_hd", PARAM_HD),
    ],
)
@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "d1",
                "Device 1",
                channel_id="1",
                button_keys=(),
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_camera_stream_source(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MagicMock,
    mock_config_entry: MockConfigEntry,
    camera_key: str,
    expected_resolution: str,
) -> None:
    """Fetching stream source calls the vendor library with the entity resolution."""
    init_integration.async_get_device_stream.return_value = TEST_STREAM_URL

    entity_id = _camera_entity_id(
        entity_registry, mock_config_entry, camera_key=camera_key
    )
    stream_source = await async_get_stream_source(hass, entity_id)

    assert stream_source == TEST_STREAM_URL
    init_integration.async_get_device_stream.assert_awaited_once()
    call = init_integration.async_get_device_stream.await_args
    assert call is not None
    assert call.args[1] == expected_resolution
    assert call.args[2] == PYIMOUAPI_LIVE_PROTOCOL


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "d1",
                "Device 1",
                channel_id="1",
                button_keys=(),
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_camera_image(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Still image fetch calls the vendor library with the configured wait time."""
    init_integration.async_get_device_image.return_value = TEST_IMAGE_BYTES

    entity_id = _camera_entity_id(entity_registry, mock_config_entry)
    image = await async_get_image(hass, entity_id)

    assert image.content == TEST_IMAGE_BYTES
    init_integration.async_get_device_image.assert_awaited_once()
    call = init_integration.async_get_device_image.await_args
    assert call is not None
    assert call.args[1] == PYIMOUAPI_SNAPSHOT_WAIT_SECONDS


@pytest.mark.parametrize(
    "camera_key",
    ["camera_sd", "camera_hd"],
)
@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        pytest.param(
            [
                create_online_device(
                    "d1",
                    "Device 1",
                    channel_id="1",
                    button_keys=(),
                )
            ],
            id="no_detect_switches",
        ),
        pytest.param(
            [
                create_online_device(
                    "d1",
                    "Device 1",
                    channel_id="1",
                    button_keys=(),
                    switches={
                        PARAM_HEADER_DETECT: {PARAM_STATE: True},
                        PARAM_MOTION_DETECT: {PARAM_STATE: False},
                    },
                )
            ],
            id="header_detect_on",
        ),
        pytest.param(
            [
                create_online_device(
                    "d1",
                    "Device 1",
                    channel_id="1",
                    button_keys=(),
                    switches={
                        PARAM_HEADER_DETECT: {PARAM_STATE: False},
                        PARAM_MOTION_DETECT: {PARAM_STATE: True},
                    },
                )
            ],
            id="motion_detect_on",
        ),
        pytest.param(
            [
                create_online_device(
                    "d1",
                    "Device 1",
                    channel_id="1",
                    button_keys=(),
                    switches={
                        PARAM_HEADER_DETECT: {PARAM_STATE: True},
                        PARAM_MOTION_DETECT: {PARAM_STATE: True},
                    },
                )
            ],
            id="both_detect_on",
        ),
    ],
    indirect=True,
)
@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default",
    "mock_camera_access_token",
    "init_integration",
)
async def test_camera_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    camera_key: str,
) -> None:
    """Snapshot full camera state for motion detection switch combinations."""
    entity_id = _camera_entity_id(
        entity_registry, mock_config_entry, camera_key=camera_key
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state == snapshot


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "d1",
                "Device 1",
                channel_id="1",
                button_keys=(),
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_camera_stream_source_propagates_api_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Imou API errors from stream fetch surface to the caller."""
    init_integration.async_get_device_stream.side_effect = ImouException(
        "stream failure"
    )

    entity_id = _camera_entity_id(entity_registry, mock_config_entry)
    with pytest.raises(HomeAssistantError, match="stream failure"):
        await async_get_stream_source(hass, entity_id)


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "d1",
                "Device 1",
                channel_id="1",
                button_keys=(),
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_camera_entities_removed_when_device_leaves_account(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Camera entities are removed when the device is no longer on the account."""
    camera_entries = [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.domain == "camera"
    ]
    assert {entry.unique_id for entry in camera_entries} == {
        "d1_1$camera_sd",
        "d1_1$camera_hd",
    }
    for camera_entry in camera_entries:
        assert hass.states.get(camera_entry.entity_id).state != STATE_UNAVAILABLE

    mock_imou_ha_device_manager.async_get_devices.return_value = []

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == []
    )
    for camera_entry in camera_entries:
        assert hass.states.get(camera_entry.entity_id) is None
