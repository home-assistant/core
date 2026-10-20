"""Test the Bosch Smart Home Camera setup, coordinator and camera platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
    BoschCameraInvalidResponseError,
    Camera,
    CameraModel,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import CAMERA_ID, CAMERAS

pytestmark = pytest.mark.usefixtures("setup_credentials")

ENTITY_ID = "camera.garden"
OTHER_ID = "22222222-2222-2222-2222-222222222222"
OTHER = Camera(OTHER_ID, "Hall", "SOMETHING_NEW", CameraModel.UNKNOWN, None)


async def test_camera_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a camera entity and its device are created from the list."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID).state == "idle"
    assert entity_registry.async_get(ENTITY_ID).unique_id == CAMERA_ID
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, CAMERA_ID), mock_config_entry.entry_id
    )
    assert device.name == "Garden"
    assert device.manufacturer == "Bosch"
    assert device.model == "Eyes Outdoor II"
    assert device.sw_version == "9.40.25"


async def test_unknown_model_uses_hardware_version(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a model outside the known lineup falls back to the raw value."""
    mock_list_cameras.return_value = [OTHER]
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, OTHER_ID), mock_config_entry.entry_id
    )
    assert device.model == "SOMETHING_NEW"
    assert device.sw_version is None


async def test_unload(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test the entry unloads."""
    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (BoschCameraConnectionError, ConfigEntryState.SETUP_RETRY),
        (BoschCameraInvalidResponseError, ConfigEntryState.SETUP_RETRY),
        (BoschCameraAuthError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    error: type[Exception],
    state: ConfigEntryState,
) -> None:
    """Test library errors map to retry or a setup error."""
    mock_list_cameras.side_effect = error
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state


async def test_update_failure_makes_camera_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failing poll marks the camera unavailable and recovers."""
    await setup_integration(hass, mock_config_entry)

    mock_list_cameras.side_effect = BoschCameraConnectionError
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_list_cameras.side_effect = None
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "idle"


async def test_camera_added_and_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test cameras appear and disappear with the account."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("camera.hall") is None

    mock_list_cameras.return_value = [*CAMERAS, OTHER]
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("camera.hall") is not None
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, OTHER_ID), mock_config_entry.entry_id
    )

    mock_list_cameras.return_value = list(CAMERAS)
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("camera.hall") is None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, OTHER_ID), mock_config_entry.entry_id
        )
        is None
    )
    assert hass.states.get(ENTITY_ID).state == "idle"

    mock_list_cameras.return_value = [*CAMERAS, OTHER]
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("camera.hall") is not None


async def test_stale_device_removed_on_startup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a device of a camera removed while Home Assistant was off is dropped."""
    mock_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, OTHER_ID)},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, OTHER_ID), mock_config_entry.entry_id
        )
        is None
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, CAMERA_ID), mock_config_entry.entry_id
    )
