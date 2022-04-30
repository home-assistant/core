"""Test helpers for Evil Genius Labs."""
import json
from unittest.mock import patch

import pytest

from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(scope="session")
def all_fixture():
    """Fixture data."""
    data = json.loads(load_fixture("data.json", "evil_genius_labs"))
    return {item["name"]: item for item in data}


@pytest.fixture(scope="session")
def info_fixture():
    """Fixture info."""
    return json.loads(load_fixture("info.json", "evil_genius_labs"))


@pytest.fixture(scope="session")
def product_fixture():
    """Fixture info."""
    return {"productName": "Fibonacci256"}


@pytest.fixture
def config_entry(hass):
    """Evil genius labs config entry."""
    entry = MockConfigEntry(domain="evil_genius_labs", data={"host": "192.168.1.113"})
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def setup_evil_genius_labs(
    hass, config_entry, all_fixture, info_fixture, product_fixture, platforms
):
    """Test up Evil Genius Labs instance."""
    with patch(
        "pyevilgenius.EvilGeniusDevice.get_all",
        return_value=all_fixture,
    ), patch(
        "pyevilgenius.EvilGeniusDevice.get_info",
        return_value=info_fixture,
    ), patch(
        "pyevilgenius.EvilGeniusDevice.get_product",
        return_value=product_fixture,
    ), patch(
        "homeassistant.components.evil_genius_labs.PLATFORMS", platforms
    ):
        assert await async_setup_component(hass, "evil_genius_labs", {})
        await hass.async_block_till_done()
        yield
