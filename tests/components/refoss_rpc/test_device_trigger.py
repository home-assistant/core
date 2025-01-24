"""The tests for refoss_rpc device triggers."""

from unittest.mock import Mock

import pytest
from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.refoss_rpc.const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    CONF_SUBTYPE,
    DOMAIN,
    EVENT_REFOSS_CLICK,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import set_integration

from tests.common import MockConfigEntry, async_get_device_automations


async def test_get_triggers_rpc_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, mock_rpc_device: Mock
) -> None:
    """Test we get the expected triggers from a refoss RPC device."""
    entry = await set_integration(hass)
    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    expected_triggers = [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: trigger_type,
            CONF_SUBTYPE: "button1",
            "metadata": {},
        }
        for trigger_type in (
            "button_down",
            "button_up",
            "button_single_push",
            "button_double_push",
            "button_triple_push",
            "button_long_push",
        )
    ]

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    triggers = [value for value in triggers if value["domain"] == DOMAIN]
    assert triggers == unordered(expected_triggers)


async def test_if_fires_on_click_event_rpc_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    mock_rpc_device: Mock,
) -> None:
    """Test for click_event trigger firing for rpc device."""
    entry = await set_integration(hass)
    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device.id,
                        CONF_TYPE: "button_single_push",
                        CONF_SUBTYPE: "button1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_single_push"},
                    },
                },
            ]
        },
    )

    message = {
        CONF_DEVICE_ID: device.id,
        ATTR_CLICK_TYPE: "button_single_push",
        ATTR_CHANNEL: 1,
    }
    hass.bus.async_fire(EVENT_REFOSS_CLICK, message)
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "test_trigger_button_single_push"


async def test_get_triggers_for_invalid_device_id(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, mock_rpc_device: Mock
) -> None:
    """Test error raised for invalid refoss_rpc device_id."""
    await set_integration(hass)
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    invalid_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "16:34:56:AB:CD:ED")},
    )

    with pytest.raises(InvalidDeviceAutomationConfig):
        await async_get_device_automations(
            hass, DeviceAutomationType.TRIGGER, invalid_device.id
        )


async def test_validate_trigger_rpc_device_not_ready(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test validate trigger config when RPC device is not ready."""
    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    entry = await set_integration(hass)
    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device.id,
                        CONF_TYPE: "button_single_push",
                        CONF_SUBTYPE: "button1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_single_push"},
                    },
                },
            ]
        },
    )
    message = {
        CONF_DEVICE_ID: device.id,
        ATTR_CLICK_TYPE: "button_single_push",
        ATTR_CHANNEL: 1,
    }
    hass.bus.async_fire(EVENT_REFOSS_CLICK, message)
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "test_trigger_single_push"


async def test_validate_trigger_invalid_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test for click_event with invalid triggers."""
    monkeypatch.setattr(mock_rpc_device, "config", {})

    entry = await set_integration(hass)
    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device.id,
                        CONF_TYPE: "button_single_push",
                        CONF_SUBTYPE: "button1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_single_click"},
                    },
                },
            ]
        },
    )

    assert "Invalid (type,subtype): ('button_single_push', 'button1')" in caplog.text
