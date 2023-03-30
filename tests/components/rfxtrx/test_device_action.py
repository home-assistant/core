"""The tests for RFXCOM RFXtrx device actions."""
from __future__ import annotations

from typing import Any, NamedTuple

import RFXtrx
import pytest

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.rfxtrx import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import create_rfx_test_cfg

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automations,
)


class DeviceTestData(NamedTuple):
    """Test data linked to a device."""

    code: str
    device_identifiers: set[tuple[str, str, str, str]]


DEVICE_LIGHTING_1 = DeviceTestData("0710002a45050170", {("rfxtrx", "10", "0", "E5")})

DEVICE_BLINDS_1 = DeviceTestData(
    "09190000009ba8010100", {("rfxtrx", "19", "0", "009ba8:1")}
)

DEVICE_TEMPHUM_1 = DeviceTestData(
    "0a52080705020095220269", {("rfxtrx", "52", "8", "05:02")}
)


@pytest.mark.parametrize("device", [DEVICE_LIGHTING_1, DEVICE_TEMPHUM_1])
async def test_device_test_data(rfxtrx, device: DeviceTestData) -> None:
    """Verify that our testing data remains correct."""
    pkt: RFXtrx.lowlevel.Packet = RFXtrx.lowlevel.parse(bytearray.fromhex(device.code))
    assert device.device_identifiers == {
        ("rfxtrx", f"{pkt.packettype:x}", f"{pkt.subtype:x}", pkt.id_string)
    }


async def setup_entry(hass, devices):
    """Construct a config setup."""
    entry_data = create_rfx_test_cfg(devices=devices)
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_start()


def _get_expected_actions(data):
    for value in data.values():
        yield {"type": "send_command", "subtype": value}


@pytest.mark.parametrize(
    ("device", "expected"),
    [
        [
            DEVICE_LIGHTING_1,
            list(_get_expected_actions(RFXtrx.lowlevel.Lighting1.COMMANDS)),
        ],
        [
            DEVICE_BLINDS_1,
            list(_get_expected_actions(RFXtrx.lowlevel.RollerTrol.COMMANDS)),
        ],
        [DEVICE_TEMPHUM_1, []],
    ],
)
async def test_get_actions(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, device, expected
) -> None:
    """Test we get the expected actions from a rfxtrx."""
    await setup_entry(hass, {device.code: {}})

    device_entry = device_registry.async_get_device(device.device_identifiers, set())
    assert device_entry

    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_entry.id
    )
    actions = [action for action in actions if action["domain"] == DOMAIN]

    expected_actions = [
        {"domain": DOMAIN, "device_id": device_entry.id, "metadata": {}, **action_type}
        for action_type in expected
    ]

    assert_lists_same(actions, expected_actions)


@pytest.mark.parametrize(
    ("device", "config", "expected"),
    [
        [
            DEVICE_LIGHTING_1,
            {"type": "send_command", "subtype": "On"},
            "0710000045050100",
        ],
        [
            DEVICE_LIGHTING_1,
            {"type": "send_command", "subtype": "Off"},
            "0710000045050000",
        ],
        [
            DEVICE_BLINDS_1,
            {"type": "send_command", "subtype": "Stop"},
            "09190000009ba8010200",
        ],
    ],
)
async def test_action(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    rfxtrx: RFXtrx.Connect,
    device,
    config,
    expected,
) -> None:
    """Test for actions."""

    await setup_entry(hass, {device.code: {}})

    device_entry = device_registry.async_get_device(device.device_identifiers, set())
    assert device_entry

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        **config,
                    },
                },
            ]
        },
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()

    rfxtrx.transport.send.assert_called_once_with(bytearray.fromhex(expected))


async def test_invalid_action(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test for invalid actions."""
    device = DEVICE_LIGHTING_1

    await setup_entry(hass, {device.code: {}})

    device_identifers: Any = device.device_identifiers
    device_entry = device_registry.async_get_device(device_identifers, set())
    assert device_entry

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "type": "send_command",
                        "subtype": "invalid",
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert "Subtype invalid not found in device commands" in caplog.text
