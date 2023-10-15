"""Test script intents."""
from homeassistant.components.script import intent as script_intent
from homeassistant.config import DEFAULT_SCRIPTS
from homeassistant.const import SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml

from tests.common import async_mock_service


async def test_bedtime_intent_not_found(hass: HomeAssistant) -> None:
    """Test HassBedtime intent."""
    await script_intent.async_setup_intents(hass)

    response = await intent.async_handle(hass, "test", "HassBedtime")
    await hass.async_block_till_done()

    assert response.speech["plain"]["speech"] == "Script not found"


async def test_bedtime_intent(hass: HomeAssistant) -> None:
    """Test HassBedtime intent."""
    await script_intent.async_setup_intents(hass)

    assert await async_setup_component(
        hass, "script", {"script": yaml.parse_yaml(DEFAULT_SCRIPTS)}
    )

    hass.states.async_set("light.random", "on")
    calls = async_mock_service(hass, "light", SERVICE_TURN_OFF)

    response = await intent.async_handle(hass, "test", "HassBedtime")
    await hass.async_block_till_done()

    assert response.speech["plain"]["speech"] == "Goodnight"
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "light"
    assert call.service == "turn_off"
    assert call.data == {}
