"""The tests for WebOS TV device triggers."""
import homeassistant.components.automation as automation
from homeassistant.components.webostv.const import DOMAIN
from homeassistant.setup import async_setup_component

from . import ENTITY_ID, setup_webostv

from tests.common import async_get_device_automations


async def test_get_triggers(hass, client):
    """Test we get the expected triggers."""
    await setup_webostv(hass, "fake-uuid")
    assert client

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get_device(identifiers={(DOMAIN, "fake-uuid")})

    turn_on_trigger = {
        "platform": "device",
        "domain": DOMAIN,
        "type": "turn_on",
        "device_id": device.id,
    }

    triggers = await async_get_device_automations(hass, "trigger", device.id)
    assert turn_on_trigger in triggers


async def test_if_fires_on_turn_on_request(hass, calls, client):
    """Test for turn_on and turn_off triggers firing."""
    await setup_webostv(hass, "fake-uuid")
    assert client

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get_device(identifiers={(DOMAIN, "fake-uuid")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": "turn_on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "{{ trigger.device_id }}",
                            "id": "{{ trigger.id }}",
                        },
                    },
                }
            ]
        },
    )

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == device.id
    assert calls[0].data["id"] == 0
