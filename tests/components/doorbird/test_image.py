"""Test DoorBird image entities."""

from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import mock_webhook_call
from .conftest import DoorbirdMockerType

from tests.typing import ClientSessionGenerator

# A body whose first 4 bytes are a recognized JPEG magic number, so
# infer_image_type accepts it. The trailing bytes are arbitrary padding.
VALID_JPEG = b"\xff\xd8\xff\xe0junk"


async def test_image_entities_registered(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    entity_registry: er.EntityRegistry,
) -> None:
    """Both last_motion and last_ring image entities are registered."""
    await doorbird_mocker()
    last_motion = hass.states.get("image.mydoorbird_last_motion")
    last_ring = hass.states.get("image.mydoorbird_last_ring")
    assert last_motion is not None
    assert last_ring is not None
    # No event has fired yet, so image_last_updated is None → state is unknown.
    assert last_motion.state == STATE_UNKNOWN
    assert last_ring.state == STATE_UNKNOWN
    assert (
        entity_registry.async_get("image.mydoorbird_last_motion").unique_id
        == "1234ABCD_last_motion"
    )
    assert (
        entity_registry.async_get("image.mydoorbird_last_ring").unique_id
        == "1234ABCD_last_ring"
    )


async def test_image_updates_on_event(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Receiving a doorbird event bumps image_last_updated on the matching image."""
    doorbird_entry = await doorbird_mocker()
    client = await hass_client()

    assert hass.states.get("image.mydoorbird_last_ring").state == STATE_UNKNOWN
    assert hass.states.get("image.mydoorbird_last_motion").state == STATE_UNKNOWN

    await mock_webhook_call(doorbird_entry.entry, client, "mydoorbird_doorbell")
    await hass.async_block_till_done()

    # Ring event only updates the ring image.
    ring_state = hass.states.get("image.mydoorbird_last_ring").state
    motion_state = hass.states.get("image.mydoorbird_last_motion").state
    assert ring_state != STATE_UNKNOWN
    assert motion_state == STATE_UNKNOWN

    await mock_webhook_call(doorbird_entry.entry, client, "mydoorbird_motion")
    await hass.async_block_till_done()

    assert hass.states.get("image.mydoorbird_last_motion").state != STATE_UNKNOWN


async def test_image_entity_fetches_bytes(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """The image proxy returns bytes fetched from the device."""
    doorbird_entry = await doorbird_mocker()
    doorbird_entry.api.get_image.return_value = VALID_JPEG
    client = await hass_client()

    state = hass.states.get("image.mydoorbird_last_ring")
    access_token = state.attributes["access_token"]
    resp = await client.get(
        f"/api/{IMAGE_DOMAIN}_proxy/image.mydoorbird_last_ring?token={access_token}"
    )
    assert resp.status == 200
    assert await resp.read() == VALID_JPEG
    assert doorbird_entry.api.get_image.called


async def test_image_rejects_non_image_body(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """A body that is not a recognized image is rejected instead of cached."""
    doorbird_entry = await doorbird_mocker()
    doorbird_entry.api.get_image.return_value = b"<html>error</html>"
    client = await hass_client()

    state = hass.states.get("image.mydoorbird_last_ring")
    access_token = state.attributes["access_token"]
    resp = await client.get(
        f"/api/{IMAGE_DOMAIN}_proxy/image.mydoorbird_last_ring?token={access_token}"
    )
    assert resp.status == 500
