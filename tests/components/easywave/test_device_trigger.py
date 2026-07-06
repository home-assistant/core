"""Tests for Easywave device triggers."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_unordered import unordered

from homeassistant.components import automation, device_automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.easywave.const import (
    CONF_BUTTON_COUNT,
    CONF_ENTRY_TYPE,
    CONF_GROUPING_MODE,
    CONF_OPERATING_TYPE,
    CONF_SENSOR_CAPABILITIES,
    CONF_SENSOR_SERIAL,
    CONF_SWITCH_MODE,
    CONF_TRANSMITTER_SERIAL,
    DOMAIN,
    ENTRY_TYPE_NEO_SENSOR,
    ENTRY_TYPE_TRANSMITTER,
    EVENT_EASYWAVE,
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_BATTERY_NORMAL,
    EVENT_TYPE_BUTTON_PRESS,
    EVENT_TYPE_BUTTON_RELEASE,
    EVENT_TYPE_GATEWAY_CONNECTED,
    EVENT_TYPE_GATEWAY_DISCONNECTED,
    TRANSMITTER_GROUPING_GROUP,
    TRANSMITTER_SWITCH_IMPULSE,
    TRANSMITTER_SWITCH_PERMANENT,
)
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_ENTRY_DATA,
    MOCK_NEO_SENSOR_DEVICE_ID,
    MOCK_NEO_SENSOR_SERIAL,
    MOCK_TRANSMITTER_DEVICE_ID,
    MOCK_TRANSMITTER_SERIAL,
    _device_record,
)

from tests.common import MockConfigEntry, async_get_device_automations
from tests.typing import WebSocketGenerator

NEO_SENSOR_CAPABILITIES = (1 << 4) | (1 << 5)

CONF_SUBTYPE = "subtype"


def _patch_integration() -> tuple[Any, Any, MagicMock]:
    """Return patches for transceiver and coordinator."""
    mock_transceiver = MagicMock()
    mock_transceiver.is_connected = True
    mock_transceiver.usb_serial_number = "12345"
    mock_transceiver.hw_version = "1.0"
    mock_transceiver.fw_version = "2.0"
    mock_transceiver.device_path = "/dev/ttyACM0"

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.async_shutdown = AsyncMock()
    mock_coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    mock_coordinator.transceiver = mock_transceiver
    mock_coordinator.is_offline = False
    mock_coordinator.register_transmitter_entities = MagicMock()
    mock_coordinator.unregister_transmitter_entity = MagicMock()
    mock_coordinator.data = {"is_connected": True, "device_path": "/dev/ttyACM0"}
    mock_coordinator.ensure_telegram_listener = MagicMock()

    transceiver_patch = patch(
        "homeassistant.components.easywave.RX11Transceiver",
        return_value=mock_transceiver,
    )
    coordinator_patch = patch(
        "homeassistant.components.easywave.EasywaveCoordinator",
        return_value=mock_coordinator,
    )
    return transceiver_patch, coordinator_patch, mock_coordinator


def _make_gateway_entry(
    devices: list[dict[str, Any]] | None = None,
) -> MockConfigEntry:
    """Return a gateway config entry with optional configured devices."""
    return MockConfigEntry(
        version=2,
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options={CONF_DEVICES: devices or []},
    )


async def _async_setup_entry(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up an Easywave config entry with integration patches."""
    entry.add_to_hass(hass)
    hass.config.country = "DE"
    t_patch, c_patch, _ = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_get_gateway_triggers(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Gateway device exposes connected and disconnected triggers."""
    entry = await _async_setup_entry(hass, _make_gateway_entry())
    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None

    expected = [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device.id,
            CONF_TYPE: EVENT_TYPE_GATEWAY_CONNECTED,
            CONF_SUBTYPE: "connected",
            "metadata": {},
        },
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device.id,
            CONF_TYPE: EVENT_TYPE_GATEWAY_DISCONNECTED,
            CONF_SUBTYPE: "disconnected",
            "metadata": {},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert triggers == unordered(expected)


@pytest.mark.parametrize(
    ("switch_mode", "include_release"),
    [
        (TRANSMITTER_SWITCH_IMPULSE, True),
        (TRANSMITTER_SWITCH_PERMANENT, False),
    ],
)
async def test_get_transmitter_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    switch_mode: str,
    include_release: bool,
) -> None:
    """Transmitter exposes button, optional release, and battery triggers."""
    await _async_setup_entry(
        hass,
        _make_gateway_entry(
            [
                _device_record(
                    MOCK_TRANSMITTER_DEVICE_ID,
                    "Test Transmitter",
                    {
                        CONF_ENTRY_TYPE: ENTRY_TYPE_TRANSMITTER,
                        CONF_TRANSMITTER_SERIAL: MOCK_TRANSMITTER_SERIAL,
                        CONF_OPERATING_TYPE: "1",
                        CONF_BUTTON_COUNT: 2,
                        CONF_GROUPING_MODE: TRANSMITTER_GROUPING_GROUP,
                        CONF_SWITCH_MODE: switch_mode,
                    },
                )
            ]
        ),
    )
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)}
    )
    assert device is not None

    expected = [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device.id,
            CONF_TYPE: EVENT_TYPE_BUTTON_PRESS,
            CONF_SUBTYPE: subtype,
            "metadata": {},
        }
        for subtype in ("a", "b")
    ]
    if include_release:
        expected.append(
            {
                CONF_PLATFORM: "device",
                CONF_DOMAIN: DOMAIN,
                CONF_DEVICE_ID: device.id,
                CONF_TYPE: EVENT_TYPE_BUTTON_RELEASE,
                CONF_SUBTYPE: "released",
                "metadata": {},
            }
        )
    expected.extend(
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device.id,
            CONF_TYPE: trigger_type,
            CONF_SUBTYPE: subtype,
            "metadata": {},
        }
        for trigger_type, subtype in (
            (EVENT_TYPE_BATTERY_LOW, "low"),
            (EVENT_TYPE_BATTERY_NORMAL, "ok"),
        )
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert triggers == unordered(expected)


async def test_get_neo_sensor_triggers_empty(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Neo sensors do not expose button or battery device triggers."""
    await _async_setup_entry(
        hass,
        _make_gateway_entry(
            [
                _device_record(
                    MOCK_NEO_SENSOR_DEVICE_ID,
                    "Test Sensor",
                    {
                        CONF_ENTRY_TYPE: ENTRY_TYPE_NEO_SENSOR,
                        CONF_SENSOR_SERIAL: MOCK_NEO_SENSOR_SERIAL,
                        CONF_SENSOR_CAPABILITIES: NEO_SENSOR_CAPABILITIES,
                    },
                )
            ]
        ),
    )
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_NEO_SENSOR_DEVICE_ID)}
    )
    assert device is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    easywave_triggers = [trigger for trigger in triggers if trigger["domain"] == DOMAIN]
    assert easywave_triggers == []


