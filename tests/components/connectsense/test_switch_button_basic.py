from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

DOMAIN = "connectsense"


async def test_button_created(hass: HomeAssistant, setup_entry, domain):
    reg = er.async_get(hass)
    button_entities = [
        ent.entity_id
        for ent in reg.entities.values()
        if ent.platform == domain
        and ent.domain == "button"
        and ent.unique_id.endswith("_reboot")
    ]
    assert len(button_entities) == 1

    # Ensure no switch entities are registered in the trimmed phase-one integration
    assert not [
        ent
        for ent in reg.entities.values()
        if ent.platform == domain and ent.domain == "switch"
    ]


async def test_button_press(hass, setup_entry, domain):
    reg = er.async_get(hass)
    btn = next(
        ent.entity_id
        for ent in reg.entities.values()
        if ent.platform == domain
        and ent.domain == "button"
        and ent.unique_id.endswith("_reboot")
    )
    await hass.services.async_call("button", "press", {"entity_id": btn}, blocking=True)
