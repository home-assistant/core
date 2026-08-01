"""Tests for the LIFX select platform."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

from lifx import LifxError, ThemeLibrary
import pytest

from homeassistant.components.lifx.const import DOMAIN
from homeassistant.components.select import ATTR_OPTIONS, DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from . import SERIAL, async_setup_lifx_entry, async_trigger_update
from .helpers import (
    INFRARED_NUMBER_ENTITY_ID,
    INFRARED_SELECT_ENTITY_ID,
    MockDevice,
    create_mock_infrared_light,
    create_mock_multizone_light,
    register_legacy_infrared_select,
)

REGISTERED_AUTOMATION_ENTITY_ID = "automation.night_vision"


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
    register_legacy_infrared_select(entity_registry)
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
            "select.my_group_my_bulb_infrared_brightness",
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
    entity_registry: er.EntityRegistry,
    factory: Callable[[], MockDevice],
    method: str,
    entity_id: str,
    option: str,
) -> None:
    """Test a library failure surfaces as a Home Assistant error."""
    register_legacy_infrared_select(entity_registry)
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


async def test_infrared_select_is_not_created_for_a_new_install(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a device that never had the select does not gain one."""
    await async_setup_lifx_entry(hass, create_mock_infrared_light())

    assert entity_registry.async_get(INFRARED_SELECT_ENTITY_ID) is None
    assert hass.states.get(INFRARED_NUMBER_ENTITY_ID) is not None
    assert not issue_registry.issues


@pytest.mark.parametrize(
    "used_by",
    [
        pytest.param([], id="unused"),
        pytest.param([REGISTERED_AUTOMATION_ENTITY_ID], id="used-by-an-automation"),
    ],
)
async def test_existing_infrared_select_is_deprecated(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    used_by: list[str],
) -> None:
    """Test an already registered select is kept and reported as deprecated."""
    register_legacy_infrared_select(entity_registry)

    with patch(
        "homeassistant.components.lifx.select.automations_with_entity",
        return_value=used_by,
    ):
        await async_setup_lifx_entry(hass, create_mock_infrared_light())

    assert hass.states.get(INFRARED_SELECT_ENTITY_ID) is not None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_infrared_select_{INFRARED_SELECT_ENTITY_ID}"
    )
    assert issue
    assert issue.translation_key == "deprecated_infrared_select"
    assert issue.breaks_in_ha_version == "2026.11.0"
    # The fix flow decides whether the select can go, so the issue stays fixable
    assert issue.is_fixable
    assert issue.translation_placeholders
    assert issue.translation_placeholders["entity_name"] == "Infrared brightness"
    assert (
        issue.translation_placeholders["replacement_entity_id"]
        == INFRARED_NUMBER_ENTITY_ID
    )


async def test_infrared_select_removed_before_start_is_left_alone(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a select removed between setup and start raises no deprecation issue."""
    hass.set_state(CoreState.not_running)
    register_legacy_infrared_select(entity_registry)

    await async_setup_lifx_entry(hass, create_mock_infrared_light())
    entity_registry.async_remove(INFRARED_SELECT_ENTITY_ID)

    hass.set_state(CoreState.running)
    # Starting also kicks off the broadcast discovery this test does not want
    with patch(
        "homeassistant.components.lifx.discovery.async_discover_devices",
        AsyncMock(return_value={}),
    ):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert not issue_registry.issues


async def test_disabled_infrared_select_is_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test disabling the select and dropping every use of it removes it."""
    register_legacy_infrared_select(entity_registry, er.RegistryEntryDisabler.USER)

    await async_setup_lifx_entry(hass, create_mock_infrared_light())

    assert entity_registry.async_get(INFRARED_SELECT_ENTITY_ID) is None
    assert not issue_registry.issues
