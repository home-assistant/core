"""Tests for the Airzone integration."""

from homeassistant.components.airzone import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import mock_aiohttp_client

CONFIG = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 3000,
}


def airzone_requests_mock(mock):
    """Mock requests performed to Airzone Local API."""

    hvac_fixture = "airzone/hvac.json"

    mock.post(
        f"http://{CONFIG[CONF_HOST]}:{CONFIG[CONF_PORT]}/api/v1/hvac",
        text=load_fixture(hvac_fixture),
    )


async def async_init_integration(
    hass: HomeAssistant,
):
    """Set up the Airzone integration in Home Assistant."""

    with mock_aiohttp_client() as _m:
        airzone_requests_mock(_m)

        entry = MockConfigEntry(domain=DOMAIN, data=CONFIG)
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
