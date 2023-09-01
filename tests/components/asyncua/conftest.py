"""template conftest."""
from typing import Any
from unittest import mock

import pytest

from homeassistant.components.asyncua.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_mock_service


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "asyncua")


@pytest.fixture
async def start_ha(hass, count, domain, config, caplog):
    """Do setup of integration."""
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


@pytest.fixture
async def caplog_setup_text(caplog):
    """Return setup log of integration."""
    return caplog.text


@pytest.fixture
@mock.patch("homeassistant.components.asyncua.OpcuaHub.get_values")
async def setup_asyncua_coordinator(
    mock_hub_get_values: dict[str, Any],
    hass: HomeAssistant,
) -> None:
    """Set up asyncua hub and coordinator for asyncua sensors integration."""

    mock_hub_get_values.return_value = {"mock_sensor_01": 99}
    await async_setup_component(
        hass=hass,
        domain=DOMAIN,
        config={
            DOMAIN: {
                "name": "mock-hub",
                "url": "opc.tcp://mock-url:mock-port",
                "scan_interval": 30,
            }
        },
    )
    await hass.async_block_till_done()
