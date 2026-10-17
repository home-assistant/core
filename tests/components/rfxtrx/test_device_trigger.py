"""The tests for RFXCOM RFXtrx device triggers."""

from typing import Any, NamedTuple

import pytest
from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.rfxtrx import DOMAIN, device_trigger
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import create_rfx_test_entry, get_device_identifier

from tests.common import (
    MockConfigEntry,
    async_get_device_automations,
    async_mock_service,
)


class EventTestData(NamedTuple):
    """Test data linked to a device."""

    code: str
    device_identifier: tuple[str, str]
    type: str
    subtype: str


DEVICE_LIGHTING_1 = ("rfxtrx", "10_0_E5")
EVENT_LIGHTING_1 = EventTestData("0710002a45050170", DEVICE_LIGHTING_1, "command", "On")

DEVICE_ROLLERTROL_1 = ("rfxtrx", "19_0_009ba8:1")
EVENT_ROLLERTROL_1 = EventTestData(
    "09190000009ba8010100", DEVICE_ROLLERTROL_1, "command", "Down"
)

DEVICE_FIREALARM_1 = ("rfxtrx", "20_3_a10900:32")
EVENT_FIREALARM_1 = EventTestData(
    "08200300a109000670", DEVICE_FIREALARM_1, "status", "Panic"
)

DEVICE_X10SECURITY_1 = ("rfxtrx", "20_0_d3dc54:32")
# Status byte 0x84 = Motion (0x04) with the tamper bit (0x80) set.
EVENT_X10SECURITY_MOTION_TAMPER = "0820004dd3dc548489"
# Status byte 0x04 = Motion (0x04) without the tamper bit.
EVENT_X10SECURITY_MOTION = "0820004dd3dc540489"


async def setup_entry(hass: HomeAssistant, devices: dict[str, Any]) -> MockConfigEntry:
    """Construct a config setup."""
    mock_entry = create_rfx_test_entry(devices=devices)
    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_start()

    return mock_entry


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (
            EVENT_LIGHTING_1,
            [
                {"type": "command", "subtype": subtype}
                for subtype in (
                    "Off",
                    "On",
                    "Dim",
                    "Bright",
                    "All/group Off",
                    "All/group On",
                    "Chime",
                    "Illegal command",
                )
            ],
        )
    ],
)
async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    event: EventTestData,
    expected,
) -> None:
    """Test we get the expected triggers from a rfxtrx."""
    mock_entry = await setup_entry(hass, {event.code: {}})

    device_entry = device_registry.async_get_device_by_identifier(
        get_device_identifier(mock_entry, event.device_identifier[1]),
        mock_entry.entry_id,
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

    mock_entry = await setup_entry(hass, {event.code: {"fire_event": True}})

    device_entry = device_registry.async_get_device_by_identifier(
        get_device_identifier(mock_entry, event.device_identifier[1]),
        mock_entry.entry_id,
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


async def test_get_triggers_missing_identifier(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test getting triggers for a device without a rfxtrx identifier fails."""
    mock_entry = await setup_entry(hass, {})

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={("dummy_only", "id")},
    )

    with pytest.raises(ValueError, match="no rfxtrx identifier"):
        await device_trigger.async_get_triggers(hass, device_entry.id)


async def test_get_triggers_missing_subentry(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test getting triggers for a device pointing at a removed subentry fails."""
    mock_entry = await setup_entry(hass, {})

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={(DOMAIN, "not_a_real_subentry_id")},
    )

    with pytest.raises(ValueError, match="no subentry"):
        await device_trigger.async_get_triggers(hass, device_entry.id)


async def test_get_triggers_invalid_event_code(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test getting triggers for a device with an invalid event code fails."""
    mock_entry = await setup_entry(hass, {"invalid": {}})
    subentry = next(iter(mock_entry.subentries.values()))

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        config_subentry_id=subentry.subentry_id,
        identifiers={(DOMAIN, subentry.subentry_id)},
    )

    with pytest.raises(ValueError, match="invalid event code"):
        await device_trigger.async_get_triggers(hass, device_entry.id)


@pytest.mark.parametrize(
    ("trigger_subtype", "firing_event", "non_firing_event"),
    [
        pytest.param(
            "Motion Tamper",
            EVENT_X10SECURITY_MOTION_TAMPER,
            EVENT_X10SECURITY_MOTION,
            id="legacy_tamper_subtype_only_matches_tamper_event",
        ),
        pytest.param(
            "Motion",
            EVENT_X10SECURITY_MOTION,
            EVENT_X10SECURITY_MOTION_TAMPER,
            id="base_subtype_only_matches_non_tamper_event",
        ),
    ],
)
async def test_firing_security1_status_trigger(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    rfxtrx,
    trigger_subtype: str,
    firing_event: str,
    non_firing_event: str,
) -> None:
    """Test Security1 status triggers discriminate on the new ``Tamper`` field.

    pyRFXtrx 0.32.0 split the X10 security tamper bit into a separate
    ``Tamper`` boolean. Pre-0.32.0 ``Motion`` and ``Motion Tamper`` were
    distinct subtypes firing on disjoint events; that behaviour must be
    preserved so existing automations keep working without migration.
    """
    # Both events are variants of the same physical device (Motion and
    # Motion Tamper differ only in the status byte), so a single configured
    # subentry covers signals from either raw event code.
    mock_entry = await setup_entry(hass, {firing_event: {"fire_event": True}})

    device_entry = device_registry.async_get_device_by_identifier(
        get_device_identifier(mock_entry, DEVICE_X10SECURITY_1[1]),
        mock_entry.entry_id,
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
                        "type": "status",
                        "subtype": trigger_subtype,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "{{trigger.platform}}"},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    await rfxtrx.signal(non_firing_event)
    assert len(calls) == 0

    await rfxtrx.signal(firing_event)
    assert len(calls) == 1
    assert calls[0].data["some"] == "device"


@pytest.mark.parametrize(
    ("event", "trigger_type", "trigger_subtype"),
    [
        pytest.param(EVENT_LIGHTING_1, "command", "invalid", id="unknown_command"),
        pytest.param(
            EVENT_LIGHTING_1,
            "status",
            "Motion Tamper",
            id="legacy_tamper_on_non_security_device",
        ),
    ],
)
async def test_invalid_trigger(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    event: EventTestData,
    trigger_type: str,
    trigger_subtype: str,
) -> None:
    """Test that unknown subtypes and misplaced legacy tamper subtypes are rejected."""
    mock_entry = await setup_entry(hass, {event.code: {"fire_event": True}})

    device_entry = device_registry.async_get_device_by_identifier(
        get_device_identifier(mock_entry, event.device_identifier[1]),
        mock_entry.entry_id,
    )
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
                        "type": trigger_type,
                        "subtype": trigger_subtype,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "{{trigger.platform}}"},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert f"Subtype {trigger_subtype} not found in device triggers" in caplog.text
