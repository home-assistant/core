"""Tests for the HDMI-CEC component."""
from unittest.mock import patch

import pytest

from homeassistant.components.hdmi_cec import DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def MockCecAdapter():
    """Mock CecAdapter.

    Always mocked as it imports the `cec` library which is part of `libcec`.
    """
    with patch(
        "homeassistant.components.hdmi_cec.CecAdapter", autospec=True
    ) as MockCecAdapter:
        yield MockCecAdapter


@pytest.fixture
def MockHDMINetwork():
    """Mock HDMINetwork."""
    with patch(
        "homeassistant.components.hdmi_cec.HDMINetwork", autospec=True
    ) as MockHDMINetwork:
        yield MockHDMINetwork


@pytest.fixture
def create_hdmi_network(hass, MockHDMINetwork):
    """Create an initialized mock hdmi_network."""

    async def hdmi_network(config=None):
        if not config:
            config = {}
        await async_setup_component(hass, DOMAIN, {DOMAIN: config})

        mock_hdmi_network = MockHDMINetwork.return_value

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        return mock_hdmi_network

    return hdmi_network


@pytest.fixture
def create_cec_entity(hass):
    """Create a CecEntity."""

    async def cec_entity(hdmi_network, device):
        new_device_callback = hdmi_network.set_new_device_callback.call_args.args[0]
        new_device_callback(device)
        await hass.async_block_till_done()

    return cec_entity
