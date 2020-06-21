"""Tests for the Abode module."""
from homeassistant.components.abode import (
    DOMAIN as ABODE_DOMAIN,
    SERVICE_CAPTURE_IMAGE,
    SERVICE_SETTINGS,
    SERVICE_TRIGGER_AUTOMATION,
)
from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN

from .common import setup_platform

from tests.async_mock import patch


async def test_change_settings(hass):
    """Test change_setting service."""
    await setup_platform(hass, ALARM_DOMAIN)

    with patch("abodepy.Abode.set_setting") as mock_set_setting:
        await hass.services.async_call(
            ABODE_DOMAIN,
            SERVICE_SETTINGS,
            {"setting": "confirm_snd", "value": "loud"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_setting.assert_called_once()


async def test_unload_entry(hass):
    """Test unloading the Abode entry."""
    mock_entry = await setup_platform(hass, ALARM_DOMAIN)

    with patch("abodepy.Abode.logout") as mock_logout, patch(
        "abodepy.event_controller.AbodeEventController.stop"
    ) as mock_events_stop:
        assert await hass.config_entries.async_unload(mock_entry.entry_id)
        mock_logout.assert_called_once()
        mock_events_stop.assert_called_once()

        assert not hass.services.has_service(ABODE_DOMAIN, SERVICE_SETTINGS)
        assert not hass.services.has_service(ABODE_DOMAIN, SERVICE_CAPTURE_IMAGE)
        assert not hass.services.has_service(ABODE_DOMAIN, SERVICE_TRIGGER_AUTOMATION)
