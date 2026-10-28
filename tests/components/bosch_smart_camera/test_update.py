"""Test the Bosch Smart Camera update platform."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import AsyncMock, patch

from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
)
from bosch_shc_camera_client.states import FirmwareStatus
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.bosch_smart_camera.coordinator import (
    FIRMWARE_SCAN_INTERVAL,
    SCAN_INTERVAL,
)
from homeassistant.components.update import UpdateEntityFeature
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import CAMERA_ID, CAMERAS

pytestmark = pytest.mark.usefixtures("setup_credentials")

ENTITY_ID = "update.garden_firmware"
AVAILABLE = FirmwareStatus("9.40.25", "9.40.30", False, False)


@pytest.fixture(autouse=True)
def mock_token_valid() -> Generator[AsyncMock]:
    """Keep the token valid while the tests advance time by hours."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid"
    ) as mock:
        yield mock


async def test_up_to_date(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a camera without a pending update."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["installed_version"] == "9.40.25"
    assert state.attributes["latest_version"] == "9.40.25"
    assert state.attributes["in_progress"] is False
    assert state.attributes["supported_features"] == UpdateEntityFeature.PROGRESS
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == f"{CAMERA_ID}_firmware"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_update_available_and_installing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_firmware_status: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a pending update, then one that is being installed."""
    mock_get_firmware_status.return_value = AVAILABLE
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["latest_version"] == "9.40.30"
    assert state.attributes["in_progress"] is False

    mock_get_firmware_status.return_value = replace(AVAILABLE, updating=True)
    freezer.tick(FIRMWARE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["in_progress"] is True


async def test_unknown_status_keeps_installed_version(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_firmware_status: AsyncMock,
) -> None:
    """Test an unreported status does not announce an update."""
    mock_get_firmware_status.return_value = FirmwareStatus(None, None, None, False)
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["latest_version"] == "9.40.25"


@pytest.mark.parametrize(
    "exception",
    [BoschCameraAuthError("rejected"), BoschCameraConnectionError("down")],
)
async def test_firmware_failure_does_not_block_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_firmware_status: AsyncMock,
    exception: Exception,
) -> None:
    """Test the camera is set up although the firmware status cannot be read."""
    mock_get_firmware_status.side_effect = exception
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    camera = hass.states.get("camera.garden")
    assert camera is not None
    assert camera.state != STATE_UNAVAILABLE
    update = hass.states.get(ENTITY_ID)
    assert update is not None
    assert update.state == STATE_UNAVAILABLE


async def test_unavailable_when_camera_list_is_stale(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed camera list refresh makes the firmware entity unavailable."""
    await setup_integration(hass, mock_config_entry)

    mock_list_cameras.side_effect = BoschCameraConnectionError("down")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_update_failure_makes_entity_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_firmware_status: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the entity becomes unavailable while the firmware cannot be read."""
    await setup_integration(hass, mock_config_entry)

    mock_get_firmware_status.side_effect = BoschCameraConnectionError("down")
    freezer.tick(FIRMWARE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_camera_added_and_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test cameras appearing and disappearing from the account."""
    other = replace(CAMERAS[0], id="22222222-2222-2222-2222-222222222222", title="Hall")
    await setup_integration(hass, mock_config_entry)

    mock_list_cameras.return_value = [*CAMERAS, other]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # The new camera has no firmware status before the next firmware refresh.
    state = hass.states.get("update.hall_firmware")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    freezer.tick(FIRMWARE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("update.hall_firmware")
    assert state is not None
    assert state.state == STATE_OFF

    mock_list_cameras.return_value = list(CAMERAS)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("update.hall_firmware")
    assert state is None or state.state == STATE_UNAVAILABLE


async def test_installed_version_follows_camera_list(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a new firmware version shows up without a firmware refresh."""
    await setup_integration(hass, mock_config_entry)

    mock_list_cameras.return_value = [replace(CAMERAS[0], firmware_version="9.40.30")]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["installed_version"] == "9.40.30"


async def test_firmware_poll_uses_shared_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_firmware_status: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the firmware poll takes its token from the camera coordinator."""
    await setup_integration(hass, mock_config_entry)

    with patch.object(
        mock_config_entry.runtime_data,
        "async_get_access_token",
        AsyncMock(return_value="shared-token"),
    ) as mock_token:
        freezer.tick(FIRMWARE_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    mock_token.assert_awaited()
    assert mock_get_firmware_status.await_args.args[1] == "shared-token"
