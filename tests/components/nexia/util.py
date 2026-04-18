"""Tests for the nexia integration."""

from unittest.mock import patch
import uuid

from nexia.home import NexiaHome

from homeassistant.components.nexia.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_fixture
from tests.test_util.aiohttp import mock_aiohttp_client


async def async_init_integration(
    hass: HomeAssistant,
    skip_setup: bool = False,
    exception: Exception | None = None,
    *,
    house_fixture="mobile_houses_123456.json",
) -> MockConfigEntry:
    """Set up the nexia integration in Home Assistant."""

    session_fixture = "session_123456.json"
    sign_in_fixture = "sign_in.json"
    set_fan_speed_fixture = "set_fan_speed_2293892.json"
    with (
        mock_aiohttp_client() as mock_session,
        patch("nexia.home.load_or_create_uuid", return_value=uuid.uuid4()),
    ):
        nexia = NexiaHome(mock_session)
        if exception:

            async def _raise_exception(*args, **kwargs):
                raise exception

            mock_session.post(
                nexia.API_MOBILE_SESSION_URL, side_effect=_raise_exception
            )
        else:
            mock_session.post(
                nexia.API_MOBILE_SESSION_URL,
                text=await async_load_fixture(hass, session_fixture, DOMAIN),
            )
        mock_session.get(
            nexia.API_MOBILE_HOUSES_URL.format(house_id=123456),
            text=await async_load_fixture(hass, house_fixture, DOMAIN),
        )
        mock_session.post(
            nexia.API_MOBILE_ACCOUNTS_SIGN_IN_URL,
            text=await async_load_fixture(hass, sign_in_fixture, DOMAIN),
        )
        mock_session.post(
            "https://www.mynexia.com/mobile/xxl_thermostats/2293892/fan_speed",
            text=await async_load_fixture(hass, set_fan_speed_fixture, DOMAIN),
        )
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_USERNAME: "mock", CONF_PASSWORD: "mock"},
            minor_version=2,
            unique_id="123456",
        )
        entry.add_to_hass(hass)

        if not skip_setup:
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

    return entry
