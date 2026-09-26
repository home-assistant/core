"""Test DoorBird image entities."""

import pytest

from homeassistant.components.doorbird.const import (
    CONF_EVENTS,
    DEFAULT_DOORBELL_EVENT,
    DEFAULT_MOTION_EVENT,
)
from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import mock_not_found_exception, mock_webhook_call
from .conftest import DoorbirdMockerType, patch_doorbird_api_entry_points

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


async def test_image_unregisters_event_entity_id_on_unload(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Unloading the entry clears the event entity_id the image registered."""
    doorbird_entry = await doorbird_mocker()
    event_entity_ids = doorbird_entry.entry.runtime_data.event_entity_ids
    assert event_entity_ids["mydoorbird_doorbell"] == "image.mydoorbird_last_ring"
    assert event_entity_ids["mydoorbird_motion"] == "image.mydoorbird_last_motion"

    await hass.config_entries.async_unload(doorbird_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert "mydoorbird_doorbell" not in event_entity_ids
    assert "mydoorbird_motion" not in event_entity_ids


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


async def test_image_updates_on_event_without_schedule_api(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Models without the schedule API still refresh on their configured events."""
    doorbird_entry = await doorbird_mocker(
        schedule_side_effect=mock_not_found_exception()
    )
    client = await hass_client()

    assert hass.states.get("image.mydoorbird_last_ring").state == STATE_UNKNOWN

    await mock_webhook_call(doorbird_entry.entry, client, "mydoorbird_doorbell")
    await hass.async_block_till_done()

    assert hass.states.get("image.mydoorbird_last_ring").state != STATE_UNKNOWN
    assert hass.states.get("image.mydoorbird_last_motion").state == STATE_UNKNOWN


async def test_image_event_mapping_follows_configured_events(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test the event to entity_id mapping tracks the configured events."""
    doorbird_entry = await doorbird_mocker()
    entry = doorbird_entry.entry

    assert (
        entry.runtime_data.event_entity_ids["mydoorbird_doorbell"]
        == "image.mydoorbird_last_ring"
    )

    with patch_doorbird_api_entry_points(doorbird_entry.api):
        hass.config_entries.async_update_entry(entry, options={CONF_EVENTS: ["motion"]})
        await hass.async_block_till_done()

        # The ring image no longer answers to a doorbell event, so the stale
        # mapping would otherwise keep naming it in the event data.
        assert "mydoorbird_doorbell" not in entry.runtime_data.event_entity_ids

        hass.config_entries.async_update_entry(
            entry, options={CONF_EVENTS: ["motion", "doorbell"]}
        )
        await hass.async_block_till_done()

    assert (
        entry.runtime_data.event_entity_ids["mydoorbird_doorbell"]
        == "image.mydoorbird_last_ring"
    )

    client = await hass_client()
    await mock_webhook_call(entry, client, "mydoorbird_doorbell")
    await hass.async_block_till_done()

    assert hass.states.get("image.mydoorbird_last_ring").state != STATE_UNKNOWN


@pytest.mark.parametrize(
    ("configured", "expected_ring", "expected_motion"),
    [
        pytest.param(
            ["doorbell", "motion"],
            ["mydoorbird_doorbell"],
            ["mydoorbird_motion"],
            id="both_defaults",
        ),
        pytest.param(["motion"], [], ["mydoorbird_motion"], id="motion_only"),
        pytest.param(["doorbell"], ["mydoorbird_doorbell"], [], id="doorbell_only"),
        pytest.param(
            ["front_door"],
            [],
            [],
            id="renamed_awaiting_a_schedule_assignment",
        ),
        pytest.param(
            ["doorbell", "front_door"],
            ["mydoorbird_doorbell"],
            [],
            id="renamed_alongside_a_default",
        ),
        pytest.param([], [], [], id="no_events"),
    ],
)
async def test_image_event_names(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    configured: list[str],
    expected_ring: list[str],
    expected_motion: list[str],
) -> None:
    """Test which registered events refresh each image.

    A renamed event has to be assigned to an input in the DoorBird app before
    the device calls it, which the schedule reports, so until then it refreshes
    nothing here.
    """
    doorbird_entry = await doorbird_mocker(options={CONF_EVENTS: configured})
    image_event_names = doorbird_entry.entry.runtime_data.door_station.image_event_names

    assert image_event_names.get(DEFAULT_DOORBELL_EVENT, []) == expected_ring
    assert image_event_names.get(DEFAULT_MOTION_EVENT, []) == expected_motion


async def test_image_cleans_up_the_events_it_registered(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removal drops the mappings the image actually registered."""
    doorbird_entry = await doorbird_mocker()
    door_station = doorbird_entry.entry.runtime_data.door_station
    event_entity_ids = doorbird_entry.entry.runtime_data.event_entity_ids

    assert event_entity_ids["mydoorbird_doorbell"] == "image.mydoorbird_last_ring"

    # A resolve while the entities are live, here attributing each event to the
    # other image. Removal has to drop what it registered, not what this says.
    door_station.image_event_names = {
        DEFAULT_DOORBELL_EVENT: ["mydoorbird_motion"],
        DEFAULT_MOTION_EVENT: ["mydoorbird_doorbell"],
    }
    entity_registry.async_update_entity(
        "image.mydoorbird_last_ring", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    assert "mydoorbird_doorbell" not in event_entity_ids
