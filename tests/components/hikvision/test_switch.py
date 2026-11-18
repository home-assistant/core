"""Test Hikvision image setting switches."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyhik.image import ImageSetting, ImageSettingType, ImageWriteResult
from pyhik.isapi import ISAPIAuthError, ISAPIConnectionError, ISAPIError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hikvision.coordinator import SCAN_INTERVAL
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_LOGBOOK_ENTRY,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

HLC = "switch.front_camera_highlight_compensation"
SMART_LIGHT = "switch.front_camera_smart_supplement_light"
IMAGE_FLIP = "switch.front_camera_image_flip"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to load during test."""
    return [Platform.SWITCH]


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_hikcamera", "mock_image_settings"
)
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all switch entities of a camera."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_hikcamera", "mock_image_settings")
async def test_enabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that only the commonly used switches are enabled by default."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(HLC).state == STATE_ON
    assert hass.states.get(SMART_LIGHT).state == STATE_OFF
    assert hass.states.get(IMAGE_FLIP) is None
    assert (
        entity_registry.async_get(IMAGE_FLIP).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )


@pytest.mark.usefixtures("mock_hikcamera", "mock_image_settings")
async def test_unknown_settings_are_skipped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a switch without a description gets no entity."""
    await setup_integration(hass, mock_config_entry)

    # The camera reports corridor/enabled as a switch, but it is not exposed.
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert not any("corridor" in entry.unique_id for entry in entries)


@pytest.mark.usefixtures("mock_hikcamera")
async def test_path_is_matched_case_insensitively(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that firmware spelling a known path differently still gets an entity."""
    mock_image_settings.get_image_settings.return_value = [
        ImageSetting(path="hlc/enabled", type=ImageSettingType.SWITCH, value="false")
    ]
    mock_image_settings.get_image_values.return_value = {"hlc/enabled": "false"}

    await setup_integration(hass, mock_config_entry)

    entry = entity_registry.async_get(HLC)
    assert entry is not None
    # The spelling of the path does not change the unique ID, whatever the firmware.
    assert entry.unique_id.endswith("_image_hlc/enabled")
    # The camera's own spelling is what gets written.
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: HLC}, blocking=True
    )
    mock_image_settings.set_image_setting.assert_called_once_with("hlc/enabled", "true")


