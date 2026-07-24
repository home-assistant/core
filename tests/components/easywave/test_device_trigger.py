"""Tests for Easywave device triggers."""

import pytest
from pytest_unordered import unordered

from homeassistant.components import automation, device_automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.easywave import device_trigger
from homeassistant.components.easywave.const import (
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
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_NEO_SENSOR_DEVICE_ID,
    MOCK_TRANSMITTER_DEVICE_ID,
    _entry_with_subentries,
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
    return _entry_with_subentries(*device_records)


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
    ("switch_mode", "release_subtypes"),
    [
        (TRANSMITTER_SWITCH_IMPULSE, ("released",)),
        (TRANSMITTER_SWITCH_PERMANENT, ()),
    ],
)
async def test_get_transmitter_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    switch_mode: str,
    release_subtypes: tuple[str, ...],
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
    expected.extend(
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device.id,
            CONF_TYPE: EVENT_TYPE_BUTTON_RELEASE,
            CONF_SUBTYPE: subtype,
            "metadata": {},
        }
        for subtype in release_subtypes
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


async def test_get_triggers_resolves_entry_via_gateway_parent(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Transmitters linked only via via_device still expose device triggers."""
    entry = _make_gateway_entry(
        _transmitter_device_record(button_count=1, title="Stored Device Transmitter")
    )
    await async_setup_easywave_entry(hass, entry)
    transmitter = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)}
    )
    assert transmitter is not None
    device_registry.async_remove_device(transmitter.id)

    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Gateway",
    )
    child = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)},
        via_device=(DOMAIN, entry.entry_id),
        name="Transmitter",
    )

    triggers = await device_trigger.async_get_triggers(hass, child.id)

    assert any(trigger[CONF_TYPE] == EVENT_TYPE_BUTTON_PRESS for trigger in triggers)


async def test_get_triggers_resolves_stored_device_without_config_entry_link(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Stored device options resolve triggers without a config entry device link."""
    entry = _make_gateway_entry(
        _transmitter_device_record(button_count=1, title="Stored Device Transmitter")
    )
    await async_setup_easywave_entry(hass, entry)
    transmitter = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)}
    )
    assert transmitter is not None
    device_registry.async_remove_device(transmitter.id)

    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    orphan = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={(DOMAIN, MOCK_TRANSMITTER_DEVICE_ID)},
        name="Transmitter",
    )

    triggers = await device_trigger.async_get_triggers(hass, orphan.id)

    assert any(trigger[CONF_TYPE] == EVENT_TYPE_BUTTON_PRESS for trigger in triggers)


async def test_get_gateway_triggers_without_config_entry_link(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Gateway identifiers resolve triggers without a direct config entry link."""
    entry = _make_gateway_entry()
    await async_setup_easywave_entry(hass, entry)
    gateway = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert gateway is not None
    device_registry.async_remove_device(gateway.id)

    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Gateway",
    )

    triggers = await device_trigger.async_get_triggers(hass, device.id)

    assert {trigger[CONF_TYPE] for trigger in triggers} == {
        EVENT_TYPE_GATEWAY_CONNECTED,
        EVENT_TYPE_GATEWAY_DISCONNECTED,
    }


async def test_get_triggers_returns_empty_for_orphan_without_loaded_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Easywave identifiers without a loaded config entry return no triggers."""
    entry = _make_gateway_entry()
    entry.add_to_hass(hass)
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={(DOMAIN, "orphan_device_id")},
    )

    assert await device_trigger.async_get_triggers(hass, device.id) == []


async def test_get_trigger_capabilities(hass: HomeAssistant) -> None:
    """Device trigger capabilities are empty for Easywave."""
    assert await device_trigger.async_get_trigger_capabilities(hass, {}) == {}
