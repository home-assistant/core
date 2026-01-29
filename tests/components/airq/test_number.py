"""Test the NUMBER platform from air-Q integration."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import setup_platform
from .common import TEST_BRIGHTNESS, TEST_DEVICE_INFO

ENTITY_ID = f"number.{TEST_DEVICE_INFO['name']}_led_brightness"


@pytest.fixture(autouse=True)
async def number_platform(hass: HomeAssistant, mock_airq: AsyncMock) -> None:
    """Configure AirQ integration and validate the setup for NUMBER platform."""
    await setup_platform(hass, Platform.NUMBER)

    # Validate the setup
    state = hass.states.get(ENTITY_ID)
    assert state is not None, (
        f"{ENTITY_ID} not found among {hass.states.async_entity_ids()}"
    )
    assert float(state.state) == TEST_BRIGHTNESS


@pytest.mark.parametrize("new_brightness", [0, 100, (TEST_BRIGHTNESS + 10) % 100])
async def test_number_set_value(
    hass: HomeAssistant, mock_airq: AsyncMock, new_brightness
) -> None:
    """Test that setting value works."""
    # Simulate the device confirming the new brightness on the next poll
    mock_airq.get_current_brightness.return_value = new_brightness

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": ENTITY_ID, "value": new_brightness},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify the API methods were called correctly
    mock_airq.set_current_brightness.assert_called_once_with(new_brightness)

    # Validate that the update propagated to the state
    state = hass.states.get(ENTITY_ID)
    assert state is not None, (
        f"{ENTITY_ID} not found among {hass.states.async_entity_ids()}"
    )
    assert float(state.state) == new_brightness


@pytest.mark.parametrize("new_brightness", [-1, 110])
async def test_number_set_invalid_value_caught_by_hass(
    hass: HomeAssistant, mock_airq: AsyncMock, new_brightness
) -> None:
    """Test that setting incorrect values errors."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": ENTITY_ID, "value": new_brightness},
            blocking=True,
        )

    mock_airq.set_current_brightness.assert_not_called()
