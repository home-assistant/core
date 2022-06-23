"""Tests for the venstar integration."""

import requests_mock

from homeassistant.components.climate.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import load_fixture

TEST_MODELS = ["t2k", "colortouch"]


def mock_venstar_devices(f):
    """Decorate function to mock a Venstar Colortouch and T2000 thermostat API."""

    async def wrapper(hass):
        # Mock thermostats are:
        # Venstar T2000, FW 4.38
        # Venstar "colortouch" T7850, FW 5.1
        with requests_mock.mock() as m:
            for model in TEST_MODELS:
                m.get(
                    f"http://venstar-{model}.localdomain/",
                    text=load_fixture(f"venstar/{model}_root.json"),
                )
                m.get(
                    f"http://venstar-{model}.localdomain/query/info",
                    text=load_fixture(f"venstar/{model}_info.json"),
                )
                m.get(
                    f"http://venstar-{model}.localdomain/query/sensors",
                    text=load_fixture(f"venstar/{model}_sensors.json"),
                )
                m.get(
                    f"http://venstar-{model}.localdomain/query/alerts",
                    text=load_fixture(f"venstar/{model}_alerts.json"),
                )
            return await f(hass)

    return wrapper


async def async_init_integration(
    hass: HomeAssistant,
    skip_setup: bool = False,
):
    """Set up the venstar integration in Home Assistant."""
    platform_config = []
    for model in TEST_MODELS:
        platform_config.append(
            {
                CONF_PLATFORM: "venstar",
                CONF_HOST: f"venstar-{model}.localdomain",
            }
        )
    config = {DOMAIN: platform_config}

    await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
