"""The tests for the spencermatic notification platform."""

import spencerassistant.components.notify as notify_comp
from spencerassistant.setup import async_setup_component

from tests.common import assert_setup_component


async def test_setup_full(hass):
    """Test valid configuration."""
    await async_setup_component(
        hass,
        "spencermatic",
        {"spencermatic": {"hosts": {"ccu2": {"host": "127.0.0.1"}}}},
    )
    with assert_setup_component(1) as handle_config:
        assert await async_setup_component(
            hass,
            "notify",
            {
                "notify": {
                    "name": "test",
                    "platform": "spencermatic",
                    "address": "NEQXXXXXXX",
                    "channel": 2,
                    "param": "SUBMIT",
                    "value": "1,1,108000,2",
                    "interface": "my-interface",
                }
            },
        )
    assert handle_config[notify_comp.DOMAIN]


async def test_setup_without_optional(hass):
    """Test valid configuration without optional."""
    await async_setup_component(
        hass,
        "spencermatic",
        {"spencermatic": {"hosts": {"ccu2": {"host": "127.0.0.1"}}}},
    )
    with assert_setup_component(1) as handle_config:
        assert await async_setup_component(
            hass,
            "notify",
            {
                "notify": {
                    "name": "test",
                    "platform": "spencermatic",
                    "address": "NEQXXXXXXX",
                    "channel": 2,
                    "param": "SUBMIT",
                    "value": "1,1,108000,2",
                }
            },
        )
    assert handle_config[notify_comp.DOMAIN]


async def test_bad_config(hass):
    """Test invalid configuration."""
    config = {notify_comp.DOMAIN: {"name": "test", "platform": "spencermatic"}}
    with assert_setup_component(0) as handle_config:
        assert await async_setup_component(hass, notify_comp.DOMAIN, config)
    assert not handle_config[notify_comp.DOMAIN]
