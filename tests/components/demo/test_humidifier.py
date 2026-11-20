"""The tests for the demo humidifier component."""

from unittest.mock import patch

import probatio
import pytest

from homeassistant.components.humidifier import (
    DOMAIN as HUMIDITY_DOMAIN,
    MODE_AWAY,
    HumidifierEntityCapabilityAttribute,
    HumidifierEntityStateAttribute,
    HumidifierService,
    HumidifierServiceArgument,
)
from homeassistant.const import ATTR_MODE, STATE_OFF, STATE_ON, Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ENTITY_DEHUMIDIFIER = "humidifier.dehumidifier"
ENTITY_HYGROSTAT = "humidifier.hygrostat"
ENTITY_HUMIDIFIER = "humidifier.humidifier"


@pytest.fixture
async def humidifier_only() -> None:
    """Enable only the datetime platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.HUMIDIFIER],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_demo_humidifier(hass: HomeAssistant, humidifier_only: None):
    """Initialize setup demo humidifier."""
    assert await async_setup_component(
        hass, HUMIDITY_DOMAIN, {"humidifier": {"platform": "demo"}}
    )
    await hass.async_block_till_done()


def test_setup_params(hass: HomeAssistant) -> None:
    """Test the initial parameters."""
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.state == STATE_ON
    assert state.attributes.get(HumidifierEntityStateAttribute.HUMIDITY) == 54.2
    assert state.attributes.get(HumidifierEntityStateAttribute.CURRENT_HUMIDITY) == 59.4
    assert state.attributes.get(HumidifierEntityStateAttribute.ACTION) == "drying"


def test_default_setup_params(hass: HomeAssistant) -> None:
    """Test the setup with default parameters."""
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.attributes.get(HumidifierEntityCapabilityAttribute.MIN_HUMIDITY) == 0
    assert state.attributes.get(HumidifierEntityCapabilityAttribute.MAX_HUMIDITY) == 100


async def test_set_target_humidity_bad_attr(hass: HomeAssistant) -> None:
    """Test setting the target humidity without required attribute."""
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.attributes.get(HumidifierEntityStateAttribute.HUMIDITY) == 54.2

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            HUMIDITY_DOMAIN,
            HumidifierService.SET_HUMIDITY,
            {
                HumidifierServiceArgument.HUMIDITY: None,
                TargetKey.ENTITY_ID: ENTITY_DEHUMIDIFIER,
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.attributes.get(HumidifierEntityStateAttribute.HUMIDITY) == 54.2


async def test_set_target_humidity(hass: HomeAssistant) -> None:
    """Test the setting of the target humidity."""
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.attributes.get(HumidifierEntityStateAttribute.HUMIDITY) == 54.2

    await hass.services.async_call(
        HUMIDITY_DOMAIN,
        HumidifierService.SET_HUMIDITY,
        {
            HumidifierServiceArgument.HUMIDITY: 64,
            TargetKey.ENTITY_ID: ENTITY_DEHUMIDIFIER,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.attributes.get(HumidifierEntityStateAttribute.HUMIDITY) == 64


async def test_set_hold_mode_away(hass: HomeAssistant) -> None:
    """Test setting the hold mode away."""
    await hass.services.async_call(
        HUMIDITY_DOMAIN,
        HumidifierService.SET_MODE,
        {
            HumidifierServiceArgument.MODE: MODE_AWAY,
            TargetKey.ENTITY_ID: ENTITY_HYGROSTAT,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_HYGROSTAT)
    assert state.attributes.get(ATTR_MODE) == MODE_AWAY


async def test_set_hold_mode_eco(hass: HomeAssistant) -> None:
    """Test setting the hold mode eco."""
    await hass.services.async_call(
        HUMIDITY_DOMAIN,
        HumidifierService.SET_MODE,
        {HumidifierServiceArgument.MODE: "eco", TargetKey.ENTITY_ID: ENTITY_HYGROSTAT},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_HYGROSTAT)
    assert state.attributes.get(ATTR_MODE) == "eco"


async def test_turn_on(hass: HomeAssistant) -> None:
    """Test turn on device."""
    await hass.services.async_call(
        HUMIDITY_DOMAIN,
        HumidifierService.TURN_OFF,
        {TargetKey.ENTITY_ID: ENTITY_DEHUMIDIFIER},
        blocking=True,
    )
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.state == STATE_OFF
    assert state.attributes.get(HumidifierEntityStateAttribute.ACTION) == "off"

    await hass.services.async_call(
        HUMIDITY_DOMAIN,
        HumidifierService.TURN_ON,
        {TargetKey.ENTITY_ID: ENTITY_DEHUMIDIFIER},
        blocking=True,
    )
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.state == STATE_ON
    assert state.attributes.get(HumidifierEntityStateAttribute.ACTION) == "drying"


async def test_turn_off(hass: HomeAssistant) -> None:
    """Test turn off device."""
    await hass.services.async_call(
        HUMIDITY_DOMAIN,
        HumidifierService.TURN_ON,
        {TargetKey.ENTITY_ID: ENTITY_DEHUMIDIFIER},
        blocking=True,
    )
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.state == STATE_ON
    assert state.attributes.get(HumidifierEntityStateAttribute.ACTION) == "drying"

    await hass.services.async_call(
        HUMIDITY_DOMAIN,
        HumidifierService.TURN_OFF,
        {TargetKey.ENTITY_ID: ENTITY_DEHUMIDIFIER},
        blocking=True,
    )
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.state == STATE_OFF
    assert state.attributes.get(HumidifierEntityStateAttribute.ACTION) == "off"


async def test_toggle(hass: HomeAssistant) -> None:
    """Test toggle device."""
    await hass.services.async_call(
        HUMIDITY_DOMAIN,
        HumidifierService.TURN_ON,
        {TargetKey.ENTITY_ID: ENTITY_DEHUMIDIFIER},
        blocking=True,
    )
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.state == STATE_ON

    await hass.services.async_call(
        HUMIDITY_DOMAIN,
        HumidifierService.TOGGLE,
        {TargetKey.ENTITY_ID: ENTITY_DEHUMIDIFIER},
        blocking=True,
    )
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        HUMIDITY_DOMAIN,
        HumidifierService.TOGGLE,
        {TargetKey.ENTITY_ID: ENTITY_DEHUMIDIFIER},
        blocking=True,
    )
    state = hass.states.get(ENTITY_DEHUMIDIFIER)
    assert state.state == STATE_ON
