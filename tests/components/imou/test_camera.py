"""Tests for Imou camera platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyimouapi.const import (
    PARAM_HD,
    PARAM_MOTION_DETECT,
    PARAM_STATE,
    PARAM_STORAGE_USED,
)
from pyimouapi.exceptions import ImouException
import pytest

from homeassistant.components.camera import async_get_image, async_get_stream_source
from homeassistant.components.imou.camera import (
    PYIMOUAPI_LIVE_PROTOCOL,
    PYIMOUAPI_SNAPSHOT_WAIT_SECONDS,
)
from homeassistant.components.imou.const import (
    CONF_OPTION_LIVE_RESOLUTION,
    DEFAULT_LIVE_RESOLUTION,
    PARAM_HEADER_DETECT,
)
from homeassistant.components.imou.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import create_online_device

from tests.common import MockConfigEntry, async_fire_time_changed

TEST_STREAM_URL = "https://example.com/live.m3u8"
TEST_IMAGE_BYTES = b"fake-image-bytes"


def _camera_entity_id(
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    *,
    device_key: str = "d1_1",
) -> str:
    """Return the entity id for a channel camera."""
    entry = next(
        registry_entry
        for registry_entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if registry_entry.unique_id == f"{device_key}$camera"
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
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_camera_entity_registered_for_channel_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Channel devices register a live view camera entity."""
    entry = next(
        registry_entry
        for registry_entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if registry_entry.unique_id == "d1_1$camera"
    )
    assert entry.domain == "camera"
    assert entry.translation_key == "camera"
    assert hass.states.get(entry.entity_id) is not None


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
) -> None:
    """Fetching stream source calls the vendor library with pyimouapi defaults."""
    init_integration.async_get_device_stream.return_value = TEST_STREAM_URL

    entity_id = _camera_entity_id(entity_registry, mock_config_entry)
    stream_source = await async_get_stream_source(hass, entity_id)

    assert stream_source == TEST_STREAM_URL
    init_integration.async_get_device_stream.assert_awaited_once()
    call = init_integration.async_get_device_stream.await_args
    assert call is not None
    assert call.args[1] == DEFAULT_LIVE_RESOLUTION
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
async def test_camera_stream_source_uses_live_resolution_option(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Stream source honors the live resolution config entry option."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_OPTION_LIVE_RESOLUTION: PARAM_HD},
    )
    init_integration.async_get_device_stream.return_value = TEST_STREAM_URL

    entity_id = _camera_entity_id(entity_registry, mock_config_entry)
    await async_get_stream_source(hass, entity_id)

    call = init_integration.async_get_device_stream.await_args
    assert call is not None
    assert call.args[1] == PARAM_HD
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
    "imou_mock_devices",
    [
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
                sensors={PARAM_STORAGE_USED: {PARAM_STATE: "10"}},
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_camera_motion_detection_state_attribute(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Camera exposes motion detection in state when a detect switch is on."""
    entity_id = _camera_entity_id(entity_registry, mock_config_entry)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["motion_detection"] is True


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
    camera_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.unique_id == "d1_1$camera"
    )
    assert hass.states.get(camera_entry.entity_id).state != STATE_UNAVAILABLE

    mock_imou_ha_device_manager.async_get_devices.return_value = []

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == []
    )
    assert hass.states.get(camera_entry.entity_id) is None
