"""Test Xiaomi BLE events."""

import pytest

from homeassistant.components import automation
from homeassistant.components.bluetooth.const import DOMAIN as BLUETOOTH_DOMAIN
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.xiaomi_ble.const import CONF_SUBTYPE, DOMAIN
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    async_get as async_get_dev_reg,
)
from homeassistant.setup import async_setup_component

from . import make_advertisement

from tests.common import (
    Any,
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


async def _async_setup_xiaomi_device(hass, mac: str, data: Any | None = None):
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id=mac, data=data)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


async def test_event_button_press(hass: HomeAssistant) -> None:
    """Make sure that a button press event is fired."""
    mac = "54:EF:44:E3:9C:BC"
    data = {"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"}
    entry = await _async_setup_xiaomi_device(hass, mac, data)
    events = async_capture_events(hass, "xiaomi_ble_event")

    # Emit button press event
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            mac,
            b'XY\x97\td\xbc\x9c\xe3D\xefT" `' b"\x88\xfd\x00\x00\x00\x00:\x14\x8f\xb3",
        ),
    )

    # wait for the event
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["address"] == "54:EF:44:E3:9C:BC"
    assert events[0].data["event_type"] == "press"
    assert events[0].data["event_properties"] is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_event_unlock_outside_the_door(hass: HomeAssistant) -> None:
    """Make sure that a unlock outside the door event is fired."""
    mac = "D7:1F:44:EB:8A:91"
    entry = await _async_setup_xiaomi_device(hass, mac)
    events = async_capture_events(hass, "xiaomi_ble_event")

    # Emit button press event
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            mac,
            b"PD\x9e\x06C\x91\x8a\xebD\x1f\xd7\x0b\x00\t" b" \x02\x00\x01\x80|D/a",
        ),
    )

    # wait for the event
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["address"] == "D7:1F:44:EB:8A:91"
    assert events[0].data["event_type"] == "unlock_outside_the_door"
    assert events[0].data["event_properties"] is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_event_successful_fingerprint_match_the_door(hass: HomeAssistant) -> None:
    """Make sure that a successful fingerprint match event is fired."""
    mac = "D7:1F:44:EB:8A:91"
    entry = await _async_setup_xiaomi_device(hass, mac)
    events = async_capture_events(hass, "xiaomi_ble_event")

    # Emit button press event
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            mac,
            b"PD\x9e\x06B\x91\x8a\xebD\x1f\xd7" b"\x06\x00\x05\xff\xff\xff\xff\x00",
        ),
    )

    # wait for the event
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["address"] == "D7:1F:44:EB:8A:91"
    assert events[0].data["event_type"] == "match_successful"
    assert events[0].data["event_properties"] is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


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


