"""The tests for Shelly device triggers."""

from unittest.mock import Mock

from aioshelly.const import MODEL_BUTTON1
import pytest
from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.shelly.const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    CONF_SUBTYPE,
    DOMAIN,
    EVENT_SHELLY_CLICK,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import init_integration

from tests.common import async_get_device_automations


@pytest.mark.parametrize(
    ("button_type", "is_valid"),
    [
        ("momentary", True),
        ("momentary_on_release", True),
        ("detached", True),
        ("toggle", False),
    ],
)
async def test_get_triggers_block_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    button_type: str,
    is_valid: bool,
) -> None:
    """Test we get the expected triggers from a shelly block device."""
    monkeypatch.setitem(
        mock_block_device.settings,
        "relays",
        [
            {"btn_type": button_type},
            {"btn_type": "toggle"},
        ],
    )
    entry = await init_integration(hass, 1)
    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    expected_triggers = []
    if is_valid:
        expected_triggers = [
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device.id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: type_,
                CONF_SUBTYPE: "button1",
                "metadata": {},
            }
            for type_ in ("single", "long")
        ]

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    triggers = [value for value in triggers if value["domain"] == DOMAIN]
    assert triggers == unordered(expected_triggers)


async def test_get_triggers_rpc_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, mock_rpc_device: Mock
) -> None:
    """Test we get the expected triggers from a shelly RPC device."""
    entry = await init_integration(hass, 2)
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
            "btn_down",
            "btn_up",
            "single_push",
            "double_push",
            "triple_push",
            "long_push",
        )
    ]

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    triggers = [value for value in triggers if value["domain"] == DOMAIN]
    assert triggers == unordered(expected_triggers)


async def test_get_triggers_button(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, mock_block_device: Mock
) -> None:
    """Test we get the expected triggers from a shelly button."""
    entry = await init_integration(hass, 1, model=MODEL_BUTTON1)
    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    expected_triggers = [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device.id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: trigger_type,
            CONF_SUBTYPE: "button",
            "metadata": {},
        }
        for trigger_type in ("single", "double", "triple", "long")
    ]

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    triggers = [value for value in triggers if value["domain"] == DOMAIN]
    assert triggers == unordered(expected_triggers)


async def test_get_triggers_non_initialized_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test we get the empty triggers for non-initialized devices."""
    monkeypatch.setattr(mock_block_device, "initialized", False)
    entry = await init_integration(hass, 1)
    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    expected_triggers = []

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    triggers = [value for value in triggers if value["domain"] == DOMAIN]
    assert triggers == unordered(expected_triggers)


async def test_get_triggers_for_invalid_device_id(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, mock_block_device: Mock
) -> None:
    """Test error raised for invalid shelly device_id."""
    await init_integration(hass, 1)
    config_entry = await init_integration(hass, 1, data={}, skip_setup=True)
    invalid_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    with pytest.raises(
        InvalidDeviceAutomationConfig,
        match="not found while configuring device automation triggers",
    ):
        await async_get_device_automations(
            hass, DeviceAutomationType.TRIGGER, invalid_device.id
        )


async def test_if_fires_on_click_event_block_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    mock_block_device: Mock,
) -> None:
    """Test for click_event trigger firing for block device."""
    entry = await init_integration(hass, 1)
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
                        CONF_TYPE: "single",
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

    message = {
        CONF_DEVICE_ID: device.id,
        ATTR_CLICK_TYPE: "single",
        ATTR_CHANNEL: 1,
    }
    hass.bus.async_fire(EVENT_SHELLY_CLICK, message)
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "test_trigger_single_click"


async def test_if_fires_on_click_event_rpc_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    mock_rpc_device: Mock,
) -> None:
    """Test for click_event trigger firing for rpc device."""
    entry = await init_integration(hass, 2)
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
                        CONF_TYPE: "single_push",
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
        ATTR_CLICK_TYPE: "single_push",
        ATTR_CHANNEL: 1,
    }
    hass.bus.async_fire(EVENT_SHELLY_CLICK, message)
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "test_trigger_single_push"


async def test_validate_trigger_block_device_not_ready(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test validate trigger config when block device is not ready."""
    monkeypatch.setattr(mock_block_device, "initialized", False)
    entry = await init_integration(hass, 1)
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
                        CONF_TYPE: "single",
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
    message = {
        CONF_DEVICE_ID: device.id,
        ATTR_CLICK_TYPE: "single",
        ATTR_CHANNEL: 1,
    }
    hass.bus.async_fire(EVENT_SHELLY_CLICK, message)
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "test_trigger_single_click"


async def test_validate_trigger_rpc_device_not_ready(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test validate trigger config when RPC device is not ready."""
    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    entry = await init_integration(hass, 2)
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
                        CONF_TYPE: "single_push",
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
        ATTR_CLICK_TYPE: "single_push",
        ATTR_CHANNEL: 1,
    }
    hass.bus.async_fire(EVENT_SHELLY_CLICK, message)
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "test_trigger_single_push"


async def test_validate_trigger_invalid_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_block_device: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test for click_event with invalid triggers."""
    entry = await init_integration(hass, 1)
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
                        CONF_TYPE: "single",
                        CONF_SUBTYPE: "button3",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_single_click"},
                    },
                },
            ]
        },
    )

    assert (
        "Invalid device automation trigger (type, subtype): ('single', 'button3')"
        in caplog.text
    )


async def test_rpc_no_runtime_data(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the device trigger for the RPC device when there is no runtime_data in the entry."""
    entry = await init_integration(hass, 2)
    monkeypatch.delattr(entry, "runtime_data")
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
                        CONF_TYPE: "single_push",
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
        ATTR_CLICK_TYPE: "single_push",
        ATTR_CHANNEL: 1,
    }
    hass.bus.async_fire(EVENT_SHELLY_CLICK, message)
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "test_trigger_single_push"


async def test_block_no_runtime_data(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    service_calls: list[ServiceCall],
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the device trigger for the block device when there is no runtime_data in the entry."""
    entry = await init_integration(hass, 1)
    monkeypatch.delattr(entry, "runtime_data")
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
                        CONF_TYPE: "single",
                        CONF_SUBTYPE: "button1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_single"},
                    },
                },
            ]
        },
    )
    message = {
        CONF_DEVICE_ID: device.id,
        ATTR_CLICK_TYPE: "single",
        ATTR_CHANNEL: 1,
    }
    hass.bus.async_fire(EVENT_SHELLY_CLICK, message)
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "test_trigger_single"
