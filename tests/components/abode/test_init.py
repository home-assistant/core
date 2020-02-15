"""Tests for the Abode module."""
import abodepy.helpers.constants as CONST

import homeassistant.components.abode as abode
from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN

from .common import setup_platform


async def test_abode_setup_from_config(hass, requests_mock):
    """Test setup from configuration yaml file."""
    config = {"abode": {"username": "foo", "password": "bar", "polling": True}}
    response = await abode.async_setup(hass, config)
    assert response


async def test_change_settings(hass, requests_mock):
    """Test change_setting service."""
    await setup_platform(hass, ALARM_DOMAIN)
    requests_mock.put(CONST.SOUNDS_URL, text="")

    await hass.services.async_call(
        "abode",
        "change_setting",
        {"setting": "confirm_snd", "value": "loud"},
        blocking=True,
    )
    await hass.async_block_till_done()
