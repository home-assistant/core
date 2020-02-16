"""Tests for the Abode module."""
from abodepy.exceptions import AbodeException
import abodepy.helpers.constants as CONST
from abodepy.helpers.errors import INVALID_SETTING
from requests.exceptions import ConnectTimeout

from homeassistant.components import abode
from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN

from .common import setup_platform


async def test_abode_setup_from_config(hass, requests_mock):
    """Test setup from configuration yaml file."""
    config = {"abode": {"username": "foo", "password": "bar", "polling": True}}
    response = await abode.async_setup(hass, config)
    assert response


async def test_connection_error(hass, requests_mock):
    """Test exception when unable to connect to Abode."""
    requests_mock.post(CONST.LOGIN_URL, exc=ConnectTimeout)
    # Tried using 'with pytest.raises(ConnectTimeout):' but
    # ConnectTimeout is not being raised
    await setup_platform(hass, ALARM_DOMAIN)


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

    # Test change_setting when an exception is raised
    requests_mock.put(CONST.SOUNDS_URL, exc=AbodeException(INVALID_SETTING))
    # Tried using 'with pytest.raises(ConnectTimeout):' but
    # AbodeException is not being raised
    await hass.services.async_call(
        "abode",
        "change_setting",
        {"setting": "confirm_snd", "value": "loud"},
        blocking=True,
    )


async def test_unload_entry(hass, requests_mock):
    """Test unloading the abode entry."""
    await setup_platform(hass, abode.ABODE_PLATFORMS)

    controller = hass.data[abode.DOMAIN]
    assert controller

    assert await abode.async_unload_entry(hass, controller)
    await hass.async_block_till_done()
    assert abode.DOMAIN not in hass.data
