"""The tests for Mobile App device actions."""
import pytest

from homeassistant.components import automation, device_automation
from homeassistant.components.mobile_app import DATA_DEVICES, DOMAIN, util
from homeassistant.setup import async_setup_component

from tests.common import assert_lists_same, async_get_device_automations, patch


async def test_get_actions(
    hass, push_registration, android_registration, ios_registration
):
    """Test we get the expected actions from a mobile_app."""

    # Generic
    webhook_id = push_registration["webhook_id"]
    device_id = hass.data[DOMAIN][DATA_DEVICES][webhook_id].id

    assert_lists_same(
        await async_get_device_automations(
            hass, device_automation.DeviceAutomationType.ACTION, device_id
        ),
        [{"domain": DOMAIN, "device_id": device_id, "metadata": {}, "type": "notify"}],
    )

    capabilitites = await device_automation._async_get_device_automation_capabilities(
        hass,
        device_automation.DeviceAutomationType.ACTION,
        {"domain": DOMAIN, "device_id": device_id, "type": "notify"},
    )
    assert "extra_fields" in capabilitites

    # Android
    webhook_id = android_registration["webhook_id"]
    device_id = hass.data[DOMAIN][DATA_DEVICES][webhook_id].id

    expected_actions = [
        {
            "domain": DOMAIN,
            "type": action,
            "device_id": device_id,
            "metadata": {},
        }
        for action in (
            "notify",
            "command_stop_tts",
            "command_update_sensors",
            "request_location_update",
            "command_auto_screen_brightness",
            "command_bluetooth",
            "command_ble_transmitter",
            "command_beacon_monitor",
            "command_activity",
            "clear_notification",
            "command_app_lock",
            "command_broadcast_intent",
            "command_dnd",
            "command_high_accuracy_mode",
            "command_launch_app",
            "command_media",
            "command_ringer_mode",
            "command_screen_brightness_level",
            "command_screen_off_timeout",
            "command_screen_on",
            "command_persistent_connection",
            "command_volume_level",
            "command_webview",
            "remove_channel",
        )
    ]

    assert_lists_same(
        await async_get_device_automations(
            hass, device_automation.DeviceAutomationType.ACTION, device_id
        ),
        expected_actions,
    )

    # iOS
    webhook_id = ios_registration["webhook_id"]
    device_id = hass.data[DOMAIN][DATA_DEVICES][webhook_id].id

    expected_actions = [
        {
            "domain": DOMAIN,
            "type": action,
            "device_id": device_id,
            "metadata": {},
        }
        for action in (
            "notify",
            "request_location_update",
            "clear_notification",
            "clear_badge",
            "update_complications",
        )
    ]

    assert_lists_same(
        await async_get_device_automations(
            hass, device_automation.DeviceAutomationType.ACTION, device_id
        ),
        expected_actions,
    )


@pytest.mark.parametrize(
    "action,extra_data",
    (
        ("command_stop_tts", {}),
        ("command_update_sensors", {}),
        ("request_location_update", {}),
        ("command_auto_screen_brightness", {"command": "turn_on"}),
        ("command_bluetooth", {"command": "turn_off"}),
        ("command_ble_transmitter", {"command": "turn_on"}),
        ("command_beacon_monitor", {"command": "turn_off"}),
        ("command_activity", {"intent_action": "abcd", "intent_uri": "abcd://efg"}),
        ("clear_notification", {"tag": "abcd"}),
        ("command_app_lock", {"app_lock_enabled": True}),
        (
            "command_broadcast_intent",
            {"intent_action": "abcd", "intent_package_name": "a.b.c.d"},
        ),
        ("command_dnd", {"command": "alarms_only"}),
        ("command_high_accuracy_mode", {"command": "force_on"}),
        ("command_launch_app", {"package_name": "io.homeassistant.mobile_app_test"}),
        ("command_media", {"media_command": "play", "media_package_name": "a.b.c.d"}),
        ("command_ringer_mode", {"command": "silent"}),
        ("command_screen_brightness_level", {"command": 200}),
        ("command_screen_off_timeout", {"command": 50}),
        ("command_screen_on", {"command": "turn_off"}),
        ("command_persistent_connection", {"persistent": "always"}),
        ("command_volume_level", {"media_stream": "call_stream", "command": 100}),
        ("command_webview", {"command": "/lovelace/settings"}),
        ("command_persistent_connection", {"persistent": "always"}),
        ("remove_channel", {"channel": "abcd"}),
    ),
)
async def test_android_action(action, extra_data, hass, android_registration):
    """Test for android app actions."""
    webhook_id = android_registration["webhook_id"]
    print(action)
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_action",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": hass.data[DOMAIN]["devices"][webhook_id].id,
                        "type": action,
                        **extra_data,
                    },
                },
            ]
        },
    )

    service_name = util.get_notify_service(hass, webhook_id)

    # Make sure it was actually registered
    assert hass.services.has_service("notify", service_name)

    with patch(
        "homeassistant.components.mobile_app.notify.MobileAppNotificationService.async_send_message"
    ) as mock_send_message:
        hass.bus.async_fire("test_action")
        await hass.async_block_till_done()
        assert len(mock_send_message.mock_calls) == 1

        assert mock_send_message.mock_calls[0][2] == {
            "target": [webhook_id],
            "message": action,
            "data": extra_data,
        }


@pytest.mark.parametrize(
    "action,extra_data",
    (
        ("request_location_update", {}),
        ("clear_notification", {"tag": "abcd"}),
        ("clear_badge", {}),
        ("update_complications", {}),
    ),
)
async def test_ios_action(action, extra_data, hass, ios_registration):
    """Test for android app actions."""
    webhook_id = ios_registration["webhook_id"]
    print(action)
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_action",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": hass.data[DOMAIN]["devices"][webhook_id].id,
                        "type": action,
                        **extra_data,
                    },
                },
            ]
        },
    )

    service_name = util.get_notify_service(hass, webhook_id)

    # Make sure it was actually registered
    assert hass.services.has_service("notify", service_name)

    with patch(
        "homeassistant.components.mobile_app.notify.MobileAppNotificationService.async_send_message"
    ) as mock_send_message:
        hass.bus.async_fire("test_action")
        await hass.async_block_till_done()
        assert len(mock_send_message.mock_calls) == 1

        assert mock_send_message.mock_calls[0][2] == {
            "target": [webhook_id],
            "message": action,
            "data": extra_data,
        }


async def test_action(hass, push_registration):
    """Test for turn_on and turn_off actions."""
    webhook_id = push_registration["webhook_id"]

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_notify",
                    },
                    "action": [
                        {"variables": {"name": "Paulus"}},
                        {
                            "domain": DOMAIN,
                            "device_id": hass.data[DOMAIN]["devices"][webhook_id].id,
                            "type": "notify",
                            "message": "Hello {{ name }}",
                        },
                    ],
                },
            ]
        },
    )

    service_name = util.get_notify_service(hass, webhook_id)

    # Make sure it was actually registered
    assert hass.services.has_service("notify", service_name)

    with patch(
        "homeassistant.components.mobile_app.notify.MobileAppNotificationService.async_send_message"
    ) as mock_send_message:
        hass.bus.async_fire("test_notify")
        await hass.async_block_till_done()
        assert len(mock_send_message.mock_calls) == 1

    assert mock_send_message.mock_calls[0][2] == {
        "target": [webhook_id],
        "message": "Hello Paulus",
        "data": {},
    }
