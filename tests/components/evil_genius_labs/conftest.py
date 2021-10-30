"""Test helpers for Evil Genius Labs."""
import json
import pathlib
from unittest.mock import patch

import pytest

from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture(scope="session")
def data_fixture():
    """Fixture data."""
    data = json.loads(
        (pathlib.Path(__file__).parent / "evil-genius-labs-data.json").read_text()
    )

    return {item["name"]: item for item in data}


@pytest.fixture(scope="session")
def info_fixture():
    """Fixture info."""
    return json.loads(
        (pathlib.Path(__file__).parent / "evil-genius-labs-info.json").read_text()
    )


@pytest.fixture
async def setup_evil_genius_labs(hass, data_fixture, info_fixture, platforms):
    """Test up Evil Genius Labs instance."""
    MockConfigEntry(
        domain="evil_genius_labs", data={"host": "192.168.1.113"}
    ).add_to_hass(hass)
    with patch(
        "pyevilgenius.EvilGeniusDevice.get_data",
        return_value=data_fixture,
    ), patch(
        "pyevilgenius.EvilGeniusDevice.get_info",
        return_value=info_fixture,
    ):
        assert await async_setup_component(hass, "evil_genius_labs", {})
        await hass.async_block_till_done()
        yield
