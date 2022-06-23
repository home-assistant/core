"""Tests of the initialization of the venstar integration."""
from unittest.mock import patch

from homeassistant.components.venstar.const import DOMAIN as VENSTAR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_SSL
from homeassistant.core import HomeAssistant

from . import VenstarColorTouchMock

from tests.common import MockConfigEntry

TEST_HOST = "venstartest.localdomain"


async def test_setup_entry(hass: HomeAssistant):
    """Validate that setup entry also configure the client."""
    config_entry = MockConfigEntry(
        domain=VENSTAR_DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_SSL: False,
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.venstar.VenstarColorTouch._request",
        new=VenstarColorTouchMock._request,
    ), patch(
        "homeassistant.components.venstar.VenstarColorTouch.update_sensors",
        new=VenstarColorTouchMock.update_sensors,
    ), patch(
        "homeassistant.components.venstar.VenstarColorTouch.update_info",
        new=VenstarColorTouchMock.update_info,
    ), patch(
        "homeassistant.components.venstar.VenstarColorTouch.update_alerts",
        new=VenstarColorTouchMock.update_alerts,
    ), patch(
        "homeassistant.components.venstar.VenstarColorTouch.get_runtimes",
        new=VenstarColorTouchMock.get_runtimes,
    ), patch(
        "homeassistant.components.venstar.VENSTAR_SLEEP",
        new=0,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_setup_entry_exception(hass: HomeAssistant):
    """Validate that setup entry also configure the client."""
    config_entry = MockConfigEntry(
        domain=VENSTAR_DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_SSL: False,
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.venstar.VenstarColorTouch._request",
        new=VenstarColorTouchMock._request,
    ), patch(
        "homeassistant.components.venstar.VenstarColorTouch.update_sensors",
        new=VenstarColorTouchMock.update_sensors,
    ), patch(
        "homeassistant.components.venstar.VenstarColorTouch.update_info",
        new=VenstarColorTouchMock.broken_update_info,
    ), patch(
        "homeassistant.components.venstar.VenstarColorTouch.update_alerts",
        new=VenstarColorTouchMock.update_alerts,
    ), patch(
        "homeassistant.components.venstar.VenstarColorTouch.get_runtimes",
        new=VenstarColorTouchMock.get_runtimes,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_RETRY
