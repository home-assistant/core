"""Tests for the LIFX select platform."""

from collections.abc import Callable

from lifx import LifxError, ThemeLibrary
import pytest

from homeassistant.components.select import ATTR_OPTIONS, DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import SERIAL, async_setup_lifx_entry, async_trigger_update
from .helpers import (
    INFRARED_SELECT_ENTITY_ID,
    MockDevice,
    create_mock_infrared_light,
    create_mock_multizone_light,
)


async def test_theme_select(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test theme options and selected theme remain lower case."""
    device = create_mock_multizone_light()
    await async_setup_lifx_entry(hass, device)
    entity_id = "select.my_group_my_bulb_theme"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert not entity.disabled
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_OPTIONS] == [
        name.lower() for name in ThemeLibrary.get_available_themes()
    ]

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: entity_id, "option": "intense"},
        blocking=True,
    )

    device.apply_theme.assert_awaited_once()
    applied_theme = device.apply_theme.await_args.args[0]
    assert applied_theme.colors == ThemeLibrary.get("intense").colors
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "intense"

    await async_trigger_update(hass)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "intense"


@pytest.mark.parametrize(
    ("option", "level", "refreshed_level"),
    [
        pytest.param("Disabled", 0.0, 0 / 65535, id="disabled"),
        pytest.param("25%", 0.25, 16383 / 65535, id="quarter"),
        pytest.param("50%", 0.5, 32767 / 65535, id="half"),
        pytest.param("100%", 1.0, 65535 / 65535, id="full"),
    ],
)
async def test_infrared_brightness(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    option: str,
    level: float,
    refreshed_level: float,
) -> None:
    """Test typed infrared levels map to unchanged option labels."""
    device = create_mock_infrared_light()
    await async_setup_lifx_entry(hass, device)
    entity_id = INFRARED_SELECT_ENTITY_ID

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert not entity.disabled
    assert entity.unique_id == f"{SERIAL}_infrared_brightness"

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: entity_id, "option": option},
        blocking=True,
    )
    device.set_infrared.assert_awaited_once_with(level)

    device.state.infrared = refreshed_level
    await async_trigger_update(hass)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == option


@pytest.mark.parametrize(
    ("factory", "method", "entity_id", "option"),
    [
        pytest.param(
            create_mock_infrared_light,
            "set_infrared",
            INFRARED_SELECT_ENTITY_ID,
            "50%",
            id="infrared_brightness",
        ),
        pytest.param(
            create_mock_multizone_light,
            "apply_theme",
            "select.my_group_my_bulb_theme",
            "intense",
            id="theme",
        ),
    ],
)
async def test_select_library_error_becomes_home_assistant_error(
    hass: HomeAssistant,
    factory: Callable[[], MockDevice],
    method: str,
    entity_id: str,
    option: str,
) -> None:
    """Test a library failure surfaces as a Home Assistant error."""
    device = factory()
    await async_setup_lifx_entry(hass, device)
    getattr(device, method).side_effect = LifxError("device unreachable")

    with pytest.raises(HomeAssistantError, match="device unreachable"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            "select_option",
            {ATTR_ENTITY_ID: entity_id, "option": option},
            blocking=True,
        )
