"""Tests for the on/off functionality of VeSync components."""

from contextlib import nullcontext
from unittest.mock import patch

import pytest

from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import ON_OFF_TESTS

from tests.common import MockConfigEntry

NoException = nullcontext()


@pytest.mark.parametrize("platform", ON_OFF_TESTS.keys())
@pytest.mark.parametrize(
    ("api_response", "expectation"),
    [
        (False, pytest.raises(HomeAssistantError)),
        (True, NoException),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    on_off_config_entry: MockConfigEntry,
    api_response: bool,
    expectation,
    platform: str,
) -> None:
    """Test turn_on and turn_off methods."""
    turn_on_func = ON_OFF_TESTS[platform]["turn_on_func"]
    turn_off_func = ON_OFF_TESTS[platform]["turn_off_func"]
    update_func = ON_OFF_TESTS[platform]["update_func"]
    domain = ON_OFF_TESTS[platform]["domain"]
    entity = ON_OFF_TESTS[platform]["entity"]

    # Test turn_on
    with (
        expectation,
        patch(turn_on_func, return_value=api_response) as turn_on_mock,
    ):
        with patch(update_func) as update_mock:
            await hass.services.async_call(
                domain,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: entity},
                blocking=True,
            )

        await hass.async_block_till_done()
        turn_on_mock.assert_called_once()
        update_mock.assert_called_once()

    # Test turn_off
    with (
        expectation,
        patch(turn_off_func, return_value=api_response) as turn_off_mock,
    ):
        with patch(update_func) as update_mock:
            await hass.services.async_call(
                domain,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: entity},
                blocking=True,
            )

        await hass.async_block_till_done()
        turn_off_mock.assert_called_once()
        update_mock.assert_called_once()
