"""Test the Bosch Smart Camera switch platform."""

from unittest.mock import AsyncMock

from bosch_shc_camera_client.cameras import BoschCameraConnectionError
from bosch_shc_camera_client.cloud import CloudPutResult
from bosch_shc_camera_client.states import CameraAccountStates
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
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
from .conftest import CAMERA_ID

pytestmark = pytest.mark.usefixtures("setup_credentials")

ENTITY_ID = "switch.garden_privacy_mode"


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
