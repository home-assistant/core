"""Test the Hikvision image settings of the cameras attached to an NVR."""

import asyncio
from datetime import timedelta
import logging
import threading
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyhik.constants import NVR_DEVICE
from pyhik.image import (
    ImageChannelInfo,
    ImageSetting,
    ImageWriteResult,
    parse_image_capabilities,
)
from pyhik.isapi import (
    ISAPIAuthError,
    ISAPIConnectionError,
    ISAPIError,
    ISAPINotSupportedError,
    RawResponse,
)
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    async_load_fixture,
)
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.hikvision import IMAGE_SETTINGS_RETRY_INTERVAL
from homeassistant.components.hikvision.const import (
    CONF_RECORDER,
    DOMAIN,
    EVENT_IMAGE_SETTING_CHANGED,
)
from homeassistant.components.hikvision.coordinator import (
    NVR_SCAN_INTERVAL,
    SCAN_INTERVAL,
)
from homeassistant.components.hikvision.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import TEST_DEVICE_ID

HLC_1 = "switch.front_camera_channel_1_highlight_compensation"
HLC_2 = "switch.front_camera_channel_2_highlight_compensation"
SMART_LIGHT_2 = "switch.front_camera_channel_2_smart_supplement_light"

IMAGE_CHANNELS = [
    ImageChannelInfo(1, True, 1),
    ImageChannelInfo(2, True, 2),
    # Listed by the NVR, but nothing is connected.
    ImageChannelInfo(3, False, None),
]
PROXY_ERROR = ISAPIError("Request failed with status 503", 503, "serviceUnavailable")


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to load during test."""
    return [Platform.SWITCH]


@pytest.fixture
def amount_of_channels() -> int:
    """Return the amount of video channels of the NVR."""
    return 2


@pytest.fixture
async def settings(hass: HomeAssistant) -> list[ImageSetting]:
    """Return the image settings of an attached camera."""
    return parse_image_capabilities(
        await async_load_fixture(hass, "image_capabilities.xml", DOMAIN),
        await async_load_fixture(hass, "image_values.xml", DOMAIN),
    )


@pytest.fixture
def mock_nvr_image_settings(
    mock_isapi_client: MagicMock,
    settings: list[ImageSetting],
    image_values: dict[str, str],
) -> MagicMock:
    """Make the mocked client list and read the cameras attached to an NVR."""
    client = mock_isapi_client.return_value
    client.get_image_channels.side_effect = None
    client.get_image_channels.return_value = IMAGE_CHANNELS
    client.get_image_settings.side_effect = lambda channel=1, proxy=False: settings
    client.get_image_values.side_effect = lambda channel=1, proxy=False: dict(
        image_values
    )
    client.set_image_setting.return_value = ImageWriteResult(True, 200, "ok")
    client.set_image_linked_setting.return_value = ImageWriteResult(True, 200, "ok")
    return client


def warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return the warnings the integration logged."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "homeassistant.components.hikvision"
        and record.levelno == logging.WARNING
    ]


@pytest.mark.parametrize("platforms", [[Platform.SWITCH, Platform.BINARY_SENSOR]])
async def test_image_entities_share_the_device_of_the_channel_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    mock_hik_nvr: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the image entities of a channel are on the device the channel uses.

    The image channel ID is assumed to be the video channel the other entities
    of the channel are named after, so both must land on the same device.
    """
    mock_hik_nvr.return_value.current_event_states = {
        "Motion": [(False, 1), (False, 2)]
    }
    await setup_integration(hass, mock_config_entry)

    for channel, entity_id in ((1, HLC_1), (2, HLC_2)):
        image_entity = entity_registry.async_get(entity_id)
        others = [
            entity
            for entity in er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
            if entity.domain == "binary_sensor"
            and entity.unique_id.endswith(f"_{channel}")
        ]
        assert others
        assert {entity.device_id for entity in others} == {image_entity.device_id}


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_each_attached_camera_gets_its_own_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the cameras are read through the NVR and get a device each."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_nvr_image_settings.get_image_channels.assert_called_once_with(proxy=True)
    assert {
        call.args[0] for call in mock_nvr_image_settings.get_image_settings.mock_calls
    } == {1, 2}
    assert all(
        call.kwargs == {"proxy": True}
        for call in mock_nvr_image_settings.get_image_settings.mock_calls
    )
    assert hass.states.get(HLC_1).state == STATE_ON
    assert hass.states.get(HLC_2).state == STATE_ON

    # The entities are on the device of their channel, linked to the NVR, the
    # same device the camera and the binary sensors of the channel use.
    nvr = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_DEVICE_ID), mock_config_entry.entry_id
    )
    for channel, entity_id in ((1, HLC_1), (2, HLC_2)):
        entity = entity_registry.async_get(entity_id)
        assert entity.unique_id == (
            f"{TEST_DEVICE_ID}_{channel}_image_highlight_compensation"
        )
        device = device_registry.async_get(entity.device_id)
        assert device.identifiers == {(DOMAIN, f"{TEST_DEVICE_ID}_{channel}")}
        assert device.via_device_id == nvr.id
    # Nothing is connected to channel 3, so it gets no entities.
    assert not channel_entities(entity_registry, mock_config_entry, 3)


