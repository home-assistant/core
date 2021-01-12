"""The tests for Mobile App device actions."""
from homeassistant.components import automation, device_automation
from homeassistant.components.mobile_app import DATA_DEVICES, DOMAIN, util
from homeassistant.setup import async_setup_component

from tests.common import async_get_device_automations, patch


async def test_get_actions(hass, push_registration):
    """Test we get the expected actions from a mobile_app."""
    webhook_id = push_registration["webhook_id"]
    device_id = hass.data[DOMAIN][DATA_DEVICES][webhook_id].id

    assert await async_get_device_automations(hass, "action", device_id) == [
        {"domain": DOMAIN, "device_id": device_id, "type": "notify"}
    ]

    capabilitites = await device_automation._async_get_device_automation_capabilities(
        hass, "action", {"domain": DOMAIN, "device_id": device_id, "type": "notify"}
    )
    assert "extra_fields" in capabilitites


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
        "data": None,
    }
