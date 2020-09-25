"""The tests for RFXCOM RFXtrx device triggers."""
from typing import NamedTuple, Set, Tuple

import pytest

import homeassistant.components.automation as automation
from homeassistant.components.rfxtrx import DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
)
from tests.components.rfxtrx.conftest import create_rfx_test_cfg


class EventTestData(NamedTuple):
    """Test data linked to a device."""

    code: str
    device_identifiers: Set[Tuple[str]]
    type: str
    subtype: str


DEVICE_SECURITY_1 = {("rfxtrx", "20", "3", "a10900:32")}
EVENT_SECURITY_1 = EventTestData(
    "08200300a109000670", DEVICE_SECURITY_1, "status", "Panic"
)

DEVICE_CHIME_1 = {("rfxtrx", "16", "0", "00:00")}
EVENT_CHIME_1 = EventTestData(
    "0a16000000000000000000", DEVICE_CHIME_1, "command", "Chime"
)


@pytest.fixture(name="device_reg")
def device_reg_fixture(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


async def setup_entry(hass, devices):
    """Construct a config setup."""
    entry_data = create_rfx_test_cfg(devices=devices)
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_start()


@pytest.mark.parametrize(
    "event,expected",
    [
        [
            EVENT_SECURITY_1,
            [
                {"type": "status", "subtype": subtype}
                for subtype in [
                    "Normal",
                    "Normal Delayed",
                    "Alarm",
                    "Alarm Delayed",
                    "Motion",
                    "No Motion",
                    "Panic",
                    "End Panic",
                    "IR",
                    "Arm Away",
                    "Arm Away Delayed",
                    "Arm Home",
                    "Arm Home Delayed",
                    "Disarm",
                    "Light 1 Off",
                    "Light 1 On",
                    "Light 2 Off",
                    "Light 2 On",
                    "Dark Detected",
                    "Light Detected",
                    "Battery low",
                    "Pairing KD101",
                    "Normal Tamper",
                    "Normal Delayed Tamper",
                    "Alarm Tamper",
                    "Alarm Delayed Tamper",
                    "Motion Tamper",
                    "No Motion Tamper",
                ]
            ],
        ]
    ],
)
async def test_get_triggers(hass, device_reg, event: EventTestData, expected):
    """Test we get the expected triggers from a rfxtrx."""
    await setup_entry(hass, {event.code: {}})

    device_entry = device_reg.async_get_device(event.device_identifiers, set())

    expected_triggers = [
        {"domain": DOMAIN, "device_id": device_entry.id, "platform": "device", **expect}
        for expect in expected
    ]

    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    triggers = [value for value in triggers if value["domain"] == "rfxtrx"]
    assert_lists_same(triggers, expected_triggers)


@pytest.mark.parametrize(
    "event",
    [
        EVENT_SECURITY_1,
        EVENT_CHIME_1,
    ],
)
async def test_firing_event(hass, device_reg, rfxtrx, event):
    """Test for turn_on and turn_off triggers firing."""

    await setup_entry(hass, {event.code: {"fire_event": True}})

    device_entry = device_reg.async_get_device(event.device_identifiers, set())

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
