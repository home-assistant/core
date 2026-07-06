"""Tests for Easywave purpose-specific triggers."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.easywave.const import (
    CONF_BUTTON_COUNT,
    CONF_ENTRY_TYPE,
    CONF_GROUPING_MODE,
    CONF_OPERATING_TYPE,
    CONF_SWITCH_MODE,
    CONF_TRANSMITTER_SERIAL,
    DOMAIN,
    ENTRY_TYPE_TRANSMITTER,
    EVENT_EASYWAVE,
    EVENT_TYPE_BUTTON_PRESS,
    EVENT_TYPE_GATEWAY_CONNECTED,
    TRANSMITTER_GROUPING_GROUP,
    TRANSMITTER_SWITCH_IMPULSE,
)
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_ENTRY_DATA,
    MOCK_TRANSMITTER_DEVICE_ID,
    MOCK_TRANSMITTER_SERIAL,
    _device_record,
)

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


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


async def _async_setup_entry(
    hass: HomeAssistant,
    *,
    button_count: int = 2,
) -> MockConfigEntry:
    """Set up an Easywave config entry with a group transmitter."""
    entry = MockConfigEntry(
        version=2,
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options={
            CONF_DEVICES: [
                _device_record(
                    MOCK_TRANSMITTER_DEVICE_ID,
                    "Test Transmitter",
                    {
                        CONF_ENTRY_TYPE: ENTRY_TYPE_TRANSMITTER,
                        CONF_TRANSMITTER_SERIAL: MOCK_TRANSMITTER_SERIAL,
                        CONF_OPERATING_TYPE: "1",
                        CONF_BUTTON_COUNT: button_count,
                        CONF_GROUPING_MODE: TRANSMITTER_GROUPING_GROUP,
                        CONF_SWITCH_MODE: TRANSMITTER_SWITCH_IMPULSE,
                    },
                )
            ]
        },
    )
    entry.add_to_hass(hass)
    hass.config.country = "DE"
    t_patch, c_patch, _ = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_easywave_button_press_a_trigger_fires(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Purpose-specific easywave.button_press_a trigger fires on matching events."""
    await _async_setup_entry(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)}
    )
    assert device is not None

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "trigger": "easywave.button_press_a",
                    "target": {"device_id": device.id},
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


async def test_easywave_gateway_connected_trigger_fires(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Purpose-specific easywave.gateway_connected trigger fires on matching events."""
    entry = await _async_setup_entry(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "trigger": "easywave.gateway_connected",
                    "target": {"device_id": device.id},
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_EASYWAVE,
        {
            "device_id": device.id,
            "type": EVENT_TYPE_GATEWAY_CONNECTED,
            "subtype": "connected",
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1


async def test_get_triggers_for_target_transmitter(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Target-based automation UI lists only configured transmitter button triggers."""
    await _async_setup_entry(hass, button_count=2)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)}
    )
    assert device is not None

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "get_triggers_for_target",
            "target": {"device_id": device.id},
            "expand_group": True,
        }
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert "easywave.button_press_a" in msg["result"]
    assert "easywave.button_press_b" in msg["result"]
    assert "easywave.button_release" in msg["result"]
    assert "easywave.button_press_c" not in msg["result"]
    assert "easywave.button_press_d" not in msg["result"]
    assert "easywave.gateway_connected" not in msg["result"]
    assert "easywave.battery_low" not in msg["result"]


async def test_get_triggers_for_target_gateway(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Gateway devices list connection triggers but not transmitter button triggers."""
    entry = await _async_setup_entry(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "get_triggers_for_target",
            "target": {"device_id": device.id},
            "expand_group": True,
        }
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert "easywave.gateway_connected" in msg["result"]
    assert "easywave.gateway_disconnected" in msg["result"]
    assert "easywave.button_press_a" not in msg["result"]
    assert "easywave.button_release" not in msg["result"]
