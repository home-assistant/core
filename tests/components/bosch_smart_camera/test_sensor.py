"""Test the Bosch Smart Camera sensor platform."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
    BoschCameraInvalidResponseError,
)
from bosch_shc_camera_client.states import WifiInfo
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bosch_smart_camera.coordinator import WIFI_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import CAMERA_ID, CAMERAS

pytestmark = pytest.mark.usefixtures("setup_credentials")

ENTITY_ID = "sensor.garden_wi_fi_signal_strength"
OTHER_ID = "22222222-2222-2222-2222-222222222222"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensor entities."""
    with patch(
        "homeassistant.components.bosch_smart_camera.PLATFORMS", [Platform.SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the signal strength sensor is disabled by default."""
    await setup_integration(hass, mock_config_entry)

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(ENTITY_ID) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_value_updates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_wifi_info: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensor follows the reported signal strength."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == "72"
    assert mock_get_wifi_info.await_args.args[1:] == ("fake-access-token", CAMERA_ID)

    mock_get_wifi_info.return_value = WifiInfo(signal_strength=None)
    freezer.tick(WIFI_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "error", [BoschCameraConnectionError, BoschCameraInvalidResponseError]
)
async def test_update_failure_makes_sensor_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_wifi_info: AsyncMock,
    freezer: FrozenDateTimeFactory,
    error: type[Exception],
) -> None:
    """Test a failing update makes the sensor unavailable until it recovers."""
    await setup_integration(hass, mock_config_entry)

    mock_get_wifi_info.side_effect = error
    freezer.tick(WIFI_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_get_wifi_info.side_effect = None
    freezer.tick(WIFI_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "72"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_first_refresh_failure_keeps_setup_alive(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_wifi_info: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failing first refresh only makes the sensor unavailable."""
    mock_get_wifi_info.side_effect = BoschCameraConnectionError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_get_wifi_info.side_effect = None
    freezer.tick(WIFI_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "72"


async def test_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_wifi_info: AsyncMock,
) -> None:
    """Test a rejected token asks the user to sign in again."""
    mock_get_wifi_info.side_effect = BoschCameraAuthError

    with patch.object(
        mock_config_entry, "async_start_reauth_if_available"
    ) as mock_start_reauth:
        await setup_integration(hass, mock_config_entry)

    assert mock_start_reauth.called


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_camera_added_and_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors follow the camera list of the account."""
    await setup_integration(hass, mock_config_entry)
    other = replace(CAMERAS[0], id=OTHER_ID, title="Hall")

    mock_list_cameras.return_value = [*CAMERAS, other]
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.hall_wi_fi_signal_strength").state == STATE_UNKNOWN

    mock_list_cameras.return_value = [other]
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID) is None
