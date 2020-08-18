"""Tests for tag triggers."""

import pytest

import homeassistant.components.automation as automation
from homeassistant.components.tag.const import DOMAIN, EVENT_TAG_SCANNED, TAG_ID
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_triggers(hass, calls):
    """Test tag triggers."""

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": DOMAIN, TAG_ID: "abc123"},
                    "action": {
                        "service": "test.automation",
                        "data": {"message": "service called"},
                    },
                }
            ]
        },
    )

    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_TAG_SCANNED, {TAG_ID: "abc123"})
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["message"] == "service called"


async def test_exception_bad_trigger(hass, calls, caplog):
    """Test for exception on event triggers firing."""

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"trigger": {"platform": DOMAIN, "oops": "abc123"}},
                    "action": {
                        "service": "test.automation",
                        "data": {"message": "service called"},
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert "Invalid config for [automation]" in caplog.text
