"""The tests for Miele device conditions."""

from collections.abc import Generator
from unittest.mock import MagicMock

from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.miele import DOMAIN
from homeassistant.components.miele.const import STATE_STATUS_TAGS, StateStatus
from homeassistant.components.miele.device_condition import CONDITION_TYPES
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry, async_get_device_automations


async def test_get_conditions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_miele_client: Generator[MagicMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we get the expected conditions from a miele."""

    TEST_DEVICE = "Dummy_Appliance_1"

    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, TEST_DEVICE)})
    assert device_entry is not None

    entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )
    expected_conditions = [
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": condition_type,
            "device_id": device_entry.id,
            "entity_id": "sensor.freezer",
            "metadata": {"secondary": False},
        }
        for condition_type in CONDITION_TYPES
    ]

    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    conds = [cond for cond in conditions if cond["domain"] == DOMAIN]

    assert conds == unordered(expected_conditions)


async def test_if_state(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
    mock_miele_client: Generator[MagicMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for in_use and not_connected conditions."""

    TEST_DEVICE = "Dummy_Appliance_1"

    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, TEST_DEVICE)})
    assert device_entry is not None

    hass.states.async_set("miele.entity", STATE_STATUS_TAGS[StateStatus.IN_USE])

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device_entry.id,
                            "entity_id": "miele.entity",
                            "type": STATE_STATUS_TAGS[StateStatus.IN_USE],
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": STATE_STATUS_TAGS[StateStatus.IN_USE]
                            + " - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event2"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device_entry.id,
                            "entity_id": "miele.entity",
                            "type": STATE_STATUS_TAGS[StateStatus.NOT_CONNECTED],
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": STATE_STATUS_TAGS[StateStatus.NOT_CONNECTED]
                            + " - {{ trigger.platform }} - {{ trigger.event.event_type }}"
                        },
                    },
                },
            ]
        },
    )
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "in_use - event - test_event1"

    hass.states.async_set("miele.entity", STATE_STATUS_TAGS[StateStatus.NOT_CONNECTED])
    hass.bus.async_fire("test_event1")
    hass.bus.async_fire("test_event2")
    await hass.async_block_till_done()
    assert len(service_calls) == 2
    assert service_calls[1].data["some"] == "not_connected - event - test_event2"
