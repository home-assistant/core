from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers import entity_registry as er
from homeassistant.const import STATE_ON, STATE_OFF

DOMAIN = "connectsense"

async def test_entities_create_and_toggle(hass: HomeAssistant, setup_entry, domain, aioclient_mock):
    reg = er.async_get(hass)

    outlet_eid = None
    for ent in reg.entities.values():
        if ent.platform == domain and ent.domain == "switch" and ent.unique_id.endswith("_outlet"):
            outlet_eid = ent.entity_id
            break
    assert outlet_eid, "Outlet switch not found"

    await async_update_entity(hass, outlet_eid)
    assert hass.states.get(outlet_eid).state in (STATE_OFF, "off")

    await hass.services.async_call("switch", "turn_on", {"entity_id": outlet_eid}, blocking=True)
    assert hass.states.get(outlet_eid).state in (STATE_ON, "on")

    await hass.services.async_call("switch", "turn_off", {"entity_id": outlet_eid}, blocking=True)
    assert hass.states.get(outlet_eid).state in (STATE_OFF, "off")

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
