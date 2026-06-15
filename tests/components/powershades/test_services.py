"""Tests for PowerShades services."""

import pytest

from homeassistant.components.powershades.const import (
    DOMAIN,
    LIMIT_LOWER,
    LIMIT_UPPER,
    OP_CLEAR_LIMITS,
    OP_JOG_DOWN,
    OP_JOG_UP,
    OP_SET_LIMIT,
    OP_SET_POSITION,
    OP_STEP_DOWN,
    OP_STEP_UP,
)
from homeassistant.components.powershades.protocol import (
    build_set_limit_payload,
    build_set_position_payload,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

ENTITY_ID = "cover.powershade_bedroom_shade"


async def test_toggle_shade(hass: HomeAssistant, config_entry) -> None:
    """The toggle_shade service toggles the shade."""
    await hass.services.async_call(
        DOMAIN, "toggle_shade", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    coordinator = config_entry.runtime_data
    coordinator.connection.async_request.assert_any_call(
        OP_SET_POSITION, build_set_position_payload(100)
    )


async def test_set_upper_limit(hass: HomeAssistant, config_entry) -> None:
    """The set_upper_limit service sets the upper limit."""
    await hass.services.async_call(
        DOMAIN, "set_upper_limit", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    coordinator = config_entry.runtime_data
    coordinator.connection.async_request.assert_any_call(
        OP_SET_LIMIT, build_set_limit_payload(LIMIT_UPPER)
    )


async def test_set_lower_limit(hass: HomeAssistant, config_entry) -> None:
    """The set_lower_limit service sets the lower limit."""
    await hass.services.async_call(
        DOMAIN, "set_lower_limit", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    coordinator = config_entry.runtime_data
    coordinator.connection.async_request.assert_any_call(
        OP_SET_LIMIT, build_set_limit_payload(LIMIT_LOWER)
    )


async def test_clear_limits(hass: HomeAssistant, config_entry) -> None:
    """The clear_limits service clears both limits."""
    await hass.services.async_call(
        DOMAIN, "clear_limits", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    coordinator = config_entry.runtime_data
    coordinator.connection.async_request.assert_any_call(OP_CLEAR_LIMITS, b"")


async def test_step_up(hass: HomeAssistant, config_entry) -> None:
    """The step_up service steps the motor up."""
    await hass.services.async_call(
        DOMAIN, "step_up", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    coordinator = config_entry.runtime_data
    coordinator.connection.async_request.assert_any_call(OP_STEP_UP, b"")


async def test_step_down(hass: HomeAssistant, config_entry) -> None:
    """The step_down service steps the motor down."""
    await hass.services.async_call(
        DOMAIN, "step_down", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    coordinator = config_entry.runtime_data
    coordinator.connection.async_request.assert_any_call(OP_STEP_DOWN, b"")


async def test_jog_up(hass: HomeAssistant, config_entry) -> None:
    """The jog_up service jogs the motor up."""
    await hass.services.async_call(
        DOMAIN, "jog_up", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    coordinator = config_entry.runtime_data
    coordinator.connection.async_request.assert_any_call(OP_JOG_UP, b"")


async def test_jog_down(hass: HomeAssistant, config_entry) -> None:
    """The jog_down service jogs the motor down."""
    await hass.services.async_call(
        DOMAIN, "jog_down", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    coordinator = config_entry.runtime_data
    coordinator.connection.async_request.assert_any_call(OP_JOG_DOWN, b"")


async def test_set_shade_name(hass: HomeAssistant, config_entry) -> None:
    """The set_shade_name service renames the shade."""
    await hass.services.async_call(
        DOMAIN,
        "set_shade_name",
        {ATTR_ENTITY_ID: ENTITY_ID, "name": "New Name"},
        blocking=True,
    )

    coordinator = config_entry.runtime_data
    assert coordinator.device_name == "Bedroom Shade"


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        "x" * 51,
        "café",
    ],
)
async def test_set_shade_name_invalid(
    hass: HomeAssistant, config_entry, name: str
) -> None:
    """Invalid shade names are rejected before reaching the device."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "set_shade_name",
            {ATTR_ENTITY_ID: ENTITY_ID, "name": name},
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_shade_name"


async def test_service_entity_not_found(hass: HomeAssistant, config_entry) -> None:
    """A service call against an unknown entity raises entity_not_found."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "toggle_shade",
            {ATTR_ENTITY_ID: "cover.does_not_exist"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "entity_not_found"


async def test_service_entry_not_loaded(hass: HomeAssistant, config_entry) -> None:
    """A service call against an unloaded config entry raises entry_not_loaded."""
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "toggle_shade",
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.translation_key == "entry_not_loaded"