def channel_entities(
    entity_registry: er.EntityRegistry, entry: MockConfigEntry, channel: int
) -> list[str]:
    """Return the entities of a channel."""
    return [
        entity.entity_id
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if f"_{channel}_image_" in entity.unique_id
    ]


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_values_are_polled_for_each_camera(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
) -> None:
    """Test the values of every camera are read through the NVR."""
    await setup_integration(hass, mock_config_entry)

    assert {
        (call.args, tuple(call.kwargs.items()))
        for call in mock_nvr_image_settings.get_image_values.mock_calls
    } == {
        ((), (("channel", 1), ("proxy", True))),
        ((), (("channel", 2), ("proxy", True))),
    }


@pytest.mark.usefixtures("mock_hik_nvr")
@pytest.mark.parametrize(
    ("service", "value"), [(SERVICE_TURN_OFF, "false"), (SERVICE_TURN_ON, "true")]
)
async def test_changes_go_to_the_camera_through_the_nvr(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    image_values: dict[str, str],
    service: str,
    value: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a change is written to its own camera, and only there."""
    caplog.set_level(logging.DEBUG, "homeassistant.components.hikvision")
    await setup_integration(hass, mock_config_entry)
    mock_nvr_image_settings.get_image_values.side_effect = (
        lambda channel=1, proxy=False: {
            **image_values,
            "HLC/enabled": value,
        }
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: HLC_2}, blocking=True
    )

    mock_nvr_image_settings.set_image_setting.assert_called_once_with(
        "HLC/enabled", value, channel=2, proxy=True
    )
    assert hass.states.get(HLC_2).state == (STATE_ON if value == "true" else STATE_OFF)
    assert hass.states.get(HLC_1).state == STATE_ON
    # The log names the camera the change went to.
    assert (
        f"{mock_config_entry.title} channel 2: set HLC/enabled to {value}"
        in caplog.text
    )


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_other_settings_changed_to_make_room_are_logged_for_the_camera(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
) -> None:
    """Test the logbook entry links to the entity of the camera that was changed."""
    await setup_integration(hass, mock_config_entry)
    events = async_capture_events(hass, EVENT_IMAGE_SETTING_CHANGED)
    mock_nvr_image_settings.set_image_setting.return_value = ImageWriteResult(
        True, 200, "ok", {"HLC/enabled": "false"}
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: SMART_LIGHT_2}, blocking=True
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert [(e.data["name"], e.data.get("entity_id")) for e in events] == [
        ("Front Camera channel 2 Highlight compensation", HLC_2)
    ]
    # The entry is the camera's: the device of its channel.
    channel = device_registry.async_get(events[0].data["device_id"])
    assert (DOMAIN, f"{TEST_DEVICE_ID}_2") in channel.identifiers


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_camera_that_cannot_be_proxied_is_skipped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    settings: list[ImageSetting],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a camera the NVR lists but cannot proxy does not stop the others."""

    def get_image_settings(channel: int = 1, proxy: bool = False):
        if channel == 2:
            raise ISAPINotSupportedError("not supported", 503, "serviceUnavailable")
        return settings

    mock_nvr_image_settings.get_image_settings.side_effect = get_image_settings

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(HLC_1).state == STATE_ON
    assert hass.states.get(HLC_2) is None
    assert not warnings(caplog)


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_camera_that_fails_is_skipped_with_a_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    settings: list[ImageSetting],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an error on one camera is reported and does not stop the others."""

    def get_image_settings(channel: int = 1, proxy: bool = False):
        if channel == 2:
            raise ISAPIError("Request failed with status 500", 500)
        return settings

    mock_nvr_image_settings.get_image_settings.side_effect = get_image_settings

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(HLC_1).state == STATE_ON
    assert warnings(caplog) == [
        "Unable to read the image settings of channel 2 of 192.168.1.100: "
        "Request failed with status 500"
    ]


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_unreadable_values_of_one_camera_are_skipped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    image_values: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a first read of the values that fails only skips that camera."""

    def get_image_values(channel: int = 1, proxy: bool = False) -> dict[str, str]:
        if channel == 2:
            raise ISAPIError("timeout")
        return dict(image_values)

    mock_nvr_image_settings.get_image_values.side_effect = get_image_values

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(HLC_1).state == STATE_ON
    assert hass.states.get(HLC_2) is None
    assert warnings(caplog) == [
        "Unable to read the image values of channel 2 of 192.168.1.100: "
        "Unable to read the image settings"
    ]


@pytest.mark.usefixtures("mock_hik_nvr")
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(ISAPINotSupportedError("not supported", 404), [], id="not_found"),
        pytest.param(
            ISAPIAuthError("Insufficient permissions", 403),
            [
                "Not allowed to read the image settings of 192.168.1.100: "
                "Insufficient permissions"
            ],
            id="not_allowed",
        ),
        pytest.param(
            PROXY_ERROR,
            [
                "Unable to read the image settings of 192.168.1.100: "
                "Request failed with status 503"
            ],
            id="error",
        ),
    ],
)
async def test_nvr_without_readable_image_channels_still_loads(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    caplog: pytest.LogCaptureFixture,
    error: ISAPIError,
    expected: list[str],
) -> None:
    """Test failing to list the cameras never stops the NVR loading."""
    mock_nvr_image_settings.get_image_channels.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not mock_config_entry.runtime_data.image_coordinators
    mock_nvr_image_settings.close.assert_called_once()
    assert warnings(caplog) == expected


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_rejected_password_while_reading_an_attached_camera_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
) -> None:
    """Test a rejected password on the first read asks for new credentials."""
    mock_nvr_image_settings.get_image_values.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_nvr_image_settings.close.assert_called_once()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.parametrize("failing", ["get_image_channels", "get_image_settings"])
