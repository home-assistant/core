"""Test the Bosch Smart Camera button platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from bosch_shc_camera_client.actions import ActionResult
from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    SERVICE_PRESS,
    ButtonDeviceClass,
)
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import CAMERA_ID, CAMERAS

pytestmark = pytest.mark.usefixtures("setup_credentials")

ENTITY_ID = "button.garden_restart"


async def _press(hass: HomeAssistant) -> None:
    """Press the restart button."""
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )


@pytest.fixture
async def enabled_entry(
    hass: HomeAssistant,
    setup_credentials: None,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> MockConfigEntry:
    """Set up the integration with the restart button enabled."""
    await setup_integration(hass, mock_config_entry)
    entity_registry.async_update_entity(ENTITY_ID, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


async def test_restart_button_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the restart button is registered but disabled."""
    await setup_integration(hass, mock_config_entry)

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == f"{CAMERA_ID}_restart"
    assert entry.original_device_class is ButtonDeviceClass.RESTART
    assert entry.entity_category is EntityCategory.CONFIG
    assert entry.disabled
    assert hass.states.get(ENTITY_ID) is None


@pytest.mark.usefixtures("enabled_entry")
async def test_restart(hass: HomeAssistant, mock_soft_reset: AsyncMock) -> None:
    """Test pressing the button restarts the camera."""
    await _press(hass)

    assert mock_soft_reset.call_args.args[1:] == ("fake-access-token", CAMERA_ID)


@pytest.mark.usefixtures("enabled_entry")
@pytest.mark.parametrize(
    ("side_effect", "return_value"),
    [
        (None, ActionResult(ok=False, status=404)),
        (BoschCameraConnectionError, ActionResult(ok=True, status=204)),
    ],
)
async def test_restart_failure(
    hass: HomeAssistant,
    mock_soft_reset: AsyncMock,
    side_effect: type[Exception] | None,
    return_value: ActionResult,
) -> None:
    """Test a rejected or failed restart raises."""
    mock_soft_reset.side_effect = side_effect
    mock_soft_reset.return_value = return_value

    with pytest.raises(HomeAssistantError, match="Unable to restart"):
        await _press(hass)


async def test_restart_auth_error(
    hass: HomeAssistant, enabled_entry: MockConfigEntry, mock_soft_reset: AsyncMock
) -> None:
    """Test a rejected token starts reauthentication."""
    mock_soft_reset.side_effect = BoschCameraAuthError("rejected", status=401)

    with (
        patch.object(enabled_entry, "async_start_reauth") as mock_reauth,
        pytest.raises(HomeAssistantError, match="sign in again"),
    ):
        await _press(hass)

    mock_reauth.assert_called_once_with(hass)


@pytest.mark.usefixtures("enabled_entry")
async def test_button_follows_camera_in_account(
    hass: HomeAssistant,
    mock_list_cameras: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the button goes away with its camera and returns with it."""
    mock_list_cameras.return_value = []
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entity_registry.async_get(ENTITY_ID) is None

    mock_list_cameras.return_value = list(CAMERAS)
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert entity_registry.async_get(ENTITY_ID) is not None
