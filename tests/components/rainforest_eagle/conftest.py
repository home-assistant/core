"""Conftest for rainforest_eagle."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.rainforest_eagle.const import (
    CONF_CLOUD_ID,
    CONF_HARDWARE_ADDRESS,
    CONF_INSTALL_CODE,
    DOMAIN,
    TYPE_EAGLE_100,
    TYPE_EAGLE_200,
)
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.setup import async_setup_component

from . import MOCK_200_RESPONSE_WITHOUT_PRICE, MOCK_CLOUD_ID

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry_200(hass):
    """Return a config entry."""
    entry = MockConfigEntry(
        domain="rainforest_eagle",
        data={
            CONF_CLOUD_ID: MOCK_CLOUD_ID,
            CONF_HOST: "192.168.1.55",
            CONF_INSTALL_CODE: "abcdefgh",
            CONF_HARDWARE_ADDRESS: "mock-hw-address",
            CONF_TYPE: TYPE_EAGLE_200,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def setup_rainforest_200(hass, config_entry_200):
    """Set up rainforest."""
    with patch(
        "aioeagle.ElectricMeter.create_instance",
        return_value=Mock(
            get_device_query=AsyncMock(return_value=MOCK_200_RESPONSE_WITHOUT_PRICE)
        ),
    ) as mock_update:
        mock_update.return_value.is_connected = True
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update.return_value


@pytest.fixture
async def setup_rainforest_100(hass):
    """Set up rainforest."""
    MockConfigEntry(
        domain="rainforest_eagle",
        data={
            CONF_CLOUD_ID: MOCK_CLOUD_ID,
            CONF_HOST: "192.168.1.55",
            CONF_INSTALL_CODE: "abcdefgh",
            CONF_HARDWARE_ADDRESS: None,
            CONF_TYPE: TYPE_EAGLE_100,
        },
    ).add_to_hass(hass)
    with patch(
        "homeassistant.components.rainforest_eagle.data.Eagle100Reader",
        return_value=Mock(
            get_instantaneous_demand=Mock(
                return_value={"InstantaneousDemand": {"Demand": "1.152000"}}
            ),
            get_current_summation=Mock(
                return_value={
                    "CurrentSummation": {
                        "SummationDelivered": "45251.285000",
                        "SummationReceived": "232.232000",
                    }
                }
            ),
        ),
    ) as mock_update:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update
