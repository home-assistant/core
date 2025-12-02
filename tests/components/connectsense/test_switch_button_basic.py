from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

DOMAIN = "connectsense"

async def test_button_press(hass, setup_entry, domain):
    reg = er.async_get(hass)
    btn = None
    for ent in reg.entities.values():
        if ent.platform == domain and ent.domain == "button" and ent.unique_id.endswith("_reboot"):
            btn = ent.entity_id
            break
    assert btn, "Reboot button not found"

    await hass.services.async_call("button", "press", {"entity_id": btn}, blocking=True)


async def test_service_send_test_notification_registered(hass, setup_entry):
    services = hass.services.async_services().get(DOMAIN, {})
    assert "send_test_notification" in services
