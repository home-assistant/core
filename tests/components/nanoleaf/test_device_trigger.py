"""Tests for Nanoleaf device triggers."""

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_get_device_automations
from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.device_automation import (
    DeviceAutomationType,
    DeviceNotFound,
)
from homeassistant.components.nanoleaf import DOMAIN
from homeassistant.components.nanoleaf.const import NANOLEAF_EVENT
from homeassistant.components.nanoleaf.device_trigger import async_get_triggers
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.setup import async_setup_component

TRIGGER_TYPES = [
    "single_tap",
    "double_tap",
    "swipe_up",
    "swipe_down",
    "swipe_left",
    "swipe_right",
]


@pytest.mark.parametrize(
    ("model", "expected_types"),
    [
        pytest.param("NL29", TRIGGER_TYPES, id="touch"),
        pytest.param("NL22", [], id="no_touch"),
    ],
)
async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    model: str,
    expected_types: list[str],
) -> None:
    """Test the triggers of a Nanoleaf device depend on its touch support."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "ABCDEF123456")},
        model=model,
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(
        [
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": device_entry.id,
                "type": trigger_type,
                "metadata": {},
            }
            for trigger_type in expected_types
        ]
    )


async def test_get_triggers_unknown_device(hass: HomeAssistant) -> None:
    """Test getting the triggers of an unknown device."""
    with pytest.raises(DeviceNotFound):
        await async_get_triggers(hass, "unknown")


async def test_if_fires_on_gesture(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    issue_registry: ir.IssueRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test the trigger firing on a matching gesture event."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "ABCDEF123456")},
        model="NL29",
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
                        "type": "swipe_up",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "{{ trigger.event.data.type }}"},
                    },
                },
            ]
        },
    )
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_device_trigger_nanoleaf")

    hass.bus.async_fire(
        NANOLEAF_EVENT, {"device_id": device_entry.id, "type": "swipe_down"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.bus.async_fire(
        NANOLEAF_EVENT, {"device_id": device_entry.id, "type": "swipe_up"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "swipe_up"
