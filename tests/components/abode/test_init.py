"""Tests for the Abode module."""

from http import HTTPStatus
from unittest.mock import patch

from jaraco.abode.exceptions import (
    AuthenticationException as AbodeAuthenticationException,
    Exception as AbodeException,
)

from homeassistant.components.abode import (
    DOMAIN as ABODE_DOMAIN,
    SERVICE_CAPTURE_IMAGE,
    SERVICE_SETTINGS,
    SERVICE_TRIGGER_AUTOMATION,
)
from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import setup_platform


async def test_change_settings(hass: HomeAssistant) -> None:
    """Test change_setting service."""
    await setup_platform(hass, ALARM_DOMAIN)

    with patch("jaraco.abode.client.Client.set_setting") as mock_set_setting:
        await hass.services.async_call(
            ABODE_DOMAIN,
            SERVICE_SETTINGS,
            {"setting": "confirm_snd", "value": "loud"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_setting.assert_called_once()


async def test_add_unique_id(hass: HomeAssistant) -> None:
    """Test unique_id is set to Abode username."""
    mock_entry = await setup_platform(hass, ALARM_DOMAIN)
    # Set unique_id to None to match previous config entries
    hass.config_entries.async_update_entry(entry=mock_entry, unique_id=None)
    await hass.async_block_till_done()

    assert mock_entry.unique_id is None

    await hass.config_entries.async_reload(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.unique_id == mock_entry.data[CONF_USERNAME]


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the Abode entry."""
    mock_entry = await setup_platform(hass, ALARM_DOMAIN)

    with (
        patch("jaraco.abode.client.Client.logout") as mock_logout,
        patch("jaraco.abode.event_controller.EventController.stop") as mock_events_stop,
    ):
        assert await hass.config_entries.async_unload(mock_entry.entry_id)
        mock_logout.assert_called_once()
        mock_events_stop.assert_called_once()

        assert not hass.services.has_service(ABODE_DOMAIN, SERVICE_SETTINGS)
        assert not hass.services.has_service(ABODE_DOMAIN, SERVICE_CAPTURE_IMAGE)
        assert not hass.services.has_service(ABODE_DOMAIN, SERVICE_TRIGGER_AUTOMATION)


async def test_invalid_credentials(hass: HomeAssistant) -> None:
    """Test Abode credentials changing."""
    with (
        patch(
            "homeassistant.components.abode.Abode",
            side_effect=AbodeAuthenticationException(
                (HTTPStatus.BAD_REQUEST, "auth error")
            ),
        ),
        patch(
            "homeassistant.components.abode.config_flow.AbodeFlowHandler.async_step_reauth",
            return_value={
                "type": FlowResultType.FORM,
                "flow_id": "mock_flow",
                "step_id": "reauth_confirm",
            },
        ) as mock_async_step_reauth,
    ):
        await setup_platform(hass, ALARM_DOMAIN)

        mock_async_step_reauth.assert_called_once()


async def test_raise_config_entry_not_ready_when_offline(hass: HomeAssistant) -> None:
    """Config entry state is SETUP_RETRY when abode is offline."""
    with patch(
        "homeassistant.components.abode.Abode",
        side_effect=AbodeException("any"),
    ):
        config_entry = await setup_platform(hass, ALARM_DOMAIN)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    assert hass.config_entries.flow.async_progress() == []
