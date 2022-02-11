"""The tests for SleepIQ button platform."""
from unittest.mock import patch

from homeassistant.components.button import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import entity_registry as er

from .conftest import setup_platform


async def test_setup(hass, mock_aioresponse):
    """Test for successfully setting up the SleepIQ platform."""
    await setup_platform(hass, DOMAIN)
    entity_registry = er.async_get(hass)

    assert len(entity_registry.entities) == 2

    entry = entity_registry.async_get("button.ile_calibrate")
    assert entry.original_name == "ILE Calibrate"

    entry = entity_registry.async_get("button.ile_stop_pump")
    assert entry.original_name == "ILE Stop Pump"


async def test_button_calibrate_press(hass, mock_aioresponse):
    """Test button press."""
    await setup_platform(hass, DOMAIN)

    with patch("asyncsleepiq.SleepIQBed.calibrate") as mock_calibrate:
        await hass.services.async_call(
            DOMAIN,
            "press",
            {ATTR_ENTITY_ID: "button.ile_calibrate"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_calibrate.assert_called_once()


async def test_button_stop_pump_press(hass, mock_aioresponse):
    """Test button press."""
    await setup_platform(hass, DOMAIN)

    with patch("asyncsleepiq.SleepIQBed.stop_pump") as mock_stop_pump:
        await hass.services.async_call(
            DOMAIN,
            "press",
            {ATTR_ENTITY_ID: "button.ile_stop_pump"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_stop_pump.assert_called_once()