async def test_rejected_password_while_discovering_the_cameras_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
    mock_nvr_image_settings: MagicMock,
    failing: str,
) -> None:
    """Test a rejected password on the discovery asks for new credentials."""
    getattr(mock_nvr_image_settings, failing).side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_nvr_image_settings.close.assert_called_once()
    # The event stream would otherwise keep trying the rejected password.
    mock_hik_nvr.return_value.disconnect.assert_called()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.usefixtures("mock_hik_nvr")
@pytest.mark.parametrize("failing", ["get_image_channels", "get_image_values"])
async def test_attached_cameras_are_tried_again_after_a_connection_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    failing: str,
) -> None:
    """Test an NVR that was busy gets the image entities without a manual reload."""
    working = getattr(mock_nvr_image_settings, failing).side_effect
    getattr(mock_nvr_image_settings, failing).side_effect = ISAPIConnectionError(
        "Timeout"
    )

    await setup_integration(hass, mock_config_entry)
    assert not mock_config_entry.runtime_data.image_coordinators

    getattr(mock_nvr_image_settings, failing).side_effect = working
    freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(HLC_1).state == STATE_ON
    assert hass.states.get(HLC_2).state == STATE_ON


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_one_camera_that_stays_out_of_reach_does_not_reload_the_entry(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_nvr_image_settings: MagicMock,
    image_values: dict[str, str],
) -> None:
    """Test the cameras that work are not interrupted by the one that does not."""
    offline = True

    def get_image_values(channel: int = 1, proxy: bool = False) -> dict[str, str]:
        if channel == 2 and offline:
            raise ISAPIConnectionError("Timeout")
        return dict(image_values)

    mock_nvr_image_settings.get_image_values.side_effect = get_image_values
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(HLC_1).state == STATE_ON
    assert hass.states.get(HLC_2) is None

    for _ in range(3):
        freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    # Only the camera that failed was asked again, and the entry was not reloaded.
    assert mock_hikcamera.call_count == 1
    mock_hikcamera.return_value.disconnect.assert_not_called()
    assert mock_nvr_image_settings.get_image_channels.call_count == 1
    assert hass.states.get(HLC_1).state == STATE_ON

    offline = False
    freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_hikcamera.call_count == 2
    assert hass.states.get(HLC_2).state == STATE_ON


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_the_list_of_cameras_is_tried_again_after_a_connection_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_nvr_image_settings: MagicMock,
) -> None:
    """Test an NVR that was busy is read again, without reloading the entry."""
    working = mock_nvr_image_settings.get_image_channels.return_value
    mock_nvr_image_settings.get_image_channels.return_value = None
    mock_nvr_image_settings.get_image_channels.side_effect = ISAPIConnectionError(
        "Timeout"
    )
    await setup_integration(hass, mock_config_entry)

    freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_hikcamera.call_count == 1

    mock_nvr_image_settings.get_image_channels.side_effect = None
    mock_nvr_image_settings.get_image_channels.return_value = working
    freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_hikcamera.call_count == 2
    assert hass.states.get(HLC_1).state == STATE_ON
    # A device that says it is an NVR needs no record of it.
    assert CONF_RECORDER not in mock_config_entry.data


