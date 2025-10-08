"""Test reproduce state for Input Weekday."""

import pytest

from homeassistant.components.input_weekday import ATTR_WEEKDAYS, DOMAIN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


@pytest.fixture
async def setup_component(hass: HomeAssistant):
    """Set up component."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"test_weekday": {"weekdays": []}}}
    )


async def test_reproduce_weekday(hass: HomeAssistant) -> None:
    """Test reproduce weekday."""
    calls = async_mock_service(hass, DOMAIN, "set_weekdays")

    await async_reproduce_state(
        hass,
        [
            State(
                "input_weekday.test_weekday",
                "mon,wed,fri",
                {ATTR_WEEKDAYS: ["mon", "wed", "fri"]},
            )
        ],
    )

    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {
        "entity_id": "input_weekday.test_weekday",
        ATTR_WEEKDAYS: ["mon", "wed", "fri"],
    }


async def test_reproduce_weekday_missing_attribute(
    hass: HomeAssistant, setup_component, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproduce weekday with missing weekdays attribute."""
    calls = async_mock_service(hass, DOMAIN, "set_weekdays")

    await async_reproduce_state(
        hass,
        [State("input_weekday.test_weekday", "mon,wed")],
    )

    await hass.async_block_till_done()

    assert len(calls) == 0
    assert "weekdays attribute is missing" in caplog.text