async def test_if_fires_on_button_press(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Device trigger automation fires when easywave_event is received."""
    entry = await _async_setup_entry(
        hass,
        _make_gateway_entry(
            [
                _device_record(
                    MOCK_TRANSMITTER_DEVICE_ID,
                    "Test Transmitter",
                    {
                        CONF_ENTRY_TYPE: ENTRY_TYPE_TRANSMITTER,
                        CONF_TRANSMITTER_SERIAL: MOCK_TRANSMITTER_SERIAL,
                        CONF_OPERATING_TYPE: "1",
                        CONF_BUTTON_COUNT: 1,
                        CONF_GROUPING_MODE: TRANSMITTER_GROUPING_GROUP,
                        CONF_SWITCH_MODE: TRANSMITTER_SWITCH_IMPULSE,
                    },
                )
            ]
        ),
    )
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)}
    )
    assert device is not None

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "device",
                    CONF_DOMAIN: DOMAIN,
                    CONF_DEVICE_ID: device.id,
                    CONF_TYPE: EVENT_TYPE_BUTTON_PRESS,
                    CONF_SUBTYPE: "a",
                },
                "action": {
                    "service": "test.automation",
                    "data": {"subtype": "{{ trigger.event.data.subtype }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_EASYWAVE,
        {
            "device_id": device.id,
            "type": EVENT_TYPE_BUTTON_PRESS,
            "subtype": "a",
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["subtype"] == "a"
    assert entry.entry_id


async def test_websocket_list_transmitter_triggers(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Device triggers are exposed via the device_automation websocket API."""
    await _async_setup_entry(
        hass,
        _make_gateway_entry(
            [
                _device_record(
                    MOCK_TRANSMITTER_DEVICE_ID,
                    "Test Transmitter",
                    {
                        CONF_ENTRY_TYPE: ENTRY_TYPE_TRANSMITTER,
                        CONF_TRANSMITTER_SERIAL: MOCK_TRANSMITTER_SERIAL,
                        CONF_OPERATING_TYPE: "1",
                        CONF_BUTTON_COUNT: 2,
                        CONF_GROUPING_MODE: TRANSMITTER_GROUPING_GROUP,
                        CONF_SWITCH_MODE: TRANSMITTER_SWITCH_IMPULSE,
                    },
                )
            ]
        ),
    )
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)}
    )
    assert device is not None

    assert await async_setup_component(hass, device_automation.DOMAIN, {})
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/trigger/list",
            "device_id": device.id,
        }
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    easywave_triggers = [t for t in msg["result"] if t["domain"] == DOMAIN]
    assert len(easywave_triggers) == 5
