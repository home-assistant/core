"""Tests for EZVIZ siren entities."""

from unittest.mock import AsyncMock

from pyezvizapi import PyEzvizError, SupportExt
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.siren import DOMAIN as SIREN_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration
from .test_init import _mock_camera_data

ENTITY_ID = "siren.camera_1_siren"


@pytest.fixture(autouse=True)
def mock_siren_camera(mock_ezviz_client: AsyncMock) -> None:
    """Return a camera supporting the siren."""
    mock_ezviz_client.load_cameras.return_value = {
        "C123456789": _mock_camera_data(
            supportExt={str(SupportExt.SupportActiveDefense.value): "1"}
        )
    }


async def test_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test turning on the siren."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SIREN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_ezviz_client.sound_alarm.assert_called_once_with("C123456789", 2)
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_turn_on_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test turning on the siren raises when the API fails."""
    await setup_integration(hass, mock_config_entry)

    def sound_alarm(serial: str, enable: int) -> None:
        raise PyEzvizError

    # A plain function, as the test harness runs Mock executor jobs inline
    mock_ezviz_client.sound_alarm = sound_alarm

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SIREN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )

    assert hass.states.get(ENTITY_ID).state != STATE_ON
