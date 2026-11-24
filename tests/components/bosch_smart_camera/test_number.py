"""Test the Bosch Smart Camera number platform."""

import asyncio
import logging
import math
from unittest.mock import AsyncMock

from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
    BoschCameraInvalidResponseError,
    Camera,
    CameraModel,
)
from bosch_shc_camera_client.settings import AudioSettings
from bosch_shc_camera_client.states import CameraAccountStates
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.bosch_smart_camera.coordinator import SCAN_INTERVAL
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import CAMERA_ID, CAMERAS

pytestmark = pytest.mark.usefixtures("setup_credentials")

ENTITY_ID = "number.garden_speaker_level"
OTHER_ID = "22222222-2222-2222-2222-222222222222"
OTHER_ENTITY_ID = "number.patio_speaker_level"


async def _set(hass: HomeAssistant, value: float) -> None:
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_VALUE: value},
        blocking=True,
    )


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_speaker_level(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the number reflects the speaker level."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.state == "60"
    assert state.attributes["min"] == 0
    assert state.attributes["max"] == 100
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == f"{CAMERA_ID}_speaker_level"
    assert entry.translation_key == "speaker_level"
    assert entry.entity_category is EntityCategory.CONFIG


async def test_no_speaker(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_audio_settings: AsyncMock,
) -> None:
    """Test a camera without a speaker gets no number."""
    mock_get_audio_settings.return_value = AudioSettings(True, 40, None, {})
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID) is None


async def test_set_speaker_level(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_audio_settings: AsyncMock,
) -> None:
    """Test setting the level writes an integer and updates the state."""
    await setup_integration(hass, mock_config_entry)

    await _set(hass, 25.4)

    assert mock_set_audio_settings.call_args.args[2] == CAMERA_ID
    assert mock_set_audio_settings.call_args.kwargs["speaker_level"] == 25
    assert hass.states.get(ENTITY_ID).state == "25"


async def test_set_speaker_level_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_audio_settings: AsyncMock,
) -> None:
    """Test a failing write raises and keeps the state."""
    mock_set_audio_settings.side_effect = BoschCameraInvalidResponseError("bad")
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as err:
        await _set(hass, 10)

    assert err.value.translation_key == "speaker_level_failed"
    assert hass.states.get(ENTITY_ID).state == "60"


async def test_set_speaker_level_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_audio_settings: AsyncMock,
) -> None:
    """Test a rejected token raises and starts the reauthentication flow."""
    mock_set_audio_settings.side_effect = BoschCameraAuthError("denied")
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as err:
        await _set(hass, 10)
    await hass.async_block_till_done()

    assert err.value.translation_key == "auth_failed"
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_poll_unreachable_keeps_setup_and_logs_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_audio_settings: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unreachable camera does not fail the refresh and logs once."""
    caplog.set_level(logging.INFO)
    await setup_integration(hass, mock_config_entry)

    mock_get_audio_settings.side_effect = BoschCameraConnectionError("down")
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    await _poll(hass, freezer)
    assert caplog.text.count("are unreachable") == 1

    mock_get_audio_settings.side_effect = None
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == "60"
    assert caplog.text.count("are reachable again") == 1


async def test_poll_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_audio_settings: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a rejected token during the poll starts the reauthentication."""
    await setup_integration(hass, mock_config_entry)

    mock_get_audio_settings.side_effect = BoschCameraAuthError("denied")
    await _poll(hass, freezer)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress()
    assert flows[0]["context"]["source"] == "reauth"


async def test_poll_during_write_keeps_written_level(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_audio_settings: AsyncMock,
    mock_get_audio_settings: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a poll that started before a write does not undo it."""
    await setup_integration(hass, mock_config_entry)
    release = asyncio.Event()

    async def slow(*args: object, **kwargs: object) -> AudioSettings:
        await release.wait()
        return AudioSettings(True, 40, 60, {})

    mock_get_audio_settings.side_effect = slow
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await asyncio.sleep(0)

    await _set(hass, 5)
    release.set()
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == "5"

    mock_get_audio_settings.side_effect = None
    mock_get_audio_settings.return_value = AudioSettings(True, 40, 70, {})
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == "70"


async def test_new_camera_gets_number(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_audio_settings: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a speaker level that appears later creates the entity."""
    mock_get_audio_settings.side_effect = BoschCameraConnectionError("down")
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID) is None

    mock_get_audio_settings.side_effect = None
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == "60"


