"""Define test fixtures for Tile."""
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.tile.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

TILE_UUID = "tile_123"


@pytest.fixture(name="api")
def api_fixture(hass):
    """Define a pytile API object."""
    tile = Mock(
        accuracy=20,
        altitude=1000,
        dead=False,
        latitude=51.528308,
        longitude=-0.3817765,
        lost=False,
        lost_timestamp=datetime(2022, 1, 1, 0, 0, 0),
        ring_state="STOPPED",
        uuid=TILE_UUID,
        voip_state="OFFLINE",
        async_update=AsyncMock(),
    )
    tile.name = "Tile 123"

    return Mock(async_get_tiles=AsyncMock(return_value={TILE_UUID: tile}))


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config, unique_id):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data=config)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_USERNAME: "user@host.com",
        CONF_PASSWORD: "123abc",
    }


@pytest.fixture(name="setup_tile")
async def setup_tile_fixture(hass, api, config):
    """Define a fixture to set up Tile."""
    with patch(
        "homeassistant.components.tile.config_flow.async_login", return_value=api
    ), patch("homeassistant.components.tile.async_login", return_value=api), patch(
        "homeassistant.components.tile.PLATFORMS", []
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="unique_id")
def unique_id_fixture(hass):
    """Define a config entry unique ID fixture."""
    return "user@host.com"
