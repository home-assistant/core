"""Test the Bosch Smart Camera switch platform."""

import asyncio
from unittest.mock import AsyncMock

from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
    BoschCameraInvalidResponseError,
    Camera,
    CameraModel,
)
from bosch_shc_camera_client.cloud import CloudPutResult
from bosch_shc_camera_client.settings import SettingWriteResult
from bosch_shc_camera_client.states import CameraAccountStates, MotionSettings
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.bosch_smart_camera.coordinator import SCAN_INTERVAL
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import CAMERA_ID, CAMERAS

pytestmark = pytest.mark.usefixtures("setup_credentials")

ENTITY_ID = "switch.garden_privacy_mode"
MOTION_ID = "switch.garden_motion_detection"


async def test_privacy_mode_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the privacy mode switch reflects the camera list."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == f"{CAMERA_ID}_privacy_mode"
    assert entry.translation_key == "privacy_mode"
    assert entry.entity_category is EntityCategory.CONFIG


@pytest.mark.parametrize(
    ("service", "enabled", "state"),
    [(SERVICE_TURN_ON, True, STATE_ON), (SERVICE_TURN_OFF, False, STATE_OFF)],
)
async def test_set_privacy_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_privacy_mode: AsyncMock,
    service: str,
    enabled: bool,
    state: str,
) -> None:
    """Test switching the privacy mode writes to the cloud and updates the state."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    assert mock_set_privacy_mode.call_args.args[2:] == (CAMERA_ID, enabled)
    assert hass.states.get(ENTITY_ID).state == state


async def test_set_privacy_mode_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_privacy_mode: AsyncMock,
) -> None:
    """Test a rejected write raises and keeps the state."""
    mock_set_privacy_mode.return_value = CloudPutResult(ok=False, status=500)
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )

    assert err.value.translation_key == "privacy_mode_failed"
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


async def test_privacy_mode_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_account_states: AsyncMock,
) -> None:
    """Test the switch is unavailable when the camera reports no privacy mode."""
    mock_account_states.return_value = {CAMERA_ID: CameraAccountStates(None, None)}
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_privacy_mode_missing_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_account_states: AsyncMock,
) -> None:
    """Test the switch is unavailable when the list has no state for the camera."""
    mock_account_states.return_value = {}
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_states_fetch_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_account_states: AsyncMock,
) -> None:
    """Test a failing state fetch makes the setup retry."""
    mock_account_states.side_effect = BoschCameraConnectionError("down")
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID) is None


@pytest.mark.parametrize("status", [401, 403])
async def test_set_privacy_mode_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_privacy_mode: AsyncMock,
    status: int,
) -> None:
    """Test a rejected token raises and starts the reauthentication flow."""
    mock_set_privacy_mode.return_value = CloudPutResult(ok=False, status=status)
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    await hass.async_block_till_done()

    assert err.value.translation_key == "auth_failed"
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_poll_during_write_keeps_written_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_privacy_mode: AsyncMock,
    mock_account_states: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a poll that started before a write does not undo it."""
    await setup_integration(hass, mock_config_entry)
    release = asyncio.Event()
    stale = {CAMERA_ID: CameraAccountStates(False, None)}

    async def slow_states(*args: object, **kwargs: object) -> dict:
        await release.wait()
        return stale

    mock_account_states.side_effect = slow_states
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await asyncio.sleep(0)

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    release.set()
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON

    mock_account_states.side_effect = None
    mock_account_states.return_value = {CAMERA_ID: CameraAccountStates(True, None)}
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    mock_account_states.return_value = {CAMERA_ID: CameraAccountStates(False, None)}
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


async def test_camera_removed_during_write(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_privacy_mode: AsyncMock,
    mock_list_cameras: AsyncMock,
    mock_account_states: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a write that finishes after the camera was removed does not fail."""
    await setup_integration(hass, mock_config_entry)

    async def remove_then_ok(*args: object) -> CloudPutResult:
        mock_list_cameras.return_value = []
        mock_account_states.return_value = {}
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        return CloudPutResult(ok=True, status=204)

    mock_set_privacy_mode.side_effect = remove_then_ok
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    assert hass.states.get(ENTITY_ID) is None


async def test_motion_detection_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_motion_settings: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the motion detection switch reflects the polled settings."""
    mock_get_motion_settings.return_value = MotionSettings(True, "HIGH")
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(MOTION_ID).state == STATE_ON
    entry = entity_registry.async_get(MOTION_ID)
    assert entry.unique_id == f"{CAMERA_ID}_motion_detection"
    assert entry.translation_key == "motion_detection"
    assert entry.entity_category is EntityCategory.CONFIG


@pytest.mark.parametrize(
    ("service", "enabled", "state"),
    [(SERVICE_TURN_ON, True, STATE_ON), (SERVICE_TURN_OFF, False, STATE_OFF)],
)
async def test_set_motion_detection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_motion_enabled: AsyncMock,
    mock_get_motion_settings: AsyncMock,
    service: str,
    enabled: bool,
    state: str,
) -> None:
    """Test switching the motion detection writes to the cloud."""
    mock_get_motion_settings.return_value = MotionSettings(not enabled, "LOW")
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: MOTION_ID}, blocking=True
    )

    assert mock_set_motion_enabled.call_args.args[2:] == (CAMERA_ID, enabled)
    assert hass.states.get(MOTION_ID).state == state


@pytest.mark.parametrize(
    "error", [BoschCameraConnectionError("down"), BoschCameraInvalidResponseError("x")]
)
async def test_set_motion_detection_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_motion_enabled: AsyncMock,
    error: Exception,
) -> None:
    """Test a failed write raises and keeps the state."""
    mock_set_motion_enabled.side_effect = error
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: MOTION_ID}, blocking=True
        )

    assert err.value.translation_key == "motion_detection_failed"
    assert hass.states.get(MOTION_ID).state == STATE_OFF


