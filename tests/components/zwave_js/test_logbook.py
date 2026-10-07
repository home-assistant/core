"""The tests for Z-Wave JS logbook."""

import pytest
from zwave_js_server.const import CommandClass

from homeassistant.components.zwave_js.const import (
    DOMAIN,
    ZWAVE_JS_NOTIFICATION_EVENT,
    ZWAVE_JS_VALUE_NOTIFICATION_EVENT,
)
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.logbook.common import MockRow, mock_humanify


async def test_humanifying_zwave_js_notification_event(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469,
    integration,
) -> None:
    """Test humanifying Z-Wave JS notification events."""
    device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, lock_schlage_be469), integration.entry_id
    )
    assert device

    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()

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
            MockRow(
                ZWAVE_JS_NOTIFICATION_EVENT,
                {
                    "device_id": device.id,
                    "command_class": CommandClass.BATTERY.value,
                    "command_class_name": "Battery",
                    "event_type": "battery low",
                    "urgency": 1,
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

    assert events[4]["name"] == "Touchscreen Deadbolt"
    assert events[4]["domain"] == "zwave_js"
    assert events[4]["message"] == "fired Battery CC 'notification' event"


async def test_humanifying_zwave_js_value_notification_event(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client,
    lock_schlage_be469,
    integration,
) -> None:
    """Test humanifying Z-Wave JS value notification events."""
    device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, lock_schlage_be469), integration.entry_id
    )
    assert device

    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()

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


@pytest.fixture(name="nameless_device_id")
def nameless_device_id_fixture(
    request: pytest.FixtureRequest,
    device_registry: dr.DeviceRegistry,
    integration: MockConfigEntry,
) -> str:
    """Return the id of a device that humanify resolves to an empty name."""
    if not request.param:
        # A device id that is not in the registry, e.g. a removed device
        return "removed_device_id"
    # A registered device with neither a user set name nor a device name. A new
    # device defaults its name to the config entry title, so clear it afterwards.
    device = device_registry.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={(DOMAIN, "nameless-node")},
    )
    device = device_registry.async_update_device(device.id, name=None)
    assert device is not None
    assert device.name_by_user is None
    assert device.name is None
    return device.id


@pytest.mark.parametrize(
    "nameless_device_id",
    [
        pytest.param(False, id="removed_device"),
        pytest.param(True, id="unnamed_device"),
    ],
    indirect=True,
)
async def test_humanifying_zwave_js_events_no_device_name(
    hass: HomeAssistant,
    nameless_device_id: str,
) -> None:
    """Test humanifying Z-Wave JS events when the device name is unavailable."""
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()

    events = mock_humanify(
        hass,
        [
            MockRow(
                ZWAVE_JS_NOTIFICATION_EVENT,
                {
                    "device_id": nameless_device_id,
                    "command_class": CommandClass.NOTIFICATION.value,
                    "command_class_name": "Notification",
                    "label": "label",
                    "event_label": "event_label",
                },
            ),
            MockRow(
                ZWAVE_JS_VALUE_NOTIFICATION_EVENT,
                {
                    "device_id": nameless_device_id,
                    "command_class": CommandClass.SCENE_ACTIVATION.value,
                    "command_class_name": "Scene Activation",
                    "label": "Scene ID",
                    "value": "001",
                },
            ),
        ],
    )

    assert events[0]["name"] == ""
    assert events[0]["domain"] == "zwave_js"
    assert (
        events[0]["message"]
        == "fired Notification CC 'notification' event 'label': 'event_label'"
    )

    assert events[1]["name"] == ""
    assert events[1]["domain"] == "zwave_js"
    assert (
        events[1]["message"]
        == "fired Scene Activation CC 'value notification' event for 'Scene ID': '001'"
    )
