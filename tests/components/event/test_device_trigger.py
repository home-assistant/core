"""The test for event device automation."""

import pytest
from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.event import DOMAIN
from homeassistant.components.event.const import ATTR_EVENT_TYPE
from homeassistant.const import CONF_PLATFORM, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .conftest import MockEventEntity

from tests.common import MockConfigEntry, async_get_device_automations


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.mark.usefixtures("mock_event_platform")
async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_event_entities: list[MockEventEntity],
) -> None:
    """Test that we get the expected triggers from an event entity."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    registry_entries: list[er.RegistryEntry] = [
        entity_registry.async_get_or_create(
            DOMAIN,
            "test",
            mock_event_entity.unique_id,
            device_id=device_entry.id,
        )
        for mock_event_entity in mock_event_entities
    ]

    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "entity_id": entry.id,
            "type": "event",
            "subtype": event_type,
            "event_type": event_type,
            "metadata": {"secondary": False},
        }
        for entry in registry_entries
        for event_type in ("short_press", "long_press")
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


@pytest.mark.usefixtures("mock_event_platform")
async def test_if_fires_on_state_change(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
    mock_event_entities: list[MockEventEntity],
) -> None:
    """Test that event device triggers fire."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        mock_event_entities[0].unique_id,
        device_id=device_entry.id,
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
                        "type": "event",
                        "event_type": "short_press",
                        "subtype": "short_press",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "event {{ trigger.platform }}"
                                " - {{ trigger.entity_id }}"
                                " - {{ trigger.from_state.state }}"
                                " - {{ trigger.to_state.state }}"
                                " - {{ trigger.event_type }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": entry.id,
                        "type": "event",
                        "event_type": "long_press",
                        "subtype": "long_press",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "event {{ trigger.platform }}"
                                " - {{ trigger.entity_id }}"
                                " - {{ trigger.from_state.state }}"
                                " - {{ trigger.to_state.state }}"
                                " - {{ trigger.event_type }}"
                            )
                        },
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(entry.entity_id).state is STATE_UNKNOWN
    assert len(service_calls) == 0

    short_press_time = dt_util.utcnow().isoformat(timespec="milliseconds")
    hass.states.async_set(
        entry.entity_id, short_press_time, {ATTR_EVENT_TYPE: "short_press"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == (
        "event device"
        f" - {entry.entity_id}"
        f" - {STATE_UNKNOWN}"
        f" - {short_press_time}"
        " - short_press"
    )

    long_press_time = dt_util.utcnow().isoformat(timespec="milliseconds")
    hass.states.async_set(
        entry.entity_id, long_press_time, {ATTR_EVENT_TYPE: "long_press"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 2
    assert service_calls[1].data["some"] == (
        "event device"
        f" - {entry.entity_id}"
        f" - {short_press_time}"
        f" - {long_press_time}"
        " - long_press"
    )
