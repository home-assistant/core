"""The tests for the Select component."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.select import (
    ATTR_CYCLE,
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN,
    SERVICE_SELECT_FIRST,
    SERVICE_SELECT_LAST,
    SERVICE_SELECT_NEXT,
    SERVICE_SELECT_OPTION,
    SERVICE_SELECT_PREVIOUS,
    SelectEntity,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.common import setup_test_component_platform


class MockSelectEntity(SelectEntity):
    """Mock SelectEntity to use in tests."""

    _attr_current_option = "option_one"
    _attr_options = ["option_one", "option_two", "option_three"]


class MockSelectEntityWithoutOptions(MockSelectEntity):
    """Mock SelectEntity without any options to use in tests."""

    _attr_name = "select without options"
    _attr_options: list[str] = []


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
        await select.async_first()

    with pytest.raises(NotImplementedError):
        await select.async_last()

    with pytest.raises(NotImplementedError):
        await select.async_next(cycle=False)

    with pytest.raises(NotImplementedError):
        await select.async_previous(cycle=False)

    with pytest.raises(NotImplementedError):
        await select.async_select_option("option_one")

    select.select_option = MagicMock()
    select._attr_current_option = None

    await select.async_first()
    assert select.select_option.call_args[0][0] == "option_one"

    await select.async_last()
    assert select.select_option.call_args[0][0] == "option_three"

    await select.async_next(cycle=False)
    assert select.select_option.call_args[0][0] == "option_one"

    await select.async_previous(cycle=False)
    assert select.select_option.call_args[0][0] == "option_three"

    await select.async_select_option("option_two")
    assert select.select_option.call_args[0][0] == "option_two"

    assert select.select_option.call_count == 5

    assert select.capability_attributes[ATTR_OPTIONS] == [
        "option_one",
        "option_two",
        "option_three",
    ]


async def test_custom_integration_and_validation(
    hass: HomeAssistant,
    mock_select_entities: list[MockSelectEntity],
) -> None:
    """Test we can only select valid options."""
    setup_test_component_platform(hass, DOMAIN, mock_select_entities)

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

    # test ServiceValidationError trigger
    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_OPTION: "option invalid", ATTR_ENTITY_ID: "select.select_1"},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "not_valid_option"

    assert hass.states.get("select.select_1").state == "option 2"

    assert hass.states.get("select.select_2").state == STATE_UNKNOWN

    with pytest.raises(ServiceValidationError):
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

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_FIRST,
        {ATTR_ENTITY_ID: "select.select_2"},
        blocking=True,
    )
    assert hass.states.get("select.select_2").state == "option 1"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_LAST,
        {ATTR_ENTITY_ID: "select.select_2"},
        blocking=True,
    )
    assert hass.states.get("select.select_2").state == "option 3"

    # Do no cycle
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_NEXT,
        {ATTR_ENTITY_ID: "select.select_2", ATTR_CYCLE: False},
        blocking=True,
    )
    assert hass.states.get("select.select_2").state == "option 3"

    # Do cycle (default behavior)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_NEXT,
        {ATTR_ENTITY_ID: "select.select_2"},
        blocking=True,
    )
    assert hass.states.get("select.select_2").state == "option 1"

    # Do not cycle
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_PREVIOUS,
        {ATTR_ENTITY_ID: "select.select_2", ATTR_CYCLE: False},
        blocking=True,
    )
    assert hass.states.get("select.select_2").state == "option 1"

    # Do cycle (default behavior)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_PREVIOUS,
        {ATTR_ENTITY_ID: "select.select_2"},
        blocking=True,
    )
    assert hass.states.get("select.select_2").state == "option 3"


@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        pytest.param(SERVICE_SELECT_FIRST, {}, id="first"),
        pytest.param(SERVICE_SELECT_LAST, {}, id="last"),
        pytest.param(SERVICE_SELECT_NEXT, {}, id="next_cycle"),
        pytest.param(SERVICE_SELECT_NEXT, {ATTR_CYCLE: False}, id="next_no_cycle"),
        pytest.param(SERVICE_SELECT_PREVIOUS, {}, id="previous_cycle"),
        pytest.param(
            SERVICE_SELECT_PREVIOUS, {ATTR_CYCLE: False}, id="previous_no_cycle"
        ),
    ],
)
@pytest.mark.parametrize(
    "current_option",
    [None, "option_one"],
    ids=["without_current_option", "with_stale_current_option"],
)
async def test_navigation_services_without_options(
    hass: HomeAssistant,
    service: str,
    service_data: dict[str, bool],
    current_option: str | None,
) -> None:
    """Test the navigation actions on an entity which has no options."""
    entity = MockSelectEntityWithoutOptions()
    entity._attr_current_option = current_option
    entity.select_option = MagicMock()
    setup_test_component_platform(hass, DOMAIN, [entity])

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    assert hass.states.get("select.select_without_options").state == STATE_UNKNOWN

    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTITY_ID: "select.select_without_options"} | service_data,
            blocking=True,
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "no_options"
    assert exc.value.translation_placeholders == {
        "entity_id": "select.select_without_options"
    }
    assert (
        str(exc.value)
        == "Entity select.select_without_options has no options to select from"
    )

    entity.select_option.assert_not_called()
    assert hass.states.get("select.select_without_options").state == STATE_UNKNOWN
