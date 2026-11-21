"""Tests for the Plexilent lights."""

import asyncio
from dataclasses import replace
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyplexilent import Device, PlexilentError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_RGBWW_COLOR,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.plexilent.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import DEVICES


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
    """Every light type becomes a light with its own color modes; others are not lights."""
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


async def test_color_temp_limits_refresh(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The white-temperature range follows the latest device data."""
    await setup_integration(hass, entry)
    kitchen = _entity_id(hass, "m:2")
    assert hass.states.get(kitchen).attributes["max_color_temp_kelvin"] == 6500

    client.devices.return_value = [
        replace(DEVICES[0], cct_min=2200, cct_max=4000),
        *DEVICES[1:],
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    attrs = hass.states.get(kitchen).attributes
    assert attrs["min_color_temp_kelvin"] == 2200
    assert attrs["max_color_temp_kelvin"] == 4000


async def test_light_unavailable_when_device_drops(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A colour-temp light goes unavailable, not error, if a poll drops it."""
    await setup_integration(hass, entry)
    kitchen = _entity_id(hass, "m:2")
    assert hass.states.get(kitchen).state == STATE_ON

    client.devices.return_value = [d for d in DEVICES if d.id != "m:2"]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(kitchen).state == STATE_UNAVAILABLE


async def test_power_state_unknown(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An online light with no power state is unknown, not off."""
    await setup_integration(hass, entry)
    gate = _entity_id(hass, "m:6")
    assert hass.states.get(gate).state == STATE_ON

    client.devices.return_value = [
        replace(d, on=None) if d.id == "m:6" else d for d in DEVICES
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(gate).state == STATE_UNKNOWN


async def test_color_temp_bounds_fall_back(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Missing device limits fall back to Home Assistant's defaults."""
    await setup_integration(hass, entry)
    kitchen = _entity_id(hass, "m:2")

    client.devices.return_value = [
        replace(DEVICES[0], cct_min=None, cct_max=None),
        *DEVICES[1:],
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    attrs = hass.states.get(kitchen).attributes
    assert attrs["min_color_temp_kelvin"] == DEFAULT_MIN_KELVIN
    assert attrs["max_color_temp_kelvin"] == DEFAULT_MAX_KELVIN


async def test_rgbww_turn_on_without_color_bounds(
    hass: HomeAssistant, client: MagicMock, entry: MockConfigEntry
) -> None:
    """An rgbww turn-on does not fail on a light whose colour bounds are unset."""
    await setup_integration(hass, entry)
    hall = _entity_id(hass, "m:4")  # dim: cct_min/cct_max are None
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: hall, ATTR_RGBWW_COLOR: (255, 0, 0, 128, 128)},
        blocking=True,
    )
    assert hass.states.get(hall).state == STATE_ON


async def test_poll_does_not_revert_command(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A poll in flight when a command lands must not revert the command."""
    await setup_integration(hass, entry)
    hall = _entity_id(hass, "m:4")

    poll_started = asyncio.Event()
    finish_poll = asyncio.Event()

    async def slow_devices() -> list[Device]:
        poll_started.set()
        await finish_poll.wait()
        return list(DEVICES)  # stale snapshot: m:4 is off

    client.devices.side_effect = slow_devices

    # Start a poll; it blocks holding the coordinator lock.
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await poll_started.wait()

    # A command arrives mid-poll; it must serialize behind the poll.
    command = hass.async_create_task(
        hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: hall}, blocking=True
        )
    )
    finish_poll.set()
    await command
    await hass.async_block_till_done()

    assert hass.states.get(hall).state == STATE_ON


async def test_command_keeps_poll_schedule(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Commanding a light does not push out the next scheduled poll."""
    await setup_integration(hass, entry)  # polls at t0
    hall = _entity_id(hass, "m:4")

    freezer.tick(SCAN_INTERVAL / 2)  # t0 + 15 s
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: hall}, blocking=True
    )
    client.devices.reset_mock()

    freezer.tick(SCAN_INTERVAL / 2)  # t0 + 30 s: the original deadline
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    client.devices.assert_awaited()


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
