"""The tests for SleepIQ number platform."""
from unittest.mock import MagicMock, patch

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.number.const import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.components.sleepiq import init_integration


async def test_sleepnumber_state(hass: HomeAssistant, requests_mock: MagicMock):
    """Test the SleepIQ sleep numbers for a bed with two sides."""
    await init_integration(hass, requests_mock)

    entity_registry = er.async_get(hass)

    state = hass.states.get("number.sleepnumber_ile_test1_sleepnumber")
    assert state.state == "40"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "SleepNumber ILE Test1 SleepNumber"
    )

    state = hass.states.get("number.sleepnumber_ile_test2_sleepnumber")
    assert state.state == "80"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed-empty"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "SleepNumber ILE Test2 SleepNumber"
    )

    entry = entity_registry.async_get("number.sleepnumber_ile_test1_sleepnumber")
    assert entry
    assert entry.unique_id == "-31_Test1_sleep_number"

    entry = entity_registry.async_get("number.sleepnumber_ile_test2_sleepnumber")
    assert entry
    assert entry.unique_id == "-31_Test2_sleep_number"


async def test_sleepnumber_state_single(hass: HomeAssistant, requests_mock: MagicMock):
    """Test the SleepIQ sleep numbers for a single bed."""
    await init_integration(hass, requests_mock, True)

    entity_registry = er.async_get(hass)

    state = hass.states.get("number.sleepnumber_ile_test1_sleepnumber")
    assert state.state == "40"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "SleepNumber ILE Test1 SleepNumber"
    )

    entry = entity_registry.async_get("number.sleepnumber_ile_test1_sleepnumber")
    assert entry
    assert entry.unique_id == "-31_Test1_sleep_number"


async def test_set_sleepnumber(hass: HomeAssistant, requests_mock: MagicMock):
    """Test setting the sleep number of a bed."""
    await init_integration(hass, requests_mock)

    with patch("sleepyq.Sleepyq.set_sleepnumber") as mock_client:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.sleepnumber_ile_test1_sleepnumber",
                ATTR_VALUE: 42,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        assert mock_client.call_count == 1
        mock_client.assert_called_with("right", 42, "-31")


async def test_actuator_state(hass: HomeAssistant, requests_mock: MagicMock):
    """Test the SleepIQ actuators for a bed with a single foundation."""
    await init_integration(hass, requests_mock)

    entity_registry = er.async_get(hass)

    state = hass.states.get("number.sleepnumber_ile_head_position")
    assert state.state == "20"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "SleepNumber ILE head Position"

    state = hass.states.get("number.sleepnumber_ile_foot_position")
    assert state.state == "15"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "SleepNumber ILE foot Position"

    entry = entity_registry.async_get("number.sleepnumber_ile_head_position")
    assert entry
    assert entry.unique_id == "-31_Test1_head"

    entry = entity_registry.async_get("number.sleepnumber_ile_foot_position")
    assert entry
    assert entry.unique_id == "-31_Test1_foot"


async def test_set_actuator(hass: HomeAssistant, requests_mock: MagicMock):
    """Test setting the actuator position."""
    await init_integration(hass, requests_mock)

    with patch("sleepyq.Sleepyq.set_foundation_position") as mock_client:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.sleepnumber_ile_head_position",
                ATTR_VALUE: 42,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        assert mock_client.call_count == 1
        mock_client.assert_called_with("right", "head", 42, "-31")
