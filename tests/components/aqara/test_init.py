"""Tests for the aqara module."""
from http import HTTPStatus
from unittest.mock import patch
import aqara_iot.openmq
from .common import mock_start

# from aqara.exceptions import aqaraAuthenticationException, AbodeException

from homeassistant import data_entry_flow
from homeassistant.components.aqara import (
    DOMAIN as aqara_DOMAIN,
    # SERVICE_CAPTURE_IMAGE,
    # SERVICE_SETTINGS,
    # SERVICE_TRIGGER_AUTOMATION,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_change_settings(hass: HomeAssistant) -> None:
    """Test change_setting service."""
    await setup_platform(hass, SWITCH_DOMAIN)

    # with patch("aqarapy.aqara.set_setting") as mock_set_setting:
    #     await hass.services.async_call(
    #         aqara_DOMAIN,
    #         SERVICE_SETTINGS,
    #         {"setting": "confirm_snd", "value": "loud"},
    #         blocking=True,
    #     )
    #     await hass.async_block_till_done()
    #     mock_set_setting.assert_called_once()


async def test_add_unique_id(hass: HomeAssistant) -> None:
    """Test unique_id is set to aqara username."""
    # mock_entry = await setup_platform(hass, SWITCH_DOMAIN)
    # Set unique_id to None to match previous config entries
    # hass.config_entries.async_update_entry(entry=mock_entry, unique_id=None)
    # await hass.async_block_till_done()

    # assert mock_entry.unique_id is None

    # with patch("aqarapy.UTILS"):
    #     await hass.config_entries.async_reload(mock_entry.entry_id)
    #     await hass.async_block_till_done()

    # assert mock_entry.unique_id == mock_entry.data[CONF_USERNAME]


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the aqara entry."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        mock_entry = await setup_platform(hass, SWITCH_DOMAIN)

        # with patch("aqarapy.aqara.logout") as mock_logout, patch(
        #     "aqarapy.event_controller.aqaraEventController.stop"
        # ) as mock_events_stop:
        # assert await hass.config_entries.async_unload(mock_entry.entry_id)
        # mock_logout.assert_called_once()
        # mock_events_stop.assert_called_once()


async def test_invalid_credentials(hass: HomeAssistant) -> None:
    """Test aqara credentials changing."""
    # with patch(
    #     "homeassistant.components.aqara.aqara",
    #     side_effect=aqaraAuthenticationException(
    #         (HTTPStatus.BAD_REQUEST, "auth error")
    #     ),
    # ), patch(
    #     "homeassistant.components.aqara.config_flow.aqaraFlowHandler.async_step_reauth",
    #     return_value={"type": data_entry_flow.RESULT_TYPE_FORM},
    # ) as mock_async_step_reauth:
    #     await setup_platform(hass, SWITCH_DOMAIN)

    #     mock_async_step_reauth.assert_called_once()


async def test_raise_config_entry_not_ready_when_offline(hass: HomeAssistant) -> None:
    """Config entry state is SETUP_RETRY when aqara is offline."""
    # with patch(
    #     "homeassistant.components.aqara.aqara",
    #     side_effect=aqaraException("any"),
    # ):
    #     config_entry = await setup_platform(hass, SWITCH_DOMAIN)
    #     await hass.async_block_till_done()

    # assert config_entry.state is ConfigEntryState.SETUP_RETRY

    # assert hass.config_entries.flow.async_progress() == []
