"""Tests for home_connect EVENT entities."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

from aiohomeconnect.model import (
    ArrayOfEvents,
    Event,
    EventKey,
    EventMessage,
    EventType,
    HomeAppliance,
)
import pytest

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.components.home_connect.const import (
    BSH_EVENT_PRESENT_STATE_CONFIRMED,
    BSH_EVENT_PRESENT_STATE_OFF,
    BSH_EVENT_PRESENT_STATE_PRESENT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.EVENT]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("appliance", ["Washer"], indirect=True)
async def test_paired_depaired_devices_flow(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test device removal and re-addition on API events."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    assert device
    entity_entries = entity_registry.entities.get_entries_for_device_id(device.id)
    assert entity_entries

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.DEPAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    assert not device
    for entity_entry in entity_entries:
        assert not entity_registry.async_get(entity_entry.entity_id)

    # Now that all everything related to the device is removed, pair it again
    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.PAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    assert device_registry.async_get_device(identifiers={(DOMAIN, appliance.ha_id)})
    for entity_entry in entity_entries:
        assert entity_registry.async_get(entity_entry.entity_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("appliance", ["Dishwasher"], indirect=True)
async def test_event_entity_availability(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test EVENT entities availability based on appliance connection."""
    entity_id = "event.dishwasher_salt_nearly_empty"
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.DISCONNECTED,
                ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    assert hass.states.is_state(entity_id, STATE_UNAVAILABLE)

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.CONNECTED,
                ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("appliance", ["Dishwasher"], indirect=True)
async def test_event_entity_state_updates(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test EVENT entity state updates based on events."""
    entity_id = "event.dishwasher_salt_nearly_empty"
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_EVENT_TYPE] is None

    for event_value, expected_event_type in (
        (BSH_EVENT_PRESENT_STATE_OFF, "off"),
        (BSH_EVENT_PRESENT_STATE_PRESENT, "present"),
        (BSH_EVENT_PRESENT_STATE_CONFIRMED, "confirmed"),
    ):
        await client.add_events(
            [
                EventMessage(
                    appliance.ha_id,
                    EventType.EVENT,
                    ArrayOfEvents(
                        [
                            Event(
                                key=EventKey.DISHCARE_DISHWASHER_EVENT_SALT_NEARLY_EMPTY,
                                raw_key=str(
                                    EventKey.DISHCARE_DISHWASHER_EVENT_SALT_NEARLY_EMPTY
                                ),
                                timestamp=0,
                                level="",
                                handling="",
                                value=event_value,
                            )
                        ]
                    ),
                )
            ]
        )
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state
        assert state.attributes[ATTR_EVENT_TYPE] == expected_event_type
