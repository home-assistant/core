"""The tests for the notify.persistent_notification service."""
from homeassistant.components import notify
import homeassistant.components.persistent_notification as pn
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_async_send_message(hass: HomeAssistant) -> None:
    """Test sending a message to notify.persistent_notification service."""
    await async_setup_component(hass, pn.DOMAIN, {"core": {}})
    await async_setup_component(hass, notify.DOMAIN, {})
    await hass.async_block_till_done()

    message = {"message": "Hello", "title": "Test notification"}
    await hass.services.async_call(
        notify.DOMAIN, notify.SERVICE_PERSISTENT_NOTIFICATION, message
    )
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids(pn.DOMAIN)
    assert len(entity_ids) == 1

    state = hass.states.get(entity_ids[0])
    assert state.attributes.get("message") == "Hello"
    assert state.attributes.get("title") == "Test notification"