async def test_camera_removed_during_write(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_audio_settings: AsyncMock,
    mock_list_cameras: AsyncMock,
    mock_account_states: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a write that finishes after the camera was removed does not fail."""
    await setup_integration(hass, mock_config_entry)

    async def remove_then_ok(*args: object, **kwargs: object) -> None:
        mock_list_cameras.return_value = []
        mock_account_states.return_value = {}
        await _poll(hass, freezer)

    mock_set_audio_settings.side_effect = remove_then_ok
    await _set(hass, 5)

    assert hass.states.get(ENTITY_ID) is None


async def test_set_speaker_level_invalid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_audio_settings: AsyncMock,
) -> None:
    """Test NaN, which passes the range check, is rejected before any write."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await _set(hass, math.nan)
    assert err.value.translation_key == "invalid_speaker_level"
    with pytest.raises(ServiceValidationError):
        await _set(hass, math.inf)
    mock_set_audio_settings.assert_not_called()


async def test_failed_poll_without_write_is_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_audio_settings: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed poll without a write makes the number unavailable."""
    await setup_integration(hass, mock_config_entry)

    mock_get_audio_settings.side_effect = BoschCameraInvalidResponseError("bad")
    await _poll(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_write_after_failed_poll_keeps_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_audio_settings: AsyncMock,
    mock_set_audio_settings: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a write that finishes after a failed poll keeps its value."""
    await setup_integration(hass, mock_config_entry)
    release = asyncio.Event()

    async def slow_fail(*args: object, **kwargs: object) -> AudioSettings:
        await release.wait()
        raise BoschCameraConnectionError("down")

    mock_get_audio_settings.side_effect = slow_fail
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await asyncio.sleep(0)

    await _set(hass, 5)
    release.set()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == "5"


async def test_write_during_poll_of_other_camera(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    mock_account_states: AsyncMock,
    mock_get_audio_settings: AsyncMock,
    mock_set_audio_settings: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a write to a camera polled earlier is kept; failures stay isolated."""
    other = Camera(
        OTHER_ID, "Patio", "HOME_Eyes_Indoor", CameraModel.EYES_INDOOR_II, "9"
    )
    mock_list_cameras.return_value = [*CAMERAS, other]
    mock_account_states.return_value = {
        CAMERA_ID: CameraAccountStates(False, None),
        OTHER_ID: CameraAccountStates(False, None),
    }
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(OTHER_ENTITY_ID).state == "60"
    release = asyncio.Event()

    async def per_camera(
        session: object, token: object, camera_id: str, **kwargs: object
    ) -> AudioSettings:
        if camera_id == CAMERA_ID:
            raise BoschCameraConnectionError("down")
        await release.wait()
        return AudioSettings(True, 40, 80, {})

    mock_get_audio_settings.side_effect = per_camera
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    # The first camera failed its poll, the second is still being polled.
    await _set(hass, 7)
    release.set()
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == "7"
    assert hass.states.get(OTHER_ENTITY_ID).state == "80"

    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(OTHER_ENTITY_ID).state == "80"


async def test_removed_camera_is_logged_again_when_it_returns(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    mock_account_states: AsyncMock,
    mock_get_audio_settings: AsyncMock,
    mock_set_audio_settings: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a removed camera loses its unreachable mark and is logged anew."""
    other = Camera(
        OTHER_ID, "Patio", "HOME_Eyes_Indoor", CameraModel.EYES_INDOOR_II, "9"
    )
    both = [*CAMERAS, other]
    states = {
        CAMERA_ID: CameraAccountStates(False, None),
        OTHER_ID: CameraAccountStates(False, None),
    }
    mock_list_cameras.return_value = both
    mock_account_states.return_value = states
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: OTHER_ENTITY_ID, ATTR_VALUE: 5},
        blocking=True,
    )

    async def other_down(
        session: object, token: object, camera_id: str, **kwargs: object
    ) -> AudioSettings:
        if camera_id == OTHER_ID:
            raise BoschCameraConnectionError("down")
        return AudioSettings(True, 40, 60, {})

    mock_get_audio_settings.side_effect = other_down
    message = "The audio settings of Patio are unreachable"
    await _poll(hass, freezer)
    assert caplog.text.count(message) == 1

    mock_list_cameras.return_value = list(CAMERAS)
    await _poll(hass, freezer)
    assert hass.states.get(OTHER_ENTITY_ID) is None

    mock_list_cameras.return_value = both
    await _poll(hass, freezer)
    assert caplog.text.count(message) == 2
