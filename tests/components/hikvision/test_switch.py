"""Test Hikvision image setting switches."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyhik.image import (
    ImageSetting,
    ImageSettingType,
    ImageWriteResult,
    parse_image_capabilities,
    parse_image_values,
)
from pyhik.isapi import ISAPIAuthError, ISAPIConnectionError, ISAPIError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
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
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import TEST_DEVICE_ID

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


@pytest.mark.usefixtures("mock_hikcamera")
async def test_unknown_settings_are_skipped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a switch without a description gets no entity."""
    mock_image_settings.get_image_settings.return_value = [
        *mock_image_settings.get_image_settings.return_value,
        ImageSetting(path="Unknown/enabled", type=ImageSettingType.SWITCH),
    ]
    mock_image_settings.get_image_values.return_value = {
        **mock_image_settings.get_image_values.return_value,
        "Unknown/enabled": "true",
    }

    await setup_integration(hass, mock_config_entry)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert entries
    assert not any("unknown" in entry.unique_id for entry in entries)


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
    # The unique ID comes from the description, not from the firmware's path.
    assert entry.unique_id == f"{TEST_DEVICE_ID}_image_highlight_compensation"
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
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == STATE_ON
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    mock_image_settings.set_image_setting.assert_called_once_with(
        "BLC/enabled", "false"
    )


_CHANNEL = '<ImageChannel version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">{}</ImageChannel>'


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("key", "element", "path"),
    [
        (
            "lens_distortion_correction",
            "<LensDistortionCorrection><enabled{}</enabled></LensDistortionCorrection>",
            "LensDistortionCorrection/enabled",
        ),
        ("image_stabilization", "<EIS><enabled{}</enabled></EIS>", "EIS/enabled"),
        ("digital_slow_shutter", "<DSS><enabled{}</enabled></DSS>", "DSS/enabled"),
        (
            "image_freeze",
            "<ImageFreeze><enabled{}</enabled></ImageFreeze>",
            "ImageFreeze/enabled",
        ),
        (
            "lens_initialization",
            "<LensInitialization><enabled{}</enabled></LensInitialization>",
            "LensInitialization/enabled",
        ),
        (
            "proportional_pan",
            "<proportionalpan><enabled{}</enabled></proportionalpan>",
            "proportionalpan/enabled",
        ),
        # At the root of the channel, not in a group of its own.
        (
            "image_loss_detection",
            "<enableImageLossDetection{}</enableImageLossDetection>",
            "enableImageLossDetection",
        ),
    ],
)
async def test_switches_the_fixture_camera_does_not_have(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    entity_registry: er.EntityRegistry,
    key: str,
    element: str,
    path: str,
) -> None:
    """Test each switch is found from the capabilities, and writes its own path.

    They are disabled by default, as configuration entities.
    """
    capabilities = _CHANNEL.format(element.format(' opt="true,false">false'))
    values = _CHANNEL.format(element.format(">true"))
    mock_image_settings.get_image_settings.return_value = parse_image_capabilities(
        capabilities, values
    )
    mock_image_settings.get_image_values.return_value = parse_image_values(values)

    await setup_integration(hass, mock_config_entry)

    entity_id = f"switch.front_camera_{key}"
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.unique_id == f"{TEST_DEVICE_ID}_image_{key}"
    assert entry.translation_key == key
    assert entry.entity_category is EntityCategory.CONFIG
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    ) == [entry]

    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    mock_image_settings.set_image_setting.assert_called_once_with(path, "false")
    mock_image_settings.set_image_setting.reset_mock()
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    mock_image_settings.set_image_setting.assert_called_once_with(path, "true")


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
@pytest.mark.parametrize(
    ("result", "message"),
    [
        (ImageWriteResult(False, 403, "lowPrivilege"), "not allowed to change"),
        # Only a 403 without a code means the user may not: a server error does not.
        (
            ImageWriteResult(False, 500, "noSubStatus"),
            r"did not accept the image setting \(noSubStatus\)",
        ),
        (
            ImageWriteResult(False, 0, "pathNotFound"),
            r"did not accept the image setting \(pathNotFound\)",
        ),
        # Turning highlight compensation off does not run into the conflict that
        # turning it, or WDR or defog, on does.
        (
            ImageWriteResult(False, 403, "HLCMutexWDROrDehaze"),
            r"did not accept the image setting \(HLCMutexWDROrDehaze\)",
        ),
        (
            ImageWriteResult(False, 403, "WDROrDehazeMutexHLC"),
            r"did not accept the image setting \(WDROrDehazeMutexHLC\)",
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
    ("sub_status", "message"),
    [
        (
            "WDROrDehazeMutexHLC",
            r"did not accept the image setting \(WDROrDehazeMutexHLC\)",
        ),
        ("badParameters", r"did not accept the image setting \(badParameters\)"),
    ],
)
async def test_settings_switched_off_before_a_refused_write_are_shown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    sub_status: str,
    message: str,
) -> None:
    """Test a setting the camera switched off to make room shows off at once.

    The camera can switch a blocker off and still refuse the change. There is no
    refresh after a refused write, so it would otherwise show on until the next
    poll. The blocker is then no longer the reason, so its message is not used.
    """
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(HLC).state == STATE_ON
    mock_image_settings.set_image_setting.return_value = ImageWriteResult(
        False, 403, sub_status, also_changed={"HLC/enabled": "false"}
    )

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: SMART_LIGHT}, blocking=True
        )

    assert hass.states.get(HLC).state == STATE_OFF
    assert hass.states.get(SMART_LIGHT).state == STATE_OFF


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
    caplog: pytest.LogCaptureFixture,
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
    await hass.async_block_till_done(wait_background_tasks=True)

    # No new request is sent with the rejected password, and the stream is stopped.
    assert mock_image_settings.get_image_values.call_count == polls
    mock_hikcamera.return_value.disconnect.assert_called_once()
    assert hass.states.get(HLC).state == STATE_UNAVAILABLE
    # The log says nothing more is tried.
    assert (
        "rejected the username or password: nothing more is sent to it until it is "
        "reauthenticated"
    ) in caplog.text
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
    await hass.async_block_till_done(wait_background_tasks=True)

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
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(HLC).state == STATE_UNAVAILABLE

    mock_image_settings.get_image_values.side_effect = None
    mock_image_settings.get_image_values.return_value = image_values
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(HLC).state == STATE_ON


