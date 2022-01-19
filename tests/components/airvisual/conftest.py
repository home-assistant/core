"""Define test fixtures for AirVisual."""
from unittest.mock import patch

import pytest

from homeassistant.components.airvisual.const import DOMAIN
from homeassistant.const import CONF_SHOW_ON_MAP
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config, unique_id):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        data=config,
        options={CONF_SHOW_ON_MAP: True},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {}


@pytest.fixture(name="setup_airvisual")
async def setup_airvisual_fixture(hass, config):
    """Define a fixture to set up AirVisual."""
    with patch("pyairvisual.air_quality.AirQuality.city"), patch(
        "pyairvisual.air_quality.AirQuality.nearest_city"
    ), patch("pyairvisual.node.NodeSamba.async_connect"), patch(
        "pyairvisual.node.NodeSamba.async_get_latest_measurements"
    ), patch(
        "pyairvisual.node.NodeSamba.async_disconnect"
    ), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="unique_id")
def unique_id_fixture(hass):
    """Define a config entry unique ID fixture."""
    return "51.528308, -0.3817765"
