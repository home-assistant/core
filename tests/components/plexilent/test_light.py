"""Tests for the Plexilent lights."""

from unittest.mock import MagicMock

from pyplexilent import PlexilentError
import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.plexilent.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


def _entity_id(hass: HomeAssistant, device_id: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(LIGHT_DOMAIN, DOMAIN, device_id)
    assert entity_id
    return entity_id


async def test_lights(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Every light type becomes a light with its own colour modes; others are not lights."""
    await setup_integration(hass, entry)

    kitchen = hass.states.get(_entity_id(hass, "m:2"))
    assert kitchen.state == STATE_ON
    assert kitchen.attributes["color_mode"] == "hs"
    assert kitchen.attributes["hs_color"] == (120, 100)
    assert kitchen.attributes["brightness"] == 102  # 40 %
    assert kitchen.attributes["min_color_temp_kelvin"] == 2700
    assert hass.states.get(_entity_id(hass, "m:4")).attributes[
        "supported_color_modes"
    ] == ["brightness"]
    assert hass.states.get(_entity_id(hass, "m:5")).state == STATE_UNAVAILABLE
    gate = hass.states.get(_entity_id(hass, "m:6"))
    assert gate.attributes["color_mode"] == "onoff"
    assert "brightness" not in gate.attributes
    assert len(hass.states.async_entity_ids(LIGHT_DOMAIN)) == 4

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "m:2"), entry.entry_id
    )
    assert (device.manufacturer, device.model, device.name) == (
        "Plexilent",
        "5ch",
        "Kitchen",
    )
    assert device.area_id == "kitchen"


@pytest.mark.parametrize(
    ("data", "sent"),
    [
        (
            {ATTR_BRIGHTNESS: 255, ATTR_COLOR_TEMP_KELVIN: 3000},
            {"on": True, "brightness": 100, "cct": 3000},
        ),
        ({ATTR_BRIGHTNESS: 1}, {"on": True, "brightness": 1}),
        ({ATTR_HS_COLOR: (30, 50)}, {"on": True, "hs": (30, 50)}),
    ],
)
async def test_turn_on(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    data: dict,
    sent: dict,
) -> None:
    """Turn on sends only what was asked; brightness never rounds down to 0 % (off)."""
    await setup_integration(hass, entry)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _entity_id(hass, "m:2"), **data},
        blocking=True,
    )
    client.command.assert_awaited_with("m:2", **sent)


async def test_turn_off_and_error(
    hass: HomeAssistant, client: MagicMock, entry: MockConfigEntry
) -> None:
    """Turn off is applied at once; a cloud error is raised to the user."""
    await setup_integration(hass, entry)
    hall = _entity_id(hass, "m:4")
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: hall}, blocking=True
    )
    assert hass.states.get(hall).state == STATE_ON
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: hall}, blocking=True
    )
    client.command.assert_awaited_with("m:4", on=False)
    assert hass.states.get(hall).state == "off"

    client.command.side_effect = PlexilentError("boom")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: hall}, blocking=True
        )
