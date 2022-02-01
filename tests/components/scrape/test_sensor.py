"""The tests for the Scrape sensor platform."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from . import RETURN_HA_VER

DOMAIN = "scrape"


async def test_init(hass: HomeAssistant) -> None:
    """Test initialize sensor."""
    config = {
        "scrape": {
            "test": {
                "resource": "https://www.home-assistant.io",
                "select": ".current-version h1",
                "value_template": "{{ value.split(':')[1] }}",
                "name": "HA version",
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.scrape.sensor.RestData", return_value=RETURN_HA_VER
    ):
        state = hass.states.get("sensor.ha_version")
        assert state.state == "2021.12.10"
