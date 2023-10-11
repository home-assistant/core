"""The tests for the Pilight binary sensor platform."""
from __future__ import annotations

import logging

import pytest

import homeassistant.components.binary_sensor as binary_sensor
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, mock_component


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, "pilight")


async def test_unique_id(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test the setting of value via pilight."""
    caplog.set_level(logging.ERROR)
    with assert_setup_component(3):
        assert await async_setup_component(
            hass,
            binary_sensor.DOMAIN,
            {
                binary_sensor.DOMAIN: [
                    {
                        "platform": "pilight",
                        "name": "test",
                        "variable": "test",
                        "payload": {"protocol": "test-protocol"},
                        "unique_id": "unique",
                    },
                    {
                        "platform": "pilight",
                        "name": "test",
                        "variable": "test",
                        "payload": {"protocol": "test-protocol"},
                        "unique_id": "not-so-unique",
                    },
                    {
                        "platform": "pilight",
                        "name": "test",
                        "variable": "test",
                        "payload": {"protocol": "test-protocol"},
                        "unique_id": "not-so-unique",
                    },
                ]
            },
        )
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 2

        ent_reg = er.async_get(hass)
        assert len(ent_reg.entities) == 2
        assert (
            ent_reg.async_get_entity_id("binary_sensor", "pilight", "unique")
            is not None
        )
        assert (
            ent_reg.async_get_entity_id("binary_sensor", "pilight", "not-so-unique")
            is not None
        )