async def test_set_motion_detection_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_motion_enabled: AsyncMock,
) -> None:
    """Test a rejected token raises and starts the reauthentication flow."""
    mock_set_motion_enabled.side_effect = BoschCameraAuthError("denied")
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: MOTION_ID}, blocking=True
        )
    await hass.async_block_till_done()

    assert err.value.translation_key == "auth_failed"
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_motion_poll_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_motion_settings: AsyncMock,
) -> None:
    """Test a rejected token while polling starts the reauthentication flow."""
    mock_get_motion_settings.side_effect = BoschCameraAuthError("denied")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert hass.config_entries.flow.async_progress()[0]["context"]["source"] == (
        "reauth"
    )


async def test_motion_poll_failure_isolated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_motion_settings: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an unreadable camera is unavailable, logged once, and recovers."""
    mock_get_motion_settings.side_effect = BoschCameraConnectionError("down")
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    assert hass.states.get(MOTION_ID).state == STATE_UNAVAILABLE
    assert caplog.text.count("motion detection of Garden is unreachable") == 1

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert caplog.text.count("motion detection of Garden is unreachable") == 1

    mock_get_motion_settings.side_effect = None
    mock_get_motion_settings.return_value = MotionSettings(True, "LOW")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(MOTION_ID).state == STATE_ON
    assert "motion detection of Garden is reachable again" in caplog.text


async def test_motion_poll_during_write_keeps_written_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_motion_enabled: AsyncMock,
    mock_get_motion_settings: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a poll that started before a write does not undo it."""
    await setup_integration(hass, mock_config_entry)
    release = asyncio.Event()

    async def slow_settings(*args: object, **kwargs: object) -> MotionSettings:
        await release.wait()
        return MotionSettings(False, "LOW")

    mock_get_motion_settings.side_effect = slow_settings
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await asyncio.sleep(0)

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: MOTION_ID}, blocking=True
    )
    release.set()
    await hass.async_block_till_done()
    assert hass.states.get(MOTION_ID).state == STATE_ON

    # The camera may revert the write, so the next poll wins.
    mock_get_motion_settings.side_effect = None
    mock_get_motion_settings.return_value = MotionSettings(False, "LOW")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(MOTION_ID).state == STATE_OFF


async def test_motion_camera_removed_during_write(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_motion_enabled: AsyncMock,
    mock_list_cameras: AsyncMock,
    mock_account_states: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a write that finishes after the camera was removed does not fail."""
    await setup_integration(hass, mock_config_entry)

    async def remove_then_ok(*args: object, **kwargs: object) -> SettingWriteResult:
        mock_list_cameras.return_value = []
        mock_account_states.return_value = {}
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        return SettingWriteResult(204, None, None)

    mock_set_motion_enabled.side_effect = remove_then_ok
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: MOTION_ID}, blocking=True
    )

    assert hass.states.get(MOTION_ID) is None


async def test_motion_write_during_other_camera_poll(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    mock_account_states: AsyncMock,
    mock_set_motion_enabled: AsyncMock,
    mock_get_motion_settings: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a write for B that ends while A is polled beats B's older GET."""
    cam_b = "22222222-2222-2222-2222-222222222222"
    # B is polled first, so its GET is done when A blocks.
    mock_list_cameras.return_value = [
        Camera(cam_b, "Yard", "HOME_Eyes_Outdoor", CameraModel.EYES_OUTDOOR_II, "1"),
        *CAMERAS,
    ]
    mock_account_states.return_value = {
        CAMERA_ID: CameraAccountStates(False, None),
        cam_b: CameraAccountStates(False, None),
    }
    await setup_integration(hass, mock_config_entry)
    release = asyncio.Event()

    async def settings(
        session: object, token: str, camera_id: str, **kwargs: object
    ) -> MotionSettings:
        if camera_id == CAMERA_ID:
            await release.wait()
        return MotionSettings(False, "LOW")

    mock_get_motion_settings.side_effect = settings
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await asyncio.sleep(0)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.yard_motion_detection"},
        blocking=True,
    )
    release.set()
    await hass.async_block_till_done()

    assert hass.states.get("switch.yard_motion_detection").state == STATE_ON
    assert hass.states.get(MOTION_ID).state == STATE_OFF


async def test_motion_write_after_failed_poll_started(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_motion_enabled: AsyncMock,
    mock_get_motion_settings: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a write that ends after a failed poll started keeps its value."""
    await setup_integration(hass, mock_config_entry)
    release = asyncio.Event()

    async def failing(*args: object, **kwargs: object) -> MotionSettings:
        await release.wait()
        raise BoschCameraConnectionError("down")

    mock_get_motion_settings.side_effect = failing
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await asyncio.sleep(0)

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: MOTION_ID}, blocking=True
    )
    release.set()
    await hass.async_block_till_done()

    assert hass.states.get(MOTION_ID).state == STATE_ON


async def test_motion_failed_poll_without_write(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_motion_enabled: AsyncMock,
    mock_get_motion_settings: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed poll after an earlier write makes the camera unavailable."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: MOTION_ID}, blocking=True
    )
    mock_get_motion_settings.side_effect = BoschCameraConnectionError("down")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(MOTION_ID).state == STATE_UNAVAILABLE


async def test_removed_cameras_are_forgotten_by_the_motion_tracking(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the write counters and unreachable marks of removed cameras are pruned."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator._motion_unreachable.add("removed")
    coordinator._motion_writes["removed"] = 3

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert "removed" not in coordinator._motion_unreachable
    assert "removed" not in coordinator._motion_writes