async def test_event_dimmer_rotate(hass: HomeAssistant) -> None:
    """Make sure that a dimmer rotate event is fired."""
    mac = "F8:24:41:C5:98:8B"
    data = {"bindkey": "b853075158487ca39a5b5ea9"}
    entry = await _async_setup_xiaomi_device(hass, mac, data)
    events = async_capture_events(hass, "xiaomi_ble_event")

    # Emit dimmer rotate left with 3 steps event
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            mac, b"X0\xb6\x036\x8b\x98\xc5A$\xf8\x8b\xb8\xf2f" b"\x13Q\x00\x00\x00\xd6"
        ),
    )

    # wait for the event
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["address"] == "F8:24:41:C5:98:8B"
    assert events[0].data["event_type"] == "rotate_left"
    assert events[0].data["event_properties"] == {"steps": 1}

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_get_triggers_button(hass: HomeAssistant) -> None:
    """Test that we get the expected triggers from a Xiaomi BLE button sensor."""
    mac = "54:EF:44:E3:9C:BC"
    data = {"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"}
    entry = await _async_setup_xiaomi_device(hass, mac, data)
    events = async_capture_events(hass, "xiaomi_ble_event")

    # Emit button press event so it creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            mac,
            b'XY\x97\td\xbc\x9c\xe3D\xefT" `' b"\x88\xfd\x00\x00\x00\x00:\x14\x8f\xb3",
        ),
    )

    # wait for the event
    await hass.async_block_till_done()
    assert len(events) == 1

    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(identifiers={get_device_id(mac)})
    assert device
    expected_trigger = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: device.id,
        CONF_TYPE: "button",
        CONF_SUBTYPE: "press",
        "metadata": {},
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert expected_trigger in triggers

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_get_triggers_double_button(hass: HomeAssistant) -> None:
    """Test that we get the expected triggers from a Xiaomi BLE switch with 2 buttons."""
    mac = "DC:ED:83:87:12:73"
    data = {"bindkey": "b93eb3787eabda352edd94b667f5d5a9"}
    entry = await _async_setup_xiaomi_device(hass, mac, data)
    events = async_capture_events(hass, "xiaomi_ble_event")

    # Emit button press event so it creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            mac,
            b"XYI\x19Os\x12\x87\x83\xed\xdc\x0b48\n\x02\x00\x00\x8dI\xae(",
        ),
    )

    # wait for the event
    await hass.async_block_till_done()
    assert len(events) == 1

    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(identifiers={get_device_id(mac)})
    assert device
    expected_trigger = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: device.id,
        CONF_TYPE: "button_right",
        CONF_SUBTYPE: "long_press",
        "metadata": {},
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert expected_trigger in triggers

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_get_triggers_lock(hass: HomeAssistant) -> None:
    """Test that we get the expected triggers from a Xiaomi BLE lock with fingerprint scanner."""
    mac = "98:0C:33:A3:04:3D"
    data = {"bindkey": "54d84797cb77f9538b224b305c877d1e"}
    entry = await _async_setup_xiaomi_device(hass, mac, data)
    events = async_capture_events(hass, "xiaomi_ble_event")

    # Emit unlock inside the door event so it creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            mac,
            b"\x48\x55\xc2\x11\x16\x50\x68\xb6\xfe\x3c\x87"
            b"\x80\x95\xc8\xa5\x83\x4f\x00\x00\x00\x46\x32\x21\xc6",
        ),
    )

    # wait for the event
    await hass.async_block_till_done()
    assert len(events) == 1

    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(identifiers={get_device_id(mac)})
    assert device
    expected_trigger = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: device.id,
        CONF_TYPE: "fingerprint",
        CONF_SUBTYPE: "skin_is_too_dry",
        "metadata": {},
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert expected_trigger in triggers

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_get_triggers_motion(hass: HomeAssistant) -> None:
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

    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(identifiers={get_device_id(mac)})
    assert device
    expected_trigger = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: device.id,
        CONF_TYPE: "motion",
        CONF_SUBTYPE: "motion_detected",
        "metadata": {},
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device.id
    )
    assert expected_trigger in triggers

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_get_triggers_for_invalid_xiami_ble_device(hass: HomeAssistant) -> None:
    """Test that we don't get triggers for an device that does not emit events."""
    mac = "C4:7C:8D:6A:3E:7A"
    entry = await _async_setup_xiaomi_device(hass, mac)
    events = async_capture_events(hass, "xiaomi_ble_event")

    # Creates the device in the registry but no events
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(mac, b"q \x5d\x01iz>j\x8d|\xc4\r\x10\x10\x02\xf4\x00"),
    )

    # wait to make sure there are no events
    await hass.async_block_till_done()
    assert len(events) == 0

    dev_reg = async_get_dev_reg(hass)
    invalid_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "invdevmac")},
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, invalid_device.id
    )
    assert triggers == []

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_get_triggers_for_invalid_device_id(hass: HomeAssistant) -> None:
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

    dev_reg = async_get_dev_reg(hass)

    invalid_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert invalid_device
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, invalid_device.id
    )
    assert triggers == []

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_if_fires_on_button_press(hass: HomeAssistant, calls) -> None:
    """Test for button press event trigger firing."""
    mac = "54:EF:44:E3:9C:BC"
    data = {"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"}
    entry = await _async_setup_xiaomi_device(hass, mac, data)

    # Creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            mac,
            b"XY\x97\tf\xbc\x9c\xe3D\xefT\x01" b"\x08\x12\x05\x00\x00\x00q^\xbe\x90",
        ),
    )

    # wait for the device being created
    await hass.async_block_till_done()

    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(identifiers={get_device_id(mac)})
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
                        CONF_TYPE: "button",
                        CONF_SUBTYPE: "press",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_button_press"},
                    },
                },
            ]
        },
    )
    # Emit button press event
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            mac,
            b'XY\x97\td\xbc\x9c\xe3D\xefT" `' b"\x88\xfd\x00\x00\x00\x00:\x14\x8f\xb3",
        ),
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "test_trigger_button_press"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_if_fires_on_double_button_long_press(hass: HomeAssistant, calls) -> None:
    """Test for button press event trigger firing."""
    mac = "DC:ED:83:87:12:73"
    data = {"bindkey": "b93eb3787eabda352edd94b667f5d5a9"}
    entry = await _async_setup_xiaomi_device(hass, mac, data)

    # Emit left button press event so it creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            mac,
            b"XYI\x19Ks\x12\x87\x83\xed\xdc!\xad\xb4\xcd\x02\x00\x00,\xf3\xd9\x83",
        ),
    )

    # wait for the device being created
    await hass.async_block_till_done()

    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(identifiers={get_device_id(mac)})
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
                        CONF_TYPE: "button_right",
                        CONF_SUBTYPE: "press",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_right_button_press"},
                    },
                },
            ]
        },
    )
    # Emit right button press event
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(
            mac,
            b"XYI\x19Ps\x12\x87\x83\xed\xdc\x13~~\xbe\x02\x00\x00\xf0\\;4",
        ),
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "test_trigger_right_button_press"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_if_fires_on_motion_detected(hass: HomeAssistant, calls) -> None:
    """Test for motion event trigger firing."""
    mac = "DE:70:E8:B2:39:0C"
    entry = await _async_setup_xiaomi_device(hass, mac)

    # Creates the device in the registry
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(mac, b"@0\xdd\x03$\x0a\x10\x01\x64"),
    )

    # wait for the device being created
    await hass.async_block_till_done()

    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(identifiers={get_device_id(mac)})
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
                        CONF_TYPE: "motion",
                        CONF_SUBTYPE: "motion_detected",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "test_trigger_motion_detected"},
                    },
                },
            ]
        },
    )
    # Emit motion detected event
    inject_bluetooth_service_info_bleak(
        hass,
        make_advertisement(mac, b"@0\xdd\x03$\x03\x00\x01\x01"),
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["some"] == "test_trigger_motion_detected"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_automation_with_invalid_trigger_type(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
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

    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(identifiers={get_device_id(mac)})
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
                        CONF_SUBTYPE: None,
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

    dev_reg = async_get_dev_reg(hass)
    device = dev_reg.async_get_device(identifiers={get_device_id(mac)})
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
                        CONF_TYPE: "motion",
                        CONF_SUBTYPE: "invalid_subtype",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "test_trigger_motion_motion_detected"
                        },
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()
    # Logs should return message to make sure subtype is of one 'motion_detected' for motion event
    assert "value must be one of ['motion_detected']" in caplog.text

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_triggers_for_invalid__model(hass: HomeAssistant, calls) -> None:
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
    dev_reg = async_get_dev_reg(hass)
    invalid_model = dev_reg.async_get_or_create(
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
                        CONF_TYPE: "motion",
                        CONF_SUBTYPE: "motion_detected",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "test_trigger_motion_motion_detected"
                        },
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
