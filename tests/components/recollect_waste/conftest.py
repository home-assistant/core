"""Define test fixtures for ReCollect Waste."""
from datetime import date
from unittest.mock import patch

from aiorecollect.client import PickupEvent, PickupType
import pytest

from homeassistant.components.recollect_waste.const import (
    CONF_PLACE_ID,
    CONF_SERVICE_ID,
    DOMAIN,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


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
        CONF_PLACE_ID: "12345",
        CONF_SERVICE_ID: "12345",
    }


@pytest.fixture(name="setup_recollect_waste")
async def setup_recollect_waste_fixture(hass, config):
    """Define a fixture to set up ReCollect Waste."""
    pickup_event = PickupEvent(
        date(2022, 1, 23), [PickupType("garbage", "Trash Collection")], "The Sun"
    )

    with patch(
        "homeassistant.components.recollect_waste.Client.async_get_pickup_events",
        return_value=[pickup_event],
    ), patch(
        "homeassistant.components.recollect_waste.config_flow.Client.async_get_pickup_events",
        return_value=[pickup_event],
    ), patch(
        "homeassistant.components.recollect_waste.PLATFORMS", []
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="unique_id")
def unique_id_fixture(hass):
    """Define a config entry unique ID fixture."""
    return "12345, 12345"
