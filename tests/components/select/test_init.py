"""The tests for the Select component."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.select import ATTR_OPTIONS, DOMAIN, SelectEntity
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    CONF_PLATFORM,
    SERVICE_SELECT_OPTION,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


class MockSelectEntity(SelectEntity):
    """Mock SelectEntity to use in tests."""

    _attr_current_option = "option_one"
    _attr_options = ["option_one", "option_two", "option_three"]


async def test_select(hass: HomeAssistant) -> None:
    """Test getting data from the mocked select entity."""
    select = MockSelectEntity()
    assert select.current_option == "option_one"
    assert select.state == "option_one"
    assert select.options == ["option_one", "option_two", "option_three"]

    # Test none selected
    select._attr_current_option = None
    assert select.current_option is None
    assert select.state is None

    # Test none existing selected
    select._attr_current_option = "option_four"
    assert select.current_option == "option_four"
    assert select.state is None

    select.hass = hass

    with pytest.raises(NotImplementedError):
        await select.async_select_option("option_one")

    select.select_option = MagicMock()
    await select.async_select_option("option_one")

    assert select.select_option.called
    assert select.select_option.call_args[0][0] == "option_one"

    assert select.capability_attributes[ATTR_OPTIONS] == [
        "option_one",
        "option_two",
        "option_three",
    ]


async def test_custom_integration_and_validation(hass, enable_custom_integrations):
    """Test we can only select valid options."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    assert hass.states.get("select.select_1").state == "option 1"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_OPTION: "option 2", ATTR_ENTITY_ID: "select.select_1"},
        blocking=True,
    )

    hass.states.async_set("select.select_1", "option 2")
    await hass.async_block_till_done()
    assert hass.states.get("select.select_1").state == "option 2"

    # test ValueError trigger
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_OPTION: "option invalid", ATTR_ENTITY_ID: "select.select_1"},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert hass.states.get("select.select_1").state == "option 2"

    assert hass.states.get("select.select_2").state == STATE_UNKNOWN

    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_OPTION: "option invalid", ATTR_ENTITY_ID: "select.select_2"},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert hass.states.get("select.select_2").state == STATE_UNKNOWN

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_OPTION: "option 3", ATTR_ENTITY_ID: "select.select_2"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("select.select_2").state == "option 3"