@pytest.mark.usefixtures("mock_hikcamera")
async def test_unavailable_while_the_camera_reports_no_value(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    image_values: dict[str, str],
) -> None:
    """Test a setting the camera currently leaves out cannot be used.

    A camera leaves out the settings of a mode that is not in use, and refuses to
    write them.
    """
    mock_image_settings.get_image_values.return_value = {
        key: value for key, value in image_values.items() if key != "HLC/enabled"
    }

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(HLC).state == STATE_UNAVAILABLE

    # Reported again, as once its mode is chosen.
    mock_image_settings.get_image_values.return_value = image_values
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(HLC).state == STATE_ON


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("value", "state"),
    [
        ("true", STATE_ON),
        ("FALSE", STATE_OFF),
        ("1", STATE_UNKNOWN),
        ("", STATE_UNKNOWN),
    ],
)
async def test_only_true_or_false_is_a_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    image_values: dict[str, str],
    value: str,
    state: str,
) -> None:
    """Test a value the camera reports that is not true or false is unknown."""
    mock_image_settings.get_image_values.return_value = {
        **image_values,
        "HLC/enabled": value,
    }

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(HLC).state == state


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
    await hass.async_block_till_done(wait_background_tasks=True)

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
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_hikcamera.return_value.disconnect.assert_not_called()
    assert not hass.config_entries.flow.async_progress()
    assert hass.states.get(HLC).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_value_spelled_otherwise_follows_its_setting(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the camera may spell a path in its values otherwise than in its settings.

    The value is stored under the setting's spelling, which the writes use too, so
    the setting has one value.
    """
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.image_coordinator
    assert hass.states.get(HLC).state == STATE_ON
    values = {
        path: value
        for path, value in mock_image_settings.get_image_values.return_value.items()
        if path != "HLC/enabled"
    }
    mock_image_settings.get_image_values.return_value = {
        **values,
        "hlc/Enabled": "false",
    }

    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(HLC).state == STATE_OFF
    assert "hlc/Enabled" not in coordinator.data

    # What a refused write switched off on the way, spelled otherwise too. No
    # poll follows a refused write.
    coordinator.async_set_updated_data({**coordinator.data, "HLC/enabled": "true"})
    mock_image_settings.set_image_setting.return_value = ImageWriteResult(
        False, 403, "badParameters", also_changed={"hlc/ENABLED": "false"}
    )
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: SMART_LIGHT}, blocking=True
        )
    assert hass.states.get(HLC).state == STATE_OFF
    assert "hlc/ENABLED" not in coordinator.data


@pytest.mark.usefixtures("mock_hikcamera")
async def test_the_settings_own_spelling_wins(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a value sent both ways is taken from the setting's own spelling."""
    await setup_integration(hass, mock_config_entry)
    values = {
        path: value
        for path, value in mock_image_settings.get_image_values.return_value.items()
        if path != "HLC/enabled"
    }
    # In both orders.
    for both_ways in (
        {**values, "HLC/enabled": "false", "hlc/enabled": "true"},
        {**values, "hlc/enabled": "true", "HLC/enabled": "false"},
    ):
        mock_image_settings.get_image_values.return_value = dict(both_ways)
        freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert hass.states.get(HLC).state == STATE_OFF
