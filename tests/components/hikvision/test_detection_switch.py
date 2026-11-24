"""Test the switches that turn the detections of a Hikvision camera on and off."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyhik.image import ImageChannelInfo, ImageWriteResult
from pyhik.isapi import (
    ISAPIAuthError,
    ISAPIConnectionError,
    ISAPIError,
    ISAPINotSupportedError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.hikvision.coordinator import (
    NVR_SCAN_INTERVAL,
    SCAN_INTERVAL,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import (
    ATTR_ENTITY_ID,
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

MOTION = "switch.front_camera_motion_detection"
LINE = "switch.front_camera_line_crossing_detection"
INTRUSION = "switch.front_camera_intrusion_detection"
TAMPERING = "switch.front_camera_video_tampering_detection"
SCENE_CHANGE = "switch.front_camera_scene_change_detection"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to load during test."""
    return [Platform.SWITCH]


async def _async_poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.usefixtures("mock_hikcamera", "mock_detections")
async def test_a_switch_for_each_detection_the_camera_has(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test each detection the camera has gets a switch, and the others none.

    The camera answers "not supported" for region entrance and exiting, and video
    loss.
    """
    await setup_integration(hass, mock_config_entry)

    states = {
        entity_id: hass.states.get(entity_id).state
        for entity_id in (MOTION, LINE, INTRUSION, TAMPERING, SCENE_CHANGE)
    }
    assert states == {
        MOTION: STATE_ON,
        LINE: STATE_ON,
        INTRUSION: STATE_ON,
        TAMPERING: STATE_OFF,
        SCENE_CHANGE: STATE_OFF,
    }
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    detections = {
        entry.unique_id: entry.entity_category
        for entry in entries
        if entry.unique_id.endswith("_detection")
    }
    assert detections == {
        # Controls, apart from the image settings.
        f"{TEST_DEVICE_ID}_{key}": None
        for key in (
            "motion_detection",
            "line_crossing_detection",
            "intrusion_detection",
            "video_tampering_detection",
            "scene_change_detection",
        )
    }
    entry = entity_registry.async_get(MOTION)
    assert entry is not None
    assert entry.disabled_by is None


@pytest.mark.usefixtures("mock_hikcamera", "mock_image_settings")
async def test_no_switch_without_detections(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a camera that has none of the detections gets no detection switch."""
    await setup_integration(hass, mock_config_entry)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert entries
    assert not any(entry.unique_id.endswith("_detection") for entry in entries)


@pytest.mark.usefixtures("mock_hikcamera", "mock_detections")
@pytest.mark.parametrize(
    ("service", "entity_id", "detection", "enabled", "state"),
    [
        (SERVICE_TURN_OFF, INTRUSION, "fieldDetection", False, STATE_OFF),
        (SERVICE_TURN_ON, SCENE_CHANGE, "sceneChangeDetection", True, STATE_ON),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    service: str,
    entity_id: str,
    detection: str,
    enabled: bool,
    state: str,
) -> None:
    """Test a switch turns its detection on or off, and shows it."""
    await setup_integration(hass, mock_config_entry)
    polls = mock_image_settings.get_image_values.call_count

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_image_settings.set_detection_enabled.assert_called_once_with(
        detection, enabled, channel=1
    )
    assert hass.states.get(entity_id).state == state
    # Read again after the change, as for an image setting.
    assert mock_image_settings.get_image_values.call_count == polls + 1


@pytest.mark.usefixtures("mock_hikcamera", "mock_detections")
async def test_follows_the_camera(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    detections: dict[str, bool],
) -> None:
    """Test a change made on the camera shows at the next poll."""
    await setup_integration(hass, mock_config_entry)

    detections["tamperDetection"] = True
    await _async_poll(hass, freezer)

    assert hass.states.get(TAMPERING).state == STATE_ON


@pytest.mark.usefixtures("mock_hikcamera", "mock_detections")
async def test_only_the_detections_the_camera_has_are_read_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a poll does not ask again for the detections the camera does not have."""
    await setup_integration(hass, mock_config_entry)
    asked = mock_image_settings.get_detection_enabled
    # The first poll asked for all of them.
    assert asked.call_count == 8
    asked.reset_mock()

    await _async_poll(hass, freezer)

    assert sorted(call.args[0] for call in asked.call_args_list) == sorted(
        [
            "motionDetection",
            "lineDetection",
            "fieldDetection",
            "tamperDetection",
            "sceneChangeDetection",
        ]
    )
    assert {call.args[1] for call in asked.call_args_list} == {1}


@pytest.mark.usefixtures("mock_hikcamera", "mock_detections")
@pytest.mark.parametrize(
    "error",
    [
        ISAPIError("Request failed with status 500", 500, "deviceError"),
        ISAPINotSupportedError("not supported", 403, "notSupport"),
        ISAPIAuthError("Insufficient permissions", 403, "lowPrivilege"),
    ],
)
async def test_unavailable_while_it_cannot_be_read(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    detections: dict[str, bool],
    error: ISAPIError,
) -> None:
    """Test a detection that cannot be read is unavailable, and the others are not.

    It comes back once it can be read again.
    """
    await setup_integration(hass, mock_config_entry)
    read = mock_image_settings.get_detection_enabled.side_effect

    def _read(detection: str, channel: int | str = 1) -> bool:
        if detection == "lineDetection":
            raise error
        return read(detection, channel)

    mock_image_settings.get_detection_enabled.side_effect = _read
    await _async_poll(hass, freezer)

    assert hass.states.get(LINE).state == STATE_UNAVAILABLE
    assert hass.states.get(MOTION).state == STATE_ON
    assert hass.states.get("switch.front_camera_highlight_compensation").state in (
        STATE_ON,
        "off",
    )

    mock_image_settings.get_detection_enabled.side_effect = read
    await _async_poll(hass, freezer)

    assert hass.states.get(LINE).state == STATE_ON


@pytest.mark.usefixtures("mock_hikcamera", "mock_detections")
async def test_kept_when_the_first_read_fails(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a detection that failed to answer the first poll still gets its switch.

    The camera has it: only "not supported" or a refusal leaves one out.
    """
    read = mock_image_settings.get_detection_enabled.side_effect
    failing = True

    def _read(detection: str, channel: int | str = 1) -> bool:
        if failing and detection == "fieldDetection":
            raise ISAPIError("Request failed with status 500", 500, "deviceError")
        return read(detection, channel)

    mock_image_settings.get_detection_enabled.side_effect = _read
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(INTRUSION).state == STATE_UNAVAILABLE

    failing = False
    await _async_poll(hass, freezer)

    assert hass.states.get(INTRUSION).state == STATE_ON


@pytest.mark.usefixtures("mock_hikcamera", "mock_detections")
async def test_not_allowed_is_left_out(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a detection the user may not read gets no switch, and is not a reauth."""
    read = mock_image_settings.get_detection_enabled.side_effect

    def _read(detection: str, channel: int | str = 1) -> bool:
        if detection == "motionDetection":
            raise ISAPIAuthError("Insufficient permissions", 403, "lowPrivilege")
        return read(detection, channel)

    mock_image_settings.get_detection_enabled.side_effect = _read
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(MOTION) is None
    assert hass.states.get(LINE).state == STATE_ON
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.usefixtures("mock_detections")
async def test_rejected_password_while_reading_starts_reauth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a 401 for a detection stops everything and asks for new credentials.

    The other detections are not asked with the rejected password.
    """
    await setup_integration(hass, mock_config_entry)
    asked: list[str] = []

    def _read(detection: str, channel: int | str = 1) -> bool:
        asked.append(detection)
        raise ISAPIAuthError("Invalid credentials", 401)

    mock_image_settings.get_detection_enabled.side_effect = _read
    await _async_poll(hass, freezer)

    assert asked == ["motionDetection"]
    mock_hikcamera.return_value.disconnect.assert_called_once()
    assert hass.states.get(MOTION).state == STATE_UNAVAILABLE
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


@pytest.mark.usefixtures("mock_hikcamera", "mock_detections")
async def test_refused_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a change the camera refuses is an error, and nothing changes."""
    await setup_integration(hass, mock_config_entry)
    mock_image_settings.set_detection_enabled.side_effect = None
    mock_image_settings.set_detection_enabled.return_value = ImageWriteResult(
        False, 400, "badParameters"
    )

    with pytest.raises(HomeAssistantError, match="badParameters"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: LINE}, blocking=True
        )

    assert hass.states.get(LINE).state == STATE_ON


@pytest.mark.usefixtures("mock_detections")
async def test_rejected_password_while_changing_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a 401 for a change stops everything and asks for new credentials."""
    await setup_integration(hass, mock_config_entry)
    mock_image_settings.set_detection_enabled.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )

    with pytest.raises(HomeAssistantError, match="rejected the username or password"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: TAMPERING}, blocking=True
        )
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_hikcamera.return_value.disconnect.assert_called_once()
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


@pytest.mark.usefixtures("mock_hik_nvr", "mock_detections")
@pytest.mark.parametrize("amount_of_channels", [2])
async def test_nvr_camera_detections(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the detections of an NVR's camera are read and set with its channel.

    The switches are on the device of the channel.
    """
    client = mock_image_settings
    settings = client.get_image_settings.return_value
    values = client.get_image_values.return_value
    client.get_image_channels.side_effect = None
    client.get_image_channels.return_value = [ImageChannelInfo(2, True, 2)]
    client.get_image_settings.side_effect = lambda channel=1, proxy=False: settings
    client.get_image_values.side_effect = lambda channel=1, proxy=False: dict(values)

    await setup_integration(hass, mock_config_entry)

    entity_id = "switch.front_camera_channel_2_intrusion_detection"
    assert hass.states.get(entity_id).state == STATE_ON
    assert {call.args[1] for call in client.get_detection_enabled.call_args_list} == {2}
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.unique_id == f"{TEST_DEVICE_ID}_2_intrusion_detection"
    device = device_registry.async_get(entry.device_id)
    assert device is not None
    assert (
        "hikvision",
        f"{TEST_DEVICE_ID}_2",
    ) in device.identifiers

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    client.set_detection_enabled.assert_called_once_with(
        "fieldDetection", False, channel=2
    )
    freezer.tick(NVR_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == STATE_OFF


def _have_detections(client: MagicMock, detections: dict[str, bool]) -> None:
    """Make the mocked device have the detections, without image settings."""

    def _get(detection: str, channel: int | str = 1) -> bool:
        if detection not in detections:
            raise ISAPINotSupportedError("not supported", 403, "notSupport")
        return detections[detection]

    client.get_detection_enabled.side_effect = _get


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_camera_without_image_settings_still_gets_its_detections(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    detections: dict[str, bool],
) -> None:
    """Test the detections do not need the image settings.

    No image values are read for a camera that has none, and its client stays open.
    """
    client = mock_isapi_client.return_value
    _have_detections(client, detections)

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(INTRUSION).state == STATE_ON
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    assert coordinator.settings == []
    client.get_image_values.assert_not_called()
    client.close.assert_not_called()


@pytest.mark.usefixtures("mock_hikcamera", "mock_detections")
async def test_detections_when_the_image_values_cannot_be_read(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a camera whose first image read fails keeps its detections.

    The image settings are read again later, as before.
    """
    mock_image_settings.get_image_values.side_effect = ISAPIError("busy", 503)

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(INTRUSION).state == STATE_ON
    assert hass.states.get("switch.front_camera_highlight_compensation") is None


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_camera_not_reached_gets_no_detection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
) -> None:
    """Test detections that cannot be reached at setup are not taken as there.

    The setup that follows the camera coming back finds them.
    """
    client = mock_isapi_client.return_value
    client.get_image_settings.side_effect = ISAPIConnectionError("timeout")
    client.get_detection_enabled.side_effect = ISAPIConnectionError("timeout")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.runtime_data.image_coordinators == []
    assert not hass.states.async_entity_ids(SWITCH_DOMAIN)
    client.close.assert_called_once()


@pytest.mark.usefixtures("mock_hik_nvr")
@pytest.mark.parametrize("amount_of_channels", [2])
@pytest.mark.parametrize(
    "listed",
    [
        # Listed, but the NVR cannot proxy its image settings.
        [ImageChannelInfo(1, True, 1), ImageChannelInfo(2, True, 2)],
        # Not listed at all: the video channels of the NVR are used.
        None,
    ],
)
async def test_nvr_cameras_without_image_settings_get_their_detections(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    detections: dict[str, bool],
    listed: list[ImageChannelInfo] | None,
) -> None:
    """Test each camera of an NVR gets its detections without image settings."""
    client = mock_isapi_client.return_value
    if listed is not None:
        client.get_image_channels.side_effect = None
        client.get_image_channels.return_value = listed
    _have_detections(client, detections)

    await setup_integration(hass, mock_config_entry)

    for channel in (1, 2):
        state = hass.states.get(
            f"switch.front_camera_channel_{channel}_intrusion_detection"
        )
        assert state is not None
        assert state.state == STATE_ON
    assert {call.args[1] for call in client.get_detection_enabled.call_args_list} == {
        1,
        2,
    }
