"""Tests for Easywave device triggers."""

import pytest
from pytest_unordered import unordered

from homeassistant.components import automation, device_automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.easywave import device_trigger
from homeassistant.components.easywave.const import (
    CONF_DEVICE_DATA,
    CONF_DEVICE_TITLE,
    DOMAIN,
    EVENT_EASYWAVE,
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_BATTERY_NORMAL,
    EVENT_TYPE_BUTTON_PRESS,
    EVENT_TYPE_BUTTON_RELEASE,
    EVENT_TYPE_GATEWAY_CONNECTED,
    EVENT_TYPE_GATEWAY_DISCONNECTED,
    TRANSMITTER_SWITCH_IMPULSE,
    TRANSMITTER_SWITCH_PERMANENT,
)
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.config_entries import ConfigSubentryData
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
    MOCK_ENTRY_ID,
    MOCK_GATEWAY_TITLE,
    MOCK_NEO_SENSOR_DEVICE_ID,
    MOCK_TRANSMITTER_DEVICE_ID,
    _devices_options,
    _neo_sensor_device_record,
    _transmitter_device_record,
    async_setup_easywave_entry,
)

from tests.common import MockConfigEntry, async_get_device_automations
from tests.typing import WebSocketGenerator

NEO_SENSOR_CAPABILITIES = (1 << 4) | (1 << 5)

CONF_SUBTYPE = "subtype"


def _make_gateway_entry(*device_records: ConfigSubentryData) -> MockConfigEntry:
    """Return a gateway config entry with optional configured devices."""
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        title=MOCK_GATEWAY_TITLE,
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options=_devices_options(*device_records) if device_records else {},
    )


async def _async_setup_entry(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up an Easywave config entry with integration patches."""
    await async_setup_easywave_entry(hass, entry)
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
            _transmitter_device_record(
                button_count=2,
                title="Test Transmitter",
                switch_mode=switch_mode,
            )
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
            _neo_sensor_device_record(
                title="Test Sensor",
                capabilities=NEO_SENSOR_CAPABILITIES,
            )
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
            _transmitter_device_record(
                button_count=1,
                title="Test Transmitter",
            )
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
            _transmitter_device_record(
                button_count=2,
                title="Test Transmitter",
            )
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


async def test_get_triggers_returns_empty_for_unknown_device(
    hass: HomeAssistant,
) -> None:
    """Unknown device IDs return no triggers."""
    assert await device_trigger.async_get_triggers(hass, "does-not-exist") == []


async def test_get_triggers_returns_empty_for_non_easywave_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Devices without an Easywave identifier return no triggers."""
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other", "device")},
    )
    triggers = await device_trigger.async_get_triggers(hass, device.id)
    assert triggers == []


async def test_get_triggers_returns_empty_for_unconfigured_easywave_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Easywave identifiers without stored device data return no triggers."""
    entry = await _async_setup_entry(hass, _make_gateway_entry())
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "transmitter_not_configured")},
    )
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert [trigger for trigger in triggers if trigger["domain"] == DOMAIN] == []


async def test_get_triggers_returns_empty_for_missing_device(
    hass: HomeAssistant,
) -> None:
    """Unknown device ids return no triggers."""
    assert await device_trigger.async_get_triggers(hass, "missing-device") == []


async def test_get_trigger_capabilities(hass: HomeAssistant) -> None:
    """Device trigger capabilities are empty for Easywave."""
    assert await device_trigger.async_get_trigger_capabilities(hass, {}) == {}


@pytest.mark.parametrize(
    "device_data",
    [
        pytest.param(None, id="missing"),
        pytest.param("invalid", id="non_dict"),
    ],
)
async def test_get_triggers_ignores_malformed_stored_device_data(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    device_data: object,
) -> None:
    """Malformed stored device data does not produce transmitter triggers."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        title=MOCK_GATEWAY_TITLE,
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options={
            CONF_DEVICES: [
                {
                    CONF_DEVICE_ID: MOCK_TRANSMITTER_DEVICE_ID,
                    CONF_DEVICE_TITLE: "Transmitter",
                    CONF_DEVICE_DATA: device_data,
                }
            ]
        },
    )
    await async_setup_easywave_entry(hass, entry)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)},
        name="Transmitter",
    )
    triggers = await device_trigger.async_get_triggers(hass, device.id)
    assert triggers == []
