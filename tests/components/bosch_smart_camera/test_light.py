"""Test the Bosch Smart Camera light platform."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
    BoschCameraInvalidResponseError,
    Camera,
    CameraModel,
)
from bosch_shc_camera_client.cloud import CameraLightSetResult
from bosch_shc_camera_client.states import LightState
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.bosch_smart_camera.coordinator import SCAN_INTERVAL
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import CAMERA_ID, CAMERAS

pytestmark = pytest.mark.usefixtures("setup_credentials")

ENTITY_ID = "light.garden_camera_light"
GEN1 = Camera(CAMERA_ID, "Garden", "OUTDOOR", CameraModel.EYES_OUTDOOR, "7.91.56")
OFF = LightState(False, False, 0.5)
ON = LightState(True, True, 0.5)
OTHER_ID = "22222222-2222-2222-2222-222222222222"
MODULE = "homeassistant.components.bosch_smart_camera.coordinator"


@pytest.fixture(autouse=True)
def mock_gen1(mock_list_cameras: AsyncMock) -> None:
    """Make the account hold a Gen1 outdoor camera."""
    mock_list_cameras.return_value = [GEN1]


@pytest.fixture
def mock_get_light() -> Generator[AsyncMock]:
    """Mock the light state of the library."""
    with patch(f"{MODULE}.get_light_state", autospec=True, return_value=OFF) as mock:
        yield mock


@pytest.fixture
def mock_set_light() -> Generator[AsyncMock]:
    """Mock the light write of the library."""
    with patch(
        f"{MODULE}.cloud_set_camera_light",
        autospec=True,
        return_value=CameraLightSetResult(ok=True, status=204),
    ) as mock:
        yield mock


@pytest.mark.usefixtures("mock_get_light")
async def test_light_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the light is created for a Gen1 outdoor camera."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    assert entity_registry.async_get(ENTITY_ID).unique_id == CAMERA_ID


@pytest.mark.usefixtures("mock_get_light")
async def test_no_light_for_other_models(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
) -> None:
    """Test cameras without the Gen1 light get no light entity."""
    mock_list_cameras.return_value = list(CAMERAS)
    await setup_integration(hass, mock_config_entry)

    assert hass.states.async_entity_ids(LIGHT_DOMAIN) == []


@pytest.mark.usefixtures("mock_get_light")
async def test_turn_on_and_off(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_set_light: AsyncMock
) -> None:
    """Test the light writes to the camera and shows the new state."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert mock_set_light.await_args.args[1:4] == (
        "fake-access-token",
        CAMERA_ID,
        True,
    )
    assert mock_set_light.await_args.kwargs == {
        "gen2": False,
        "last_front_intensity": 0.5,
    }

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    assert mock_set_light.await_args.args[3] is False


@pytest.mark.usefixtures("mock_get_light")
async def test_intensity_defaults_to_full(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_light: AsyncMock,
    mock_set_light: AsyncMock,
) -> None:
    """Test an unknown intensity is sent as full intensity."""
    mock_get_light.return_value = LightState(False, False, None)
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert mock_set_light.await_args.kwargs["last_front_intensity"] == 1.0


@pytest.mark.usefixtures("mock_get_light")
@pytest.mark.parametrize(
    "side_effect",
    [
        BoschCameraAuthError("rejected"),
        BoschCameraConnectionError("offline"),
        CameraLightSetResult(ok=False, status=400),
    ],
)
async def test_write_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_light: AsyncMock,
    side_effect: Exception | CameraLightSetResult,
) -> None:
    """Test a failed write raises and leaves the state untouched."""
    await setup_integration(hass, mock_config_entry)
    if isinstance(side_effect, Exception):
        mock_set_light.side_effect = side_effect
    else:
        mock_set_light.return_value = side_effect

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    assert err.value.translation_key == "light_failed"
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


async def test_unavailable_without_light_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_get_light: AsyncMock
) -> None:
    """Test the light is unavailable when the coordinator has no state for it."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator.light_states.clear()
    coordinator.async_update_listeners()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_light_auth_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_get_light: AsyncMock
) -> None:
    """Test a rejected token while reading the light starts reauthentication."""
    mock_get_light.side_effect = BoschCameraAuthError("rejected")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "error",
    [BoschCameraConnectionError("offline"), BoschCameraInvalidResponseError("bad")],
)
async def test_light_read_error_only_affects_the_light(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_light: AsyncMock,
    error: Exception,
) -> None:
    """Test a failing light endpoint leaves the camera itself available."""
    mock_get_light.side_effect = error
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get("camera.garden").state != STATE_UNAVAILABLE


@pytest.mark.parametrize("status", [401, 403])
@pytest.mark.usefixtures("mock_get_light")
async def test_write_auth_status_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_set_light: AsyncMock,
    status: int,
) -> None:
    """Test a rejected write token starts reauthentication."""
    await setup_integration(hass, mock_config_entry)
    mock_set_light.return_value = CameraLightSetResult(ok=False, status=status)

    with (
        patch.object(
            mock_config_entry, "async_start_reauth_if_available"
        ) as start_reauth,
        pytest.raises(HomeAssistantError) as err,
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    assert err.value.translation_key == "auth_failed"
    start_reauth.assert_called_once_with(hass)


async def test_poll_started_before_a_write_does_not_overwrite_it(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_light: AsyncMock,
    mock_set_light: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an older poll result is dropped after a successful write."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    async def stale_read(*args: Any, **kwargs: Any) -> LightState:
        await coordinator.async_set_light(CAMERA_ID, True)
        return OFF

    mock_get_light.side_effect = stale_read
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_write_during_poll_of_another_camera_is_kept(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    mock_get_light: AsyncMock,
    mock_set_light: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a write to a camera polled earlier is not overwritten by the batch."""
    other = Camera(OTHER_ID, "Yard", "OUTDOOR", CameraModel.EYES_OUTDOOR, None)
    mock_list_cameras.return_value = [GEN1, other]
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    async def read(session: Any, token: str, camera_id: str) -> LightState:
        if camera_id == OTHER_ID:
            await coordinator.async_set_light(CAMERA_ID, True)
        return OFF

    mock_get_light.side_effect = read
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_write_after_failed_poll_keeps_working(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_light: AsyncMock,
    mock_set_light: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a poll failing during a write does not break recording the write."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    async def slow_write(*args: Any, **kwargs: Any) -> CameraLightSetResult:
        mock_get_light.side_effect = BoschCameraConnectionError("offline")
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        return CameraLightSetResult(ok=True, status=204)

    mock_set_light.side_effect = slow_write
    await coordinator.async_set_light(CAMERA_ID, True)

    assert hass.states.get(ENTITY_ID).state == STATE_ON