@pytest.mark.usefixtures("mock_hikcamera")
async def test_backlight_compensation_without_a_mode_is_a_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a camera that has the BLC flag and no mode to fold it into can set it."""
    mock_image_settings.get_image_settings.return_value = [
        ImageSetting(path="BLC/enabled", type=ImageSettingType.SWITCH, value="true")
    ]
    mock_image_settings.get_image_values.return_value = {"BLC/enabled": "true"}

    await setup_integration(hass, mock_config_entry)

    entity_id = "switch.front_camera_backlight_compensation"
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None

    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    mock_image_settings.set_image_setting.assert_called_once_with(
        "BLC/enabled", "false"
    )


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("service", "expected_value"),
    [(SERVICE_TURN_OFF, "false"), (SERVICE_TURN_ON, "true")],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    image_values: dict[str, str],
    service: str,
    expected_value: str,
) -> None:
    """Test changing a switch writes the setting to the camera."""
    await setup_integration(hass, mock_config_entry)
    mock_image_settings.get_image_values.return_value = {
        **image_values,
        "HLC/enabled": expected_value,
    }

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: HLC}, blocking=True
    )

    mock_image_settings.set_image_setting.assert_called_once_with(
        "HLC/enabled", expected_value
    )
    assert hass.states.get(HLC).state == (
        STATE_ON if expected_value == "true" else STATE_OFF
    )


@pytest.mark.usefixtures("mock_hikcamera")
async def test_other_settings_changed_to_make_room_are_logged(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    image_values: dict[str, str],
) -> None:
    """Test the user is told when the camera had to switch another setting off."""
    await setup_integration(hass, mock_config_entry)
    events = async_capture_events(hass, EVENT_LOGBOOK_ENTRY)
    mock_image_settings.set_image_setting.return_value = ImageWriteResult(
        True, 200, "ok", {"HLC/enabled": "false", "WDR/mode": "CLOSE"}
    )
    mock_image_settings.get_image_values.return_value = {
        **image_values,
        "HLC/enabled": "false",
        "Exposure/OverexposeSuppress/enabled": "true",
    }

    context = Context()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SMART_LIGHT},
        blocking=True,
        context=context,
    )
    await hass.async_block_till_done()

    # The entries belong to the action that asked for the change.
    assert all(e.context.id == context.id for e in events)
    # The switch has an entity: it is named and linked. WDR has none yet in this
    # test, so the path stands in for its name.
    assert [
        (e.data["name"], e.data["message"], e.data.get("entity_id")) for e in events
    ] == [
        (
            "Front Camera Highlight compensation",
            "was turned off automatically so that Front Camera Smart supplement light could be changed",
            HLC,
        ),
        (
            "WDR/mode",
            "was turned off automatically so that Front Camera Smart supplement light could be changed",
            None,
        ),
    ]
    # An entry that has no entity of its own is the integration's.
    assert [e.data.get("domain") for e in events] == [None, "hikvision"]
    assert hass.states.get(HLC).state == STATE_OFF
    assert hass.states.get(SMART_LIGHT).state == STATE_ON


@pytest.mark.usefixtures("mock_hikcamera")
async def test_other_settings_are_logged_when_the_change_is_still_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a blocker that was switched off is reported even if the change failed."""
    await setup_integration(hass, mock_config_entry)
    events = async_capture_events(hass, EVENT_LOGBOOK_ENTRY)
    mock_image_settings.set_image_setting.return_value = ImageWriteResult(
        False, 403, "WDROrDehazeMutexHLC", {"HLC/enabled": "false"}
    )

    # The blocker was switched off, so it is not named as the reason.
    with pytest.raises(HomeAssistantError, match="did not accept the image setting"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: SMART_LIGHT}, blocking=True
        )

    assert [e.data["name"] for e in events] == ["Front Camera Highlight compensation"]
    # The stored value follows the camera without waiting for the next poll.
    assert hass.states.get(HLC).state == STATE_OFF


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("result", "message"),
    [
        (ImageWriteResult(False, 403, "lowPrivilege"), "not allowed to change"),
        (
            ImageWriteResult(False, 0, "pathNotFound"),
            r"did not accept the image setting \(pathNotFound\)",
        ),
        # Firmware differs in the code it uses for the two directions, so the message
        # follows the setting that was asked for: this is highlight compensation.
        (
            ImageWriteResult(False, 403, "HLCMutexWDROrDehaze"),
            "Highlight compensation cannot be turned on while wide dynamic range",
        ),
        (
            ImageWriteResult(False, 403, "WDROrDehazeMutexHLC"),
            "Highlight compensation cannot be turned on while wide dynamic range",
        ),
    ],
)
async def test_write_rejected_by_camera(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    result: ImageWriteResult,
    message: str,
) -> None:
    """Test a rejected write is reported and leaves the state unchanged."""
    await setup_integration(hass, mock_config_entry)
    mock_image_settings.set_image_setting.return_value = result

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: HLC}, blocking=True
        )

    assert hass.states.get(HLC).state == STATE_ON


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("error", "message"),
    [
        (ISAPIConnectionError("camera is gone"), "Failed to connect"),
        (ISAPIAuthError("Insufficient permissions", 403), "not allowed to change"),
        (ISAPIError("bad document"), "did not accept the image setting"),
    ],
)
async def test_write_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    error: ISAPIError,
    message: str,
) -> None:
    """Test an error while writing is reported with a translated message."""
    await setup_integration(hass, mock_config_entry)
    mock_image_settings.set_image_setting.side_effect = error

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: HLC}, blocking=True
        )

    assert not hass.config_entries.flow.async_progress()
    assert hass.states.get(HLC).state == STATE_ON


