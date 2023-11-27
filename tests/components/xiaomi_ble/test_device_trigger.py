"""Test Xiaomi BLE events."""
import pytest

from homeassistant.components import automation
from homeassistant.components.bluetooth.const import DOMAIN as BLUETOOTH_DOMAIN
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.xiaomi_ble.const import (
    CONF_EVENT_PROPERTIES,
    DOMAIN,
    EVENT_PROPERTIES,
    EVENT_TYPE,
    XIAOMI_BLE_EVENT,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import make_advertisement

from tests.common import (
    MockConfigEntry,
    async_capture_events,
    async_get_device_automations,
    async_mock_service,
)
from tests.components.bluetooth import inject_bluetooth_service_info_bleak


@callback
def get_device_id(mac: str) -> tuple[str, str]:
    """Get device registry identifier for xiaomi_ble."""
    return (BLUETOOTH_DOMAIN, mac)


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def _async_setup_xiaomi_device(hass, mac: str):
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=mac,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


async def test_event_motion_detected(hass: HomeAssistant) -> None:
    """Make sure that a motion detected event is fired."""
    mac = "DE:70:E8:B2:39:0C"
    entry = await _async_setup_xiaomi_device(hass, mac)
    events = async_capture_events(hass, "xiaomi_ble_event")

    # Emit motion detected event
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(mac, b"@0\xdd\x03$\x03\x00\x01\x01"),
    )

    # wait for the event
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["address"] == "DE:70:E8:B2:39:0C"
    assert events[0].data["event_type"] == "motion_detected"
    assert events[0].data["event_properties"] is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_get_triggers(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that we get the expected triggers from a Xiaomi BLE motion sensor."""
    mac = "DE:70:E8:B2:39:0C"
    entry = await _async_setup_xiaomi_device(hass, mac)
    events = async_capture_events(hass, "xiaomi_ble_event")

    # Emit motion detected event so it creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(mac, b"@0\xdd\x03$\x03\x00\x01\x01"),
    )

    # wait for the event
    await hass.async_block_till_done()
    assert len(events) == 1

    device = device_registry.async_get_device(identifiers={get_device_id(mac)})
    assert device
    expected_trigger = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: device.id,
        CONF_TYPE: "motion_detected",
        CONF_EVENT_PROPERTIES: None,
        "metadata": {},
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert expected_trigger in triggers

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_get_triggers_for_invalid_xiami_ble_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that we don't get triggers for an invalid device."""
    mac = "DE:70:E8:B2:39:0C"
    entry = await _async_setup_xiaomi_device(hass, mac)
    events = async_capture_events(hass, "xiaomi_ble_event")

    # Emit motion detected event so it creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(mac, b"@0\xdd\x03$\x03\x00\x01\x01"),
    )

    # wait for the event
    await hass.async_block_till_done()
    assert len(events) == 1

    invalid_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "invdevmac")},
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, invalid_device.id
    )
    assert triggers == []

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_get_triggers_for_invalid_device_id(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that we don't get triggers when using an invalid device_id."""
    mac = "DE:70:E8:B2:39:0C"
    entry = await _async_setup_xiaomi_device(hass, mac)

    # Emit motion detected event so it creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(mac, b"@0\xdd\x03$\x03\x00\x01\x01"),
    )

    # wait for the event
    await hass.async_block_till_done()

    invalid_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert invalid_device
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, invalid_device.id
    )
    assert triggers == []

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_if_fires_on_motion_detected(
    hass: HomeAssistant, calls, device_registry: dr.DeviceRegistry
) -> None:
    """Test for motion event trigger firing."""
    mac = "DE:70:E8:B2:39:0C"
    entry = await _async_setup_xiaomi_device(hass, mac)

    # Emit motion detected event so it creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(mac, b"@0\xdd\x03$\x03\x00\x01\x01"),
    )

    # wait for the event
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={get_device_id(mac)})
    device_id = device.id

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_TYPE: "motion_detected",
                        CONF_EVENT_PROPERTIES: None,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_motion_detected"},
                    },
                },
            ]
        },
    )

    message = {
        CONF_DEVICE_ID: device_id,
        CONF_ADDRESS: "DE:70:E8:B2:39:0C",
        EVENT_TYPE: "motion_detected",
        EVENT_PROPERTIES: None,
    }

    hass.bus.async_fire(XIAOMI_BLE_EVENT, message)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "test_trigger_motion_detected"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_automation_with_invalid_trigger_type(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test for automation with invalid trigger type."""
    mac = "DE:70:E8:B2:39:0C"
    entry = await _async_setup_xiaomi_device(hass, mac)

    # Emit motion detected event so it creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(mac, b"@0\xdd\x03$\x03\x00\x01\x01"),
    )

    # wait for the event
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={get_device_id(mac)})
    device_id = device.id

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_TYPE: "invalid",
                        CONF_EVENT_PROPERTIES: None,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_motion_detected"},
                    },
                },
            ]
        },
    )
    # Logs should return message to make sure event type is of one ["motion_detected"]
    assert "motion_detected" in caplog.text

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_automation_with_invalid_trigger_event_property(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test for automation with invalid trigger event property."""
    mac = "DE:70:E8:B2:39:0C"
    entry = await _async_setup_xiaomi_device(hass, mac)

    # Emit motion detected event so it creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(mac, b"@0\xdd\x03$\x03\x00\x01\x01"),
    )

    # wait for the event
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={get_device_id(mac)})
    device_id = device.id

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_TYPE: "motion_detected",
                        CONF_EVENT_PROPERTIES: "invalid_property",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_motion_detected"},
                    },
                },
            ]
        },
    )
    # Logs should return message to make sure event property is of one [None] for motion event
    assert str([None]) in caplog.text

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_triggers_for_invalid__model(
    hass: HomeAssistant, calls, device_registry: dr.DeviceRegistry
) -> None:
    """Test invalid model doesn't return triggers."""
    mac = "DE:70:E8:B2:39:0C"
    entry = await _async_setup_xiaomi_device(hass, mac)

    # Emit motion detected event so it creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(mac, b"@0\xdd\x03$\x03\x00\x01\x01"),
    )

    # wait for the event
    await hass.async_block_till_done()

    # modify model to invalid model
    invalid_model = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, mac)},
        model="invalid model",
    )
    invalid_model_id = invalid_model.id

    # setup automation to validate trigger config
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: invalid_model_id,
                        CONF_TYPE: "motion_detected",
                        CONF_EVENT_PROPERTIES: None,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_motion_detected"},
                    },
                },
            ]
        },
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, invalid_model_id
    )
    assert triggers == []

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
