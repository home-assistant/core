"""Test Scrape component setup process."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.scrape.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import MockRestData, return_integration_config

TEST_CONFIG = {
    "resource": "https://www.home-assistant.io",
    "name": "Release",
    "select": ".current-version h1",
    "value_template": "{{ value.split(':')[1] }}",
    "index": 0,
    "verify_ssl": True,
}


async def test_setup_config(hass: HomeAssistant) -> None:
    """Test setup from yaml."""
    config = {
        "scrape": [
            return_integration_config(select=".current-version h1", name="HA version")
        ]
    }

    mocker = MockRestData("test_scrape_sensor")
    with patch(
        "homeassistant.components.rest.RestData",
        return_value=mocker,
    ) as mock_setup:
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_version")
    assert state.state == "Current Version: 2021.12.10"

    assert len(mock_setup.mock_calls) == 1


async def test_setup_no_data_fails(hass: HomeAssistant) -> None:
    """Test setup entry no data fails."""
    config = {
        "scrape": [
            return_integration_config(select=".current-version h1", name="HA version"),
        ]
    }

    with patch(
        "homeassistant.components.scrape.coordinator.RestData",
        return_value=MockRestData("test_scrape_sensor_no_data"),
    ):
        assert not await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.ha_version")
    assert state is None


async def test_setup_config_no_configuration(hass: HomeAssistant) -> None:
    """Test setup from yaml missing configuration options."""
    config = {"scrape": None}

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    entities = er.async_get(hass)
    assert entities.entities == {}