async def test_rejected_password_while_writing_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a changed password is noticed by the write, not only by the next poll."""
    await setup_integration(hass, mock_config_entry)
    mock_image_settings.set_image_setting.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )
    polls = mock_image_settings.get_image_values.call_count

    with pytest.raises(HomeAssistantError, match="rejected the username or password"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: HLC}, blocking=True
        )
    await hass.async_block_till_done()

    # No new request is sent with the rejected password, and the stream is stopped.
    assert mock_image_settings.get_image_values.call_count == polls
    mock_hikcamera.return_value.disconnect.assert_called_once()
    assert hass.states.get(HLC).state == STATE_UNAVAILABLE
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_requests_queued_behind_a_rejected_password_are_not_sent(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test the first 401 stops the actions and the poll already waiting for it.

    Each attempt with a wrong password counts towards locking the account.
    """
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.image_coordinator
    mock_image_settings.set_image_setting.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )
    polls = mock_image_settings.get_image_values.call_count

    # Queue two actions and a poll behind a request that is still running.
    async with coordinator.lock:
        actions = [
            hass.async_create_task(
                hass.services.async_call(
                    SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
                )
            )
            for service, entity_id in (
                (SERVICE_TURN_OFF, HLC),
                (SERVICE_TURN_OFF, SMART_LIGHT),
            )
        ]
        freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
        # The first action and the poll wait for the lock; the second action waits
        # for the first, as the platform runs one action at a time.
        for _ in range(100):
            if len(coordinator.lock._waiters or ()) == 2:
                break
            await asyncio.sleep(0)
        assert len(coordinator.lock._waiters or ()) == 2
    results = await asyncio.gather(*actions, return_exceptions=True)
    await hass.async_block_till_done()

    assert mock_image_settings.set_image_setting.call_count == 1
    assert mock_image_settings.get_image_values.call_count == polls
    for result in results:
        assert isinstance(result, HomeAssistantError)
        assert result.translation_key == "invalid_auth"
    mock_hikcamera.return_value.disconnect.assert_called_once()
    assert hass.states.get(HLC).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_hikcamera")
async def test_unavailable_when_polling_fails(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    image_values: dict[str, str],
) -> None:
    """Test entities become unavailable when the camera stops answering."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(HLC).state == STATE_ON

    mock_image_settings.get_image_values.side_effect = ISAPIError("timeout")
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(HLC).state == STATE_UNAVAILABLE

    mock_image_settings.get_image_values.side_effect = None
    mock_image_settings.get_image_values.return_value = image_values
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(HLC).state == STATE_ON


@pytest.mark.usefixtures("mock_hikcamera")
async def test_state_unknown_when_the_camera_reports_no_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    image_values: dict[str, str],
) -> None:
    """Test a setting the camera currently does not report has an unknown state."""
    mock_image_settings.get_image_values.return_value = {
        key: value for key, value in image_values.items() if key != "HLC/enabled"
    }

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(HLC).state == STATE_UNKNOWN


async def test_rejected_password_while_polling_starts_reauth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a changed password stops the event stream and asks for new credentials."""
    await setup_integration(hass, mock_config_entry)
    assert not hass.config_entries.flow.async_progress()

    mock_image_settings.get_image_values.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # The stream would otherwise keep retrying the old password.
    mock_hikcamera.return_value.disconnect.assert_called_once()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert hass.states.get(HLC).state == STATE_UNAVAILABLE


async def test_missing_permission_while_polling_is_not_a_reauth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a camera that stops allowing reads does not ask for a new password."""
    await setup_integration(hass, mock_config_entry)

    mock_image_settings.get_image_values.side_effect = ISAPIAuthError(
        "Insufficient permissions", 403
    )
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_hikcamera.return_value.disconnect.assert_not_called()
    assert not hass.config_entries.flow.async_progress()
    assert hass.states.get(HLC).state == STATE_UNAVAILABLE
