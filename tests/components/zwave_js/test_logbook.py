"""The tests for Z-Wave JS logbook."""
from zwave_js_server.const import CommandClass

from homeassistant.components.zwave_js.const import (
    ZWAVE_JS_NOTIFICATION_EVENT,
    ZWAVE_JS_VALUE_NOTIFICATION_EVENT,
)
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.components.logbook.common import MockRow, mock_humanify


async def test_humanifying_zwave_js_notification_event(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test humanifying Z-Wave JS notification events."""
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(
        identifiers={get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device

    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})

    events = mock_humanify(
        hass,
        [
            MockRow(
                ZWAVE_JS_NOTIFICATION_EVENT,
                {
                    "device_id": device.id,
                    "command_class": CommandClass.NOTIFICATION.value,
                    "command_class_name": "Notification",
                    "label": "label",
                    "event_label": "event_label",
                },
            ),
            MockRow(
                ZWAVE_JS_NOTIFICATION_EVENT,
                {
                    "device_id": device.id,
                    "command_class": CommandClass.ENTRY_CONTROL.value,
                    "command_class_name": "Entry Control",
                    "event_type": 1,
                    "data_type": 2,
                },
            ),
            MockRow(
                ZWAVE_JS_NOTIFICATION_EVENT,
                {
                    "device_id": device.id,
                    "command_class": CommandClass.SWITCH_MULTILEVEL.value,
                    "command_class_name": "Multilevel Switch",
                    "event_type": 1,
                    "direction": "up",
                },
            ),
            MockRow(
                ZWAVE_JS_NOTIFICATION_EVENT,
                {
                    "device_id": device.id,
                    "command_class": CommandClass.POWERLEVEL.value,
                    "command_class_name": "Powerlevel",
                },
            ),
        ],
    )

    assert events[0]["name"] == "Touchscreen Deadbolt"
    assert events[0]["domain"] == "zwave_js"
    assert (
        events[0]["message"]
        == "fired Notification CC 'notification' event 'label': 'event_label'"
    )

    assert events[1]["name"] == "Touchscreen Deadbolt"
    assert events[1]["domain"] == "zwave_js"
    assert events[1]["message"] == (
        "fired Entry Control CC 'notification' event for event type '1' "
        "with data type '2'"
    )

    assert events[2]["name"] == "Touchscreen Deadbolt"
    assert events[2]["domain"] == "zwave_js"
    assert (
        events[2]["message"]
        == "fired Multilevel Switch CC 'notification' event for event type '1': 'up'"
    )

    assert events[3]["name"] == "Touchscreen Deadbolt"
    assert events[3]["domain"] == "zwave_js"
    assert events[3]["message"] == "fired Powerlevel CC 'notification' event"


async def test_humanifying_zwave_js_value_notification_event(
    hass: HomeAssistant, client, lock_schlage_be469, integration
) -> None:
    """Test humanifying Z-Wave JS value notification events."""
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(
        identifiers={get_device_id(client.driver, lock_schlage_be469)}
    )
    assert device

    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})

    events = mock_humanify(
        hass,
        [
            MockRow(
                ZWAVE_JS_VALUE_NOTIFICATION_EVENT,
                {
                    "device_id": device.id,
                    "command_class": CommandClass.SCENE_ACTIVATION.value,
                    "command_class_name": "Scene Activation",
                    "label": "Scene ID",
                    "value": "001",
                },
            ),
        ],
    )

    assert events[0]["name"] == "Touchscreen Deadbolt"
    assert events[0]["domain"] == "zwave_js"
    assert (
        events[0]["message"]
        == "fired Scene Activation CC 'value notification' event for 'Scene ID': '001'"
    )
