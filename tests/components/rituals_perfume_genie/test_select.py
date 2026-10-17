"""Tests for the Rituals Perfume Genie select platform."""

import pytest
from ritualsgenie import RoomSize

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_NEXT,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_SELECT_OPTION,
    EntityCategory,
    UnitOfArea,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .common import init_integration, mock_config_entry, mock_diffuser


async def test_select_entity(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the creation and state of the diffuser select entity."""
    config_entry = mock_config_entry(unique_id="select_test")
    diffuser = mock_diffuser(hublot="lot123", room_size_square_meter=60)
    await init_integration(hass, config_entry, [diffuser])

    state = hass.states.get("select.genie_room_size")
    assert state
    assert state.state == str(diffuser.room_size_square_meter)
    assert state.attributes[ATTR_OPTIONS] == ["15", "30", "60", "100"]

    entry = entity_registry.async_get("select.genie_room_size")
    assert entry
    assert entry.unique_id == f"{diffuser.hublot}-room_size_square_meter"
    assert entry.unit_of_measurement == UnitOfArea.SQUARE_METERS
    assert entry.entity_category == EntityCategory.CONFIG


async def test_select_option(hass: HomeAssistant) -> None:
    """Test selecting of a option."""
    config_entry = mock_config_entry(unique_id="select_invalid_option_test")
    diffuser = mock_diffuser(hublot="lot123", room_size_square_meter=60)
    client = await init_integration(hass, config_entry, [diffuser])
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})

    state = hass.states.get("select.genie_room_size")
    assert state
    assert state.state == "60"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.genie_room_size", ATTR_OPTION: "30"},
        blocking=True,
    )

    client.set_room_size_category.assert_awaited_once_with(
        diffuser.hub_hash, RoomSize.MEDIUM
    )

    diffuser.room_size_square_meter = 30
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ["select.genie_room_size"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.genie_room_size")
    assert state
    assert state.state == "30"


async def test_select_invalid_option(hass: HomeAssistant) -> None:
    """Test selecting an invalid option."""
    config_entry = mock_config_entry(unique_id="select_invalid_option_test")
    diffuser = mock_diffuser(hublot="lot123", room_size_square_meter=60)
    await init_integration(hass, config_entry, [diffuser])
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})

    state = hass.states.get("select.genie_room_size")
    assert state
    assert state.state == "60"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: "select.genie_room_size", ATTR_OPTION: "120"},
            blocking=True,
        )
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ["select.genie_room_size"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.genie_room_size")
    assert state
    assert state.state == "60"


async def test_select_next_twice(hass: HomeAssistant) -> None:
    """Test selecting the next option twice before an update moves on twice."""
    config_entry = mock_config_entry(unique_id="select_next_twice_test")
    diffuser = mock_diffuser(hublot="lot123", room_size_square_meter=15)
    client = await init_integration(hass, config_entry, [diffuser])

    for _ in range(2):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_NEXT,
            {ATTR_ENTITY_ID: "select.genie_room_size"},
            blocking=True,
        )

    assert [call.args[1] for call in client.set_room_size_category.await_args_list] == [
        RoomSize.MEDIUM,
        RoomSize.LARGE,
    ]

    state = hass.states.get("select.genie_room_size")
    assert state
    assert state.state == "60"
