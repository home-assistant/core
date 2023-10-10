"""Tests for refoss component."""
from unittest.mock import patch

import pytest

from homeassistant.components.refoss.const import DOMAIN as REFOSS_DOMAIN
from homeassistant.components.switch import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .common import FakeDiscovery, build_base_device_mock

from tests.common import MockConfigEntry

ENTITY_ID_SWITCH = f"{DOMAIN}.r10"


async def async_setup_refoss_switch(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the refoss switch platform."""
    entry = MockConfigEntry(domain=REFOSS_DOMAIN)
    entry.add_to_hass(hass)
    await async_setup_component(hass, REFOSS_DOMAIN, {REFOSS_DOMAIN: {DOMAIN: {}}})
    await hass.async_block_till_done()
    return entry


@patch("homeassistant.components.refoss.PLATFORMS", [DOMAIN])
async def test_registry_settings(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for entity registry settings."""
    with patch(
        "homeassistant.components.refoss.util.Discovery",
        return_value=FakeDiscovery(),
    ), patch(
        "homeassistant.components.refoss.bridge.async_build_base_device",
        return_value=build_base_device_mock(),
    ), patch(
        "homeassistant.components.refoss.switch.isinstance",
        return_value=True,
    ):
        entry = await async_setup_refoss_switch(hass)
        assert entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "entity",
    [
        ENTITY_ID_SWITCH,
    ],
)
async def test_send_switch_on(
    hass: HomeAssistant, entity, entity_registry_enabled_by_default: None
) -> None:
    """Test for sending power on command to the device."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.refoss.util.Discovery",
        return_value=FakeDiscovery(),
    ), patch(
        "homeassistant.components.refoss.bridge.async_build_base_device",
        return_value=build_base_device_mock(),
    ), patch(
        "homeassistant.components.refoss.switch.isinstance",
        return_value=True,
    ):
        entry = await async_setup_refoss_switch(hass)
        await hass.async_block_till_done()
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity},
            blocking=True,
        )

        state = hass.states.get(entity)
        assert state is not None
        assert state.state == STATE_ON


@pytest.mark.parametrize(
    "entity",
    [
        ENTITY_ID_SWITCH,
    ],
)
async def test_send_switch_off(
    hass: HomeAssistant, entity, entity_registry_enabled_by_default: None
) -> None:
    """Test for sending power on command to the device."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.refoss.util.Discovery",
        return_value=FakeDiscovery(),
    ), patch(
        "homeassistant.components.refoss.bridge.async_build_base_device",
        return_value=build_base_device_mock(),
    ), patch(
        "homeassistant.components.refoss.switch.isinstance",
        return_value=True,
    ):
        entry = await async_setup_refoss_switch(hass)
        await hass.async_block_till_done()
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity},
            blocking=True,
        )

        state = hass.states.get(entity)
        assert state is not None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for entity registry settings (disabled_by, unique_id)."""
    await async_setup_refoss_switch(hass)

    hass.states.async_all(DOMAIN)
