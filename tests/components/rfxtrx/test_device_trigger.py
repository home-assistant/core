"""The tests for RFXCOM RFXtrx device triggers."""
from __future__ import annotations

from typing import Any, NamedTuple

import pytest
from pytest_unordered import unordered

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.rfxtrx import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import create_rfx_test_cfg

from tests.common import (
    MockConfigEntry,
    async_get_device_automations,
    async_mock_service,
)


class EventTestData(NamedTuple):
    """Test data linked to a device."""

    code: str
    device_identifiers: set[tuple[str, str, str, str]]
    type: str
    subtype: str


DEVICE_LIGHTING_1 = {("rfxtrx", "10", "0", "E5")}
EVENT_LIGHTING_1 = EventTestData("0710002a45050170", DEVICE_LIGHTING_1, "command", "On")

DEVICE_ROLLERTROL_1 = {("rfxtrx", "19", "0", "009ba8:1")}
EVENT_ROLLERTROL_1 = EventTestData(
    "09190000009ba8010100", DEVICE_ROLLERTROL_1, "command", "Down"
)

DEVICE_FIREALARM_1 = {("rfxtrx", "20", "3", "a10900:32")}
EVENT_FIREALARM_1 = EventTestData(
    "08200300a109000670", DEVICE_FIREALARM_1, "status", "Panic"
)


async def setup_entry(hass, devices):
    """Construct a config setup."""
    entry_data = create_rfx_test_cfg(devices=devices)
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_start()


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        [
            EVENT_LIGHTING_1,
            [
                {"type": "command", "subtype": subtype}
                for subtype in [
                    "Off",
                    "On",
                    "Dim",
                    "Bright",
                    "All/group Off",
                    "All/group On",
                    "Chime",
                    "Illegal command",
                ]
            ],
        ]
    ],
)
async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    event: EventTestData,
    expected,
) -> None:
    """Test we get the expected triggers from a rfxtrx."""
    await setup_entry(hass, {event.code: {}})

    device_entry = device_registry.async_get_device(
        identifiers=event.device_identifiers
    )
    assert device_entry

    # Add alternate identifiers, to make sure we can handle future formats
    identifiers: list[str] = list(*event.device_identifiers)
    device_registry.async_update_device(
        device_entry.id, merge_identifiers={(identifiers[0], "_".join(identifiers[1:]))}
    )
    device_entry = device_registry.async_get_device(
        identifiers=event.device_identifiers
    )
    assert device_entry

    expected_triggers = [
        {
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "platform": "device",
            "metadata": {},
            **expect,
        }
        for expect in expected
    ]

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    triggers = [value for value in triggers if value["domain"] == "rfxtrx"]
    assert triggers == unordered(expected_triggers)


@pytest.mark.parametrize(
    "event",
    [
        EVENT_LIGHTING_1,
        EVENT_ROLLERTROL_1,
        EVENT_FIREALARM_1,
    ],
)
async def test_firing_event(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, rfxtrx, event
) -> None:
    """Test for turn_on and turn_off triggers firing."""

    await setup_entry(hass, {event.code: {"fire_event": True}})

    device_entry = device_registry.async_get_device(
        identifiers=event.device_identifiers
    )
    assert device_entry

    calls = async_mock_service(hass, "test", "automation")

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
                        "type": event.type,
                        "subtype": event.subtype,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("{{trigger.platform}}")},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    await rfxtrx.signal(event.code)

    assert len(calls) == 1
    assert calls[0].data["some"] == "device"


async def test_invalid_trigger(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test for invalid actions."""
    event = EVENT_LIGHTING_1

    await setup_entry(hass, {event.code: {"fire_event": True}})

    device_identifiers: Any = event.device_identifiers
    device_entry = device_registry.async_get_device(identifiers=device_identifiers)
    assert device_entry

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
                        "type": event.type,
                        "subtype": "invalid",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("{{trigger.platform}}")},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert "Subtype invalid not found in device triggers" in caplog.text