async def test_a_recorder_that_reports_a_camera_type_is_tried_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_nvr_image_settings: MagicMock,
    settings: list[ImageSetting],
) -> None:
    """Test a timeout listing the cameras is retried when the type says camera."""
    assert mock_hikcamera.return_value.get_type == "Camera"

    def get_image_settings(channel: int = 1, proxy: bool = False):
        if not proxy:
            raise PROXY_ERROR
        return settings

    working = mock_nvr_image_settings.get_image_channels.return_value
    mock_nvr_image_settings.get_image_settings.side_effect = get_image_settings
    mock_nvr_image_settings.get_image_channels.return_value = None
    mock_nvr_image_settings.get_image_channels.side_effect = ISAPIConnectionError(
        "Timeout"
    )
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(HLC_1) is None

    mock_nvr_image_settings.get_image_channels.side_effect = None
    mock_nvr_image_settings.get_image_channels.return_value = working
    freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # One reload, set up as an NVR at once.
    assert mock_hikcamera.call_count == 2
    assert mock_config_entry.data[CONF_RECORDER] is True
    assert hass.states.get(HLC_1).state == STATE_ON


async def test_a_recorder_found_as_the_settings_change_is_not_recorded(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_nvr_image_settings: MagicMock,
    settings: list[ImageSetting],
) -> None:
    """Test the retry records nothing about a device it may no longer talk to.

    The connection settings changed while it listed the cameras.
    """

    def get_image_settings(channel: int = 1, proxy: bool = False):
        if not proxy:
            raise PROXY_ERROR
        return settings

    working = mock_nvr_image_settings.get_image_channels.return_value
    mock_nvr_image_settings.get_image_settings.side_effect = get_image_settings
    mock_nvr_image_settings.get_image_channels.return_value = None
    mock_nvr_image_settings.get_image_channels.side_effect = ISAPIConnectionError(
        "Timeout"
    )
    await setup_integration(hass, mock_config_entry)

    def get_image_channels(*args: Any, **kwargs: Any) -> list[ImageChannelInfo]:
        hass.loop.call_soon_threadsafe(
            lambda: hass.config_entries.async_update_entry(
                mock_config_entry,
                data={**mock_config_entry.data, CONF_HOST: "192.168.1.200"},
            )
        )
        return working

    mock_nvr_image_settings.get_image_channels.side_effect = get_image_channels
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert CONF_RECORDER not in mock_config_entry.data
    reload.assert_not_called()


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_cameras_that_fail_together_are_tried_again_by_one_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
) -> None:
    """Test each camera that fails does not start a retry of its own."""
    mock_nvr_image_settings.get_image_settings.side_effect = ISAPIConnectionError(
        "Timeout"
    )
    with patch(
        "homeassistant.components.hikvision.async_track_time_interval",
        return_value=lambda: None,
    ) as track:
        await setup_integration(hass, mock_config_entry)

    assert track.call_count == 1


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_an_nvr_that_lists_no_camera_on_a_retry_is_set_up_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
) -> None:
    """Test the list of an NVR that answers at last is read, even with no camera.

    Its cameras may be connected later: the reload reads the list once more.
    """
    mock_nvr_image_settings.get_image_channels.side_effect = ISAPIConnectionError(
        "Timeout"
    )
    await setup_integration(hass, mock_config_entry)

    mock_nvr_image_settings.get_image_channels.side_effect = None
    mock_nvr_image_settings.get_image_channels.return_value = [
        ImageChannelInfo(1, False, None)
    ]
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    reload.assert_called_once_with(mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_a_camera_that_is_still_busy_on_a_retry_is_not_set_up_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    settings: list[ImageSetting],
) -> None:
    """Test the entry is reloaded only once the camera gives its settings."""

    def get_image_settings(channel: int = 1, proxy: bool = False):
        if channel == 2:
            raise PROXY_ERROR
        return settings

    mock_nvr_image_settings.get_image_settings.side_effect = get_image_settings
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(HLC_2) is None

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        reload.assert_not_called()

        mock_nvr_image_settings.get_image_settings.side_effect = (
            lambda channel=1, proxy=False: settings
        )
        freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    reload.assert_called_once_with(mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_a_camera_that_refuses_the_read_does_not_stop_the_others(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    settings: list[ImageSetting],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a camera the user may not read is not taken for a rejected password."""

    def get_image_settings(channel: int = 1, proxy: bool = False):
        if channel == 1:
            raise ISAPIAuthError("Insufficient permissions", 403)
        return settings

    mock_nvr_image_settings.get_image_settings.side_effect = get_image_settings
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(HLC_1) is None
    assert hass.states.get(HLC_2).state == STATE_ON
    assert not hass.config_entries.flow.async_progress()
    assert warnings(caplog) == [
        "Unable to read the image settings of channel 1 of 192.168.1.100: "
        "Insufficient permissions"
    ]


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_no_camera_sends_the_password_again_once_it_was_rejected(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    image_values: dict[str, str],
) -> None:
    """Test the cameras of an NVR share the login, so all of them stop together."""
    await setup_integration(hass, mock_config_entry)

    def get_image_values(channel: int = 1, proxy: bool = False) -> dict[str, str]:
        if channel == 1:
            raise ISAPIAuthError("Invalid credentials", 401)
        return dict(image_values)

    mock_nvr_image_settings.get_image_values.side_effect = get_image_values
    mock_nvr_image_settings.get_image_values.reset_mock()
    freezer.tick(NVR_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert hass.states.get(HLC_1).state == STATE_UNAVAILABLE
    assert hass.states.get(HLC_2).state == STATE_UNAVAILABLE

    # Nothing is sent with the rejected password until the new one is entered, not
    # by a write that was already waiting either.
    mock_nvr_image_settings.get_image_values.reset_mock()
    coordinator = mock_config_entry.runtime_data.image_coordinators[1]
    with pytest.raises(HomeAssistantError, match="rejected the username or password"):
        await coordinator.async_set_setting("HLC/enabled", "false")
    freezer.tick(NVR_SCAN_INTERVAL * 3)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_nvr_image_settings.get_image_values.assert_not_called()
    mock_nvr_image_settings.set_image_setting.assert_not_called()


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_a_write_rejected_on_one_camera_stops_the_others(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
) -> None:
    """Test a 401 on a write stops the polling of every camera of the NVR."""
    await setup_integration(hass, mock_config_entry)
    mock_nvr_image_settings.set_image_setting.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )

    with pytest.raises(HomeAssistantError, match="rejected the username or password"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: HLC_2}, blocking=True
        )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(hass.config_entries.flow.async_progress()) == 1
    assert hass.states.get(HLC_1).state == STATE_UNAVAILABLE
    assert hass.states.get(HLC_2).state == STATE_UNAVAILABLE
    mock_nvr_image_settings.get_image_values.reset_mock()
    freezer.tick(NVR_SCAN_INTERVAL * 3)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_nvr_image_settings.get_image_values.assert_not_called()


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_a_poll_rejected_on_one_camera_stops_the_others(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    image_values: dict[str, str],
) -> None:
    """Test a 401 on one camera's poll makes every camera of the NVR unavailable.

    They share the login: none of them can be reached with it now. The first
    camera's poll, just before, worked.
    """
    await setup_integration(hass, mock_config_entry)

    def get_image_values(channel: int = 1, proxy: bool = False) -> dict[str, str]:
        if channel == 2:
            raise ISAPIAuthError("Invalid credentials", 401)
        return dict(image_values)

    mock_nvr_image_settings.get_image_values.side_effect = get_image_values
    freezer.tick(NVR_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(HLC_1).state == STATE_UNAVAILABLE
    assert hass.states.get(HLC_2).state == STATE_UNAVAILABLE
    assert len(hass.config_entries.flow.async_progress()) == 1


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_the_cameras_of_an_nvr_are_polled_slowly(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
) -> None:
    """Test the cameras share one client, so they are not all read every 30 seconds."""
    await setup_integration(hass, mock_config_entry)
    mock_nvr_image_settings.get_image_values.reset_mock()

    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_nvr_image_settings.get_image_values.assert_not_called()

    freezer.tick(NVR_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_nvr_image_settings.get_image_values.call_count == 2


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_a_camera_that_does_not_allow_the_values_is_not_tried_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    image_values: dict[str, str],
) -> None:
    """Test a refusal is not retried by reloading the entry, which stops the events."""

    def get_image_values(channel: int = 1, proxy: bool = False) -> dict[str, str]:
        if channel == 2:
            raise ISAPIAuthError("Forbidden", 403)
        return dict(image_values)

    mock_nvr_image_settings.get_image_values.side_effect = get_image_values
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(HLC_1).state == STATE_ON
    mock_nvr_image_settings.get_image_channels.reset_mock()

    freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_nvr_image_settings.get_image_channels.assert_not_called()


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_no_reload_is_scheduled_once_the_password_was_rejected(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    image_values: dict[str, str],
) -> None:
    """Test a retry that was waiting does not reload the entry with the old password."""

    def get_image_values(channel: int = 1, proxy: bool = False) -> dict[str, str]:
        if channel == 2:
            raise ISAPIConnectionError("Timeout")
        return dict(image_values)

    mock_nvr_image_settings.get_image_values.side_effect = get_image_values
    await setup_integration(hass, mock_config_entry)
    # A camera that worked is rejected before the retry is due
    mock_config_entry.runtime_data.image_coordinators[0].credentials_rejected = True
    mock_nvr_image_settings.get_image_channels.reset_mock()

    freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_nvr_image_settings.get_image_channels.assert_not_called()


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_diagnostics_do_not_send_a_rejected_password_again(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
) -> None:
    """Test the raw documents are not requested once the device rejected the login."""
    await setup_integration(hass, mock_config_entry)
    mock_config_entry.runtime_data.image_coordinators[0].credentials_rejected = True

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    mock_nvr_image_settings.request_raw.assert_not_called()
    for channel in ("1", "2"):
        assert result["channel_image_settings"][channel]["raw_documents"] == {
            "capabilities": "error: credentials rejected",
            "values": "error: credentials rejected",
        }


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_an_unload_during_a_download_stops_the_cameras_not_read_yet(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
) -> None:
    """Test a download the entry unloads under asks the next camera for nothing.

    Each camera refuses a request once its entry unloads, and the client is closed
    after the request that was running.
    """
    await setup_integration(hass, mock_config_entry)
    started = threading.Event()
    finish = threading.Event()

    def _slow_read(method: str, endpoint: str) -> RawResponse:
        started.set()
        finish.wait(5)
        return RawResponse(200, b"<ImageChannel/>")

    mock_nvr_image_settings.request_raw.side_effect = _slow_read
    download = hass.async_create_task(
        async_get_config_entry_diagnostics(hass, mock_config_entry)
    )
    await hass.async_add_executor_job(started.wait, 5)
    unload = hass.async_create_task(
        hass.config_entries.async_unload(mock_config_entry.entry_id)
    )
    for _ in range(10):
        await asyncio.sleep(0)
    finish.set()
    result = await download
    assert await unload

    channel_2 = "/ISAPI/ContentMgmt/ImageProxy/channels/2"
    assert not [
        call
        for call in mock_nvr_image_settings.request_raw.call_args_list
        if call.args[1].startswith(channel_2)
    ]
    assert result["channel_image_settings"]["2"]["raw_documents"] == {
        "capabilities": "error: the image settings client is closing",
        "values": "error: the image settings client is closing",
    }
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_nvr_image_settings.close.assert_called_once()


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_the_client_is_shared_and_closed_once_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    mock_isapi_client: MagicMock,
) -> None:
    """Test all the cameras of an NVR use one client, which unloading closes."""
    await setup_integration(hass, mock_config_entry)
    mock_isapi_client.assert_called_once()
    assert len(mock_config_entry.runtime_data.image_coordinators) == 2
    mock_nvr_image_settings.close.assert_not_called()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    mock_nvr_image_settings.close.assert_called_once()


@pytest.mark.parametrize("platforms", [[Platform.SWITCH, Platform.BINARY_SENSOR]])
async def test_recorder_that_reports_a_camera_type_is_set_up_as_an_nvr(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_hik_get_channels: MagicMock,
    mock_nvr_image_settings: MagicMock,
    settings: list[ImageSetting],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an NVR that reports itself as a camera is found by its errors.

    It is recorded as a recorder, and set up again as an NVR: its events and its
    video go on the device of each camera, as its image settings do.
    """
    camera = mock_hikcamera.return_value
    assert camera.get_type == "Camera"
    camera.current_event_states = {"Motion": [(False, 1), (False, 2)]}

    def get_image_settings(channel: int = 1, proxy: bool = False):
        if not proxy:
            raise ISAPIError(
                "Request failed with status 503", 503, "serviceUnavailable"
            )
        return settings

    mock_nvr_image_settings.get_image_settings.side_effect = get_image_settings

    with caplog.at_level(logging.INFO):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_RECORDER] is True
    assert "reports the type of a camera but is a recorder" in caplog.text
    data = mock_config_entry.runtime_data
    assert data.is_nvr
    # The video of each camera is asked for by its channel.
    assert camera.device_type == NVR_DEVICE
    assert [c.channel for c in data.image_coordinators] == [1, 2]
    # The second setup reads the channels as for an NVR.
    mock_hik_get_channels.assert_called_once()
    # The first, as a camera, did not look for the camera's detections: it is set
    # up again at once. Only the channels' are asked for.
    asked = mock_nvr_image_settings.get_detection_enabled.call_args_list
    assert sorted(call.args[1] for call in asked) == [1] * 8 + [2] * 8
    entity = entity_registry.async_get(HLC_1)
    assert entity.unique_id == f"{TEST_DEVICE_ID}_1_image_highlight_compensation"
    device = device_registry.async_get(entity.device_id)
    assert device.identifiers == {(DOMAIN, f"{TEST_DEVICE_ID}_1")}
    # The events of the camera are on its device too.
    motion = [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.domain == "binary_sensor" and entry.unique_id.endswith("_1")
    ]
    assert motion
    assert {entry.device_id for entry in motion} == {device.id}
    assert not warnings(caplog)


async def test_a_recorded_recorder_is_set_up_as_an_nvr_at_once(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_hik_get_channels: MagicMock,
    mock_nvr_image_settings: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a device known to be a recorder is not read as a camera first."""
    assert mock_hikcamera.return_value.get_type == "Camera"
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_RECORDER: True}
    )

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as mock_schedule_reload:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_schedule_reload.assert_not_called()
    assert mock_config_entry.runtime_data.is_nvr
    assert mock_hikcamera.return_value.device_type == NVR_DEVICE
    # Its events are read as for an NVR, though it reports some as a camera.
    mock_hikcamera.return_value.get_event_triggers.assert_called_once()
    mock_hik_get_channels.assert_called_once()
    for call in mock_nvr_image_settings.get_image_settings.call_args_list:
        assert call.kwargs["proxy"] is True
    assert [c.channel for c in mock_config_entry.runtime_data.image_coordinators] == [
        1,
        2,
    ]


@pytest.mark.usefixtures("mock_hikcamera")
async def test_camera_is_read_directly_before_the_nvr_endpoints_are_tried(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a camera that works never goes through the NVR endpoints."""
    await setup_integration(hass, mock_config_entry)

    mock_image_settings.get_image_channels.assert_not_called()
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    assert coordinator.channel is None


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ISAPIAuthError("Invalid credentials", 401), id="not_allowed"),
        pytest.param(ISAPIConnectionError("Timeout"), id="unreachable"),
    ],
)
async def test_nvr_endpoints_are_not_tried_after_an_auth_or_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    error: ISAPIError,
) -> None:
    """Test other endpoints are not tried when they would fail the same way."""
    mock_isapi_client.return_value.get_image_settings.side_effect = error

    await setup_integration(hass, mock_config_entry)

    mock_isapi_client.return_value.get_image_channels.assert_not_called()


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ISAPINotSupportedError("not supported", 404), id="not_found"),
        pytest.param(PROXY_ERROR, id="error"),
    ],
)
async def test_camera_without_image_settings_tries_the_nvr_endpoints_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    error: ISAPIError,
) -> None:
    """Test a failing camera is probed once, and still loads without entities."""
    mock_isapi_client.return_value.get_image_settings.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not mock_config_entry.runtime_data.image_coordinators
    mock_isapi_client.return_value.get_image_channels.assert_called_once_with(
        proxy=True
    )


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_diagnostics_report_every_attached_camera(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
) -> None:
    """Test the diagnostics hold the settings and documents of each camera."""
    mock_nvr_image_settings.request_raw.side_effect = lambda method, endpoint: (
        RawResponse(200, f"<{endpoint}/>".encode())
    )
    await setup_integration(hass, mock_config_entry)
    mock_nvr_image_settings.get_image_values.reset_mock()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["image_settings"] is None
    assert set(result["channel_image_settings"]) == {"1", "2"}
    # The current values are read through the NVR, as a poll reads them.
    assert sorted(
        call.kwargs["channel"]
        for call in mock_nvr_image_settings.get_image_values.call_args_list
        if call.kwargs["proxy"]
    ) == [1, 2]
    for channel in ("1", "2"):
        camera = result["channel_image_settings"][channel]
        assert camera["values_source"] == "camera"
        assert camera["settings"]["HLC/enabled"]["value"] == "true"
        proxy = f"/ISAPI/ContentMgmt/ImageProxy/channels/{channel}"
        assert camera["raw_documents"] == {
            "capabilities": f"<{proxy}/capabilities/>",
            "values": f"<{proxy}/>",
        }


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_discovery_requests_take_their_turn_on_the_shared_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    settings: list[ImageSetting],
) -> None:
    """Test each camera is read under the lock its coordinators already use.

    The cameras found so far can be reached, by the diagnostics for one, while
    the next ones are read.
    """
    locked: list[bool] = []

    def get_image_settings(channel: int = 1, proxy: bool = False):
        coordinators = mock_config_entry.runtime_data.image_coordinators
        if coordinators:
            locked.append(coordinators[0].lock.locked())
        return settings

    mock_nvr_image_settings.get_image_settings.side_effect = get_image_settings

    await setup_integration(hass, mock_config_entry)

    assert locked == [True]
    assert len(mock_config_entry.runtime_data.image_coordinators) == 2


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_a_request_waiting_on_a_rejected_discovery_is_not_sent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    settings: list[ImageSetting],
) -> None:
    """Test a diagnostics download queued behind a read that got a 401 sends nothing.

    It is next on the shared client, before the client is closed.
    """
    downloads: list[asyncio.Task] = []

    def get_image_settings(channel: int = 1, proxy: bool = False):
        if channel == 1:
            return settings
        # A download of the first camera's diagnostics now waits for this read.
        hass.loop.call_soon_threadsafe(
            lambda: downloads.append(
                hass.async_create_task(
                    async_get_config_entry_diagnostics(hass, mock_config_entry)
                )
            )
        )
        for _ in range(20):
            asyncio.run_coroutine_threadsafe(asyncio.sleep(0), hass.loop).result()
        raise ISAPIAuthError("Invalid credentials", 401)

    mock_nvr_image_settings.get_image_settings.side_effect = get_image_settings
    await setup_integration(hass, mock_config_entry)
    [download] = downloads
    await download

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    # Only the first refresh of the first camera read its values.
    assert mock_nvr_image_settings.get_image_values.call_count == 1
    mock_nvr_image_settings.request_raw.assert_not_called()


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_discovery_stops_once_another_request_got_the_password_rejected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    image_values: dict[str, str],
) -> None:
    """Test the next camera is not read with a password a request got rejected.

    Here the first camera's coordinator gets the 401, as a diagnostics download
    would while the second camera waits to be read.
    """

    def get_image_values(channel: int = 1, proxy: bool = False):
        # The read is done; the rejection comes from another request.
        mock_config_entry.runtime_data.image_coordinators[
            0
        ].shared.credentials_rejected = True
        return dict(image_values)

    mock_nvr_image_settings.get_image_values.side_effect = get_image_values

    await setup_integration(hass, mock_config_entry)

    assert [
        call.args[0]
        for call in mock_nvr_image_settings.get_image_settings.call_args_list
    ] == [1]
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.usefixtures("mock_hik_nvr")
async def test_a_failed_discovery_closes_the_client_once_a_request_ends(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nvr_image_settings: MagicMock,
    settings: list[ImageSetting],
) -> None:
    """Test the clean-up of a discovery does not close the client under a request.

    The first camera can be reached, by the diagnostics for one, while the second
    is read; the second then gets the password rejected.
    """
    release = asyncio.Event()
    holding = asyncio.Event()

    async def _hold_the_lock() -> None:
        # A request of the first camera, queued behind the discovery's own.
        [coordinator] = mock_config_entry.runtime_data.image_coordinators
        async with coordinator.lock:
            holding.set()
            await release.wait()

    def get_image_settings(channel: int = 1, proxy: bool = False):
        if channel == 1:
            return settings
        hass.loop.call_soon_threadsafe(hass.async_create_task, _hold_the_lock())
        raise ISAPIAuthError("Invalid credentials", 401)

    mock_nvr_image_settings.get_image_settings.side_effect = get_image_settings
    mock_config_entry.add_to_hass(hass)
    setup = hass.async_create_task(
        hass.config_entries.async_setup(mock_config_entry.entry_id)
    )
    try:
        async with asyncio.timeout(5):
            await holding.wait()
        for _ in range(10):
            await asyncio.sleep(0)
        mock_nvr_image_settings.close.assert_not_called()
    finally:
        release.set()
    assert await setup is False
    await hass.async_block_till_done()

    mock_nvr_image_settings.close.assert_called_once()
