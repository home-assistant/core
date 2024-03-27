"""Tests for the lifx integration select entity."""

from datetime import timedelta

import pytest

from homeassistant.components import lifx
from homeassistant.components.lifx.const import DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    DEFAULT_ENTRY_TITLE,
    IP_ADDRESS,
    SERIAL,
    MockLifxCommand,
    _mocked_infrared_bulb,
    _mocked_light_strip,
    _patch_config_flow_try_connect,
    _patch_device,
    _patch_discovery,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_theme_select(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test selecting a theme."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_light_strip()
    bulb.product = 38
    bulb.power_level = 0
    bulb.color = [0, 0, 65535, 3500]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "select.my_bulb_theme"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert not entity.disabled

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: entity_id, "option": "intense"},
        blocking=True,
    )

    assert len(bulb.set_extended_color_zones.calls) == 1
    bulb.set_extended_color_zones.reset_mock()


async def test_infrared_brightness(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test getting and setting infrared brightness."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_infrared_bulb()
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    unique_id = f"{SERIAL}_infrared_brightness"
    entity_id = "select.my_bulb_infrared_brightness"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert not entity.disabled
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state.state == "100%"


@pytest.mark.usefixtures("mock_discovery")
async def test_set_infrared_brightness_25_percent(hass: HomeAssistant) -> None:
    """Test getting and setting infrared brightness."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_infrared_bulb()
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "select.my_bulb_infrared_brightness"

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: entity_id, "option": "25%"},
        blocking=True,
    )

    bulb.get_infrared = MockLifxCommand(bulb, infrared_brightness=16383)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert bulb.set_infrared.calls[0][0][0] == 16383

    state = hass.states.get(entity_id)
    assert state.state == "25%"

    bulb.set_infrared.reset_mock()


@pytest.mark.usefixtures("mock_discovery")
async def test_set_infrared_brightness_50_percent(hass: HomeAssistant) -> None:
    """Test getting and setting infrared brightness."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_infrared_bulb()
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "select.my_bulb_infrared_brightness"

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: entity_id, "option": "50%"},
        blocking=True,
    )

    bulb.get_infrared = MockLifxCommand(bulb, infrared_brightness=32767)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert bulb.set_infrared.calls[0][0][0] == 32767

    state = hass.states.get(entity_id)
    assert state.state == "50%"

    bulb.set_infrared.reset_mock()


@pytest.mark.usefixtures("mock_discovery")
async def test_set_infrared_brightness_100_percent(hass: HomeAssistant) -> None:
    """Test getting and setting infrared brightness."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_infrared_bulb()
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "select.my_bulb_infrared_brightness"

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: entity_id, "option": "100%"},
        blocking=True,
    )

    bulb.get_infrared = MockLifxCommand(bulb, infrared_brightness=65535)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert bulb.set_infrared.calls[0][0][0] == 65535

    state = hass.states.get(entity_id)
    assert state.state == "100%"

    bulb.set_infrared.reset_mock()


@pytest.mark.usefixtures("mock_discovery")
async def test_disable_infrared(hass: HomeAssistant) -> None:
    """Test getting and setting infrared brightness."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_infrared_bulb()
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "select.my_bulb_infrared_brightness"

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: entity_id, "option": "Disabled"},
        blocking=True,
    )

    bulb.get_infrared = MockLifxCommand(bulb, infrared_brightness=0)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert bulb.set_infrared.calls[0][0][0] == 0

    state = hass.states.get(entity_id)
    assert state.state == "Disabled"

    bulb.set_infrared.reset_mock()


@pytest.mark.usefixtures("mock_discovery")
async def test_invalid_infrared_brightness(hass: HomeAssistant) -> None:
    """Test getting and setting infrared brightness."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=SERIAL,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_infrared_bulb()
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "select.my_bulb_infrared_brightness"

    bulb.get_infrared = MockLifxCommand(bulb, infrared_brightness=12345)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN
