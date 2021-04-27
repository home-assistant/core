"""Tests for the nexia integration."""
from unittest.mock import patch
import uuid

from nexia.home import NexiaHome
import requests_mock

from homeassistant.components.nexia.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


async def async_init_integration(
    hass: HomeAssistant,
    skip_setup: bool = False,
) -> MockConfigEntry:
    """Set up the nexia integration in Home Assistant."""

    house_fixture = "nexia/mobile_houses_123456.json"
    session_fixture = "nexia/session_123456.json"
    sign_in_fixture = "nexia/sign_in.json"

    with requests_mock.mock() as m, patch(
        "nexia.home.load_or_create_uuid", return_value=uuid.uuid4()
    ):
        m.post(NexiaHome.API_MOBILE_SESSION_URL, text=load_fixture(session_fixture))
        m.get(
            NexiaHome.API_MOBILE_HOUSES_URL.format(house_id=123456),
            text=load_fixture(house_fixture),
        )
        m.post(
            NexiaHome.API_MOBILE_ACCOUNTS_SIGN_IN_URL,
            text=load_fixture(sign_in_fixture),
        )
        entry = MockConfigEntry(
            domain=DOMAIN, data={CONF_USERNAME: "mock", CONF_PASSWORD: "mock"}
        )
        entry.add_to_hass(hass)

        if not skip_setup:
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

    return entry
