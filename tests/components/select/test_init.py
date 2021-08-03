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
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component

from tests.common import mock_registry
from tests.testing_config.custom_components.test.select import (
    UNIQUE_SELECT_1,
    UNIQUE_SELECT_2,
)


class MockSelectEntity(SelectEntity):
    """Mock SelectEntity to use in tests."""

    _attr_current_option = "option_one"
    _attr_options = ["option_one", "option_two", "option_three"]


@pytest.fixture
def entity_reg(hass: HomeAssistant) -> entity_registry.EntityRegistry:
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


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


async def test_custom_integration_and_validation(
    hass, entity_reg, enable_custom_integrations
):
    """Test we can only select valid options."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    reg_entry_1 = entity_reg.async_get_or_create(
        DOMAIN,
        "test",
        UNIQUE_SELECT_1,
    )
    reg_entry_2 = entity_reg.async_get_or_create(
        DOMAIN,
        "test",
        UNIQUE_SELECT_2,
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    assert hass.states.get(reg_entry_1.entity_id).state == "option 1"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_OPTION: "option 2", ATTR_ENTITY_ID: reg_entry_1.entity_id},
        blocking=True,
    )

    hass.states.async_set(reg_entry_1.entity_id, "option 2")
    await hass.async_block_till_done()
    assert hass.states.get(reg_entry_1.entity_id).state == "option 2"

    # test ValueError trigger
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_OPTION: "option invalid", ATTR_ENTITY_ID: reg_entry_1.entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert hass.states.get(reg_entry_1.entity_id).state == "option 2"

    assert hass.states.get(reg_entry_2.entity_id).state == STATE_UNKNOWN

    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_OPTION: "option invalid", ATTR_ENTITY_ID: reg_entry_2.entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert hass.states.get(reg_entry_2.entity_id).state == STATE_UNKNOWN

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_OPTION: "option 3", ATTR_ENTITY_ID: reg_entry_2.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(reg_entry_2.entity_id).state == "option 3"
