"""Tests for the HDMI-CEC component."""

from collections.abc import Callable, Coroutine, Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.hdmi_cec import DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

type CecEntityCreator = Callable[..., Coroutine[Any, Any, None]]
type HDMINetworkCreator = Callable[..., Coroutine[Any, Any, MagicMock]]


@pytest.fixture(name="mock_cec_adapter", autouse=True)
def mock_cec_adapter_fixture() -> Generator[MagicMock]:
    """Mock CecAdapter.

    Always mocked as it imports the `cec` library which is part of `libcec`.
    """
    with patch(
        "homeassistant.components.hdmi_cec.CecAdapter", autospec=True
    ) as mock_cec_adapter:
        yield mock_cec_adapter


@pytest.fixture(name="mock_hdmi_network")
def mock_hdmi_network_fixture() -> Generator[MagicMock]:
    """Mock HDMINetwork."""
    with patch(
        "homeassistant.components.hdmi_cec.HDMINetwork", autospec=True
    ) as mock_hdmi_network:
        yield mock_hdmi_network


@pytest.fixture
def create_hdmi_network(
    hass: HomeAssistant, mock_hdmi_network: MagicMock
) -> HDMINetworkCreator:
    """Create an initialized mock hdmi_network."""

    async def hdmi_network(config=None):
        if not config:
            config = {}
        await async_setup_component(hass, DOMAIN, {DOMAIN: config})

        mock_hdmi_network_instance = mock_hdmi_network.return_value

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()
        return mock_hdmi_network_instance

    return hdmi_network


@pytest.fixture
def create_cec_entity(hass: HomeAssistant) -> CecEntityCreator:
    """Create a CecEntity."""

    async def cec_entity(hdmi_network, device):
        new_device_callback = hdmi_network.set_new_device_callback.call_args.args[0]
        new_device_callback(device)
        await hass.async_block_till_done()

    return cec_entity
