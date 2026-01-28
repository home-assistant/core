"""Test recorder recorded entities."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import recorder
from homeassistant.components.recorder.recorded_entities import (
    DATA_RECORDED_ENTITIES,
    EntityRecordingDisabler,
    RecordedEntities,
    RecordedEntity,
    RecorderPreferences,
    async_get_entity_options,
    async_set_entity_option,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import flush_store
from tests.typing import WebSocketGenerator


@pytest.fixture(name="entities")
def entities_fixture(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    request: pytest.FixtureRequest,
) -> dict[str, str]:
    """Set up the test environment."""
    if request.param == "entities_unique_id":
        return entities_unique_id(entity_registry)
    if request.param == "entities_no_unique_id":
        return entities_no_unique_id(hass)
    raise RuntimeError("Invalid setup fixture")


def entities_unique_id(entity_registry: er.EntityRegistry) -> dict[str, str]:
    """Create some entities in the entity registry."""
    entry_sensor = entity_registry.async_get_or_create("sensor", "test", "unique1")
    return {
        "sensor": entry_sensor.entity_id,
    }


def entities_no_unique_id(hass: HomeAssistant) -> dict[str, str]:
    """Create some entities not in the entity registry."""
    sensor = "sensor.test"
    return {
        "sensor": sensor,
    }


@pytest.mark.usefixtures("recorder_mock")
async def test_load_preferences(hass: HomeAssistant) -> None:
    """Make sure that we can load/save data correctly."""
    recorded_entities = hass.data[DATA_RECORDED_ENTITIES]
    assert recorded_entities.entities == {}
    assert recorded_entities.recorder_preferences == RecorderPreferences(
        entity_filter_imported=True
    )

    async_set_entity_option(hass, "light.kitchen", recording_disabled_by=None)
    async_set_entity_option(
        hass, "light.living_room", recording_disabled_by=EntityRecordingDisabler.USER
    )

    assert recorded_entities.entities == {
        "light.kitchen": RecordedEntity(None),
        "light.living_room": RecordedEntity(EntityRecordingDisabler.USER),
    }

    await flush_store(recorded_entities._store)

    recorded_entities2 = RecordedEntities(hass)
    await recorded_entities2.async_initialize()

    assert recorded_entities.entities == recorded_entities2.entities
    assert (
        recorded_entities.recorder_preferences
        == recorded_entities2.recorder_preferences
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_record_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test record entity."""
    ws_client = await hass_ws_client(hass)

    entry1 = entity_registry.async_get_or_create("test", "test", "unique1")
    entry2 = entity_registry.async_get_or_create("test", "test", "unique2")

    recorded_entities = hass.data[DATA_RECORDED_ENTITIES]
    assert len(recorded_entities.entities) == 0

    # Set options
    await ws_client.send_json_auto_id(
        {
            "type": "recorder/recorded_entities/set_options",
            "entity_ids": [entry1.entity_id],
            "recording_disabled_by": None,
        }
    )

    response = await ws_client.receive_json()
    assert response["success"]

    entry1 = entity_registry.async_get(entry1.entity_id)
    assert entry1.options == {"recorder": {"recording_disabled_by": None}}
    entry2 = entity_registry.async_get(entry2.entity_id)
    assert entry2.options == {}
    # Settings should be stored in the entity registry
    assert len(recorded_entities.entities) == 0

    # Update options
    await ws_client.send_json_auto_id(
        {
            "type": "recorder/recorded_entities/set_options",
            "entity_ids": [entry1.entity_id, entry2.entity_id],
            "recording_disabled_by": "user",
        }
    )

    response = await ws_client.receive_json()
    assert response["success"]

    entry1 = entity_registry.async_get(entry1.entity_id)
    assert entry1.options == {"recorder": {"recording_disabled_by": "user"}}
    entry2 = entity_registry.async_get(entry2.entity_id)
    assert entry2.options == {"recorder": {"recording_disabled_by": "user"}}
    # Settings should be stored in the entity registry
    assert len(recorded_entities.entities) == 0


@pytest.mark.usefixtures("recorder_mock")
async def test_record_entity_unknown(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test behavior when disabling recording of an unknown entity."""
    ws_client = await hass_ws_client(hass)

    recorded_entities = hass.data[DATA_RECORDED_ENTITIES]
    assert len(recorded_entities.entities) == 0

    # Set options
    await ws_client.send_json_auto_id(
        {
            "type": "recorder/recorded_entities/set_options",
            "entity_ids": ["test.test1"],
            "recording_disabled_by": None,
        }
    )

    response = await ws_client.receive_json()
    assert response["success"]

    assert len(recorded_entities.entities) == 1
    assert recorded_entities.entities == {
        "test.test1": RecordedEntity(recording_disabled_by=None)
    }

    # Update options
    await ws_client.send_json_auto_id(
        {
            "type": "recorder/recorded_entities/set_options",
            "entity_ids": ["test.test1", "test.test2"],
            "recording_disabled_by": "user",
        }
    )

    response = await ws_client.receive_json()
    assert response["success"]

    assert len(recorded_entities.entities) == 2
    assert recorded_entities.entities == {
        "test.test1": RecordedEntity(
            recording_disabled_by=EntityRecordingDisabler.USER
        ),
        "test.test2": RecordedEntity(
            recording_disabled_by=EntityRecordingDisabler.USER
        ),
    }


@pytest.mark.parametrize(
    "entities", ["entities_unique_id", "entities_no_unique_id"], indirect=True
)
@pytest.mark.usefixtures("recorder_mock")
async def test_update_recorder(
    hass: HomeAssistant,
    entities: dict[str, str],
) -> None:
    """Test recorder exclusion set is updated."""
    unrecorded_entities = recorder.get_instance(hass).unrecorded_entities
    assert unrecorded_entities == set()

    entity_id = entities["sensor"]

    # Settings changed - recorder exclusion set updated
    async_set_entity_option(hass, entity_id, recording_disabled_by=None)
    await hass.async_block_till_done()
    assert recorder.get_instance(hass).unrecorded_entities is not unrecorded_entities
    unrecorded_entities = recorder.get_instance(hass).unrecorded_entities
    assert unrecorded_entities == set()

    # Settings not changed - recorder exclusion set not updated
    async_set_entity_option(hass, entity_id, recording_disabled_by=None)
    await hass.async_block_till_done()
    assert recorder.get_instance(hass).unrecorded_entities is unrecorded_entities
    assert unrecorded_entities == set()

    # Settings changed - recorder exclusion set updated
    async_set_entity_option(
        hass, entity_id, recording_disabled_by=EntityRecordingDisabler.USER
    )
    await hass.async_block_till_done()
    assert recorder.get_instance(hass).unrecorded_entities is not unrecorded_entities
    unrecorded_entities = recorder.get_instance(hass).unrecorded_entities
    assert unrecorded_entities == {entity_id}


@pytest.mark.usefixtures("recorder_mock")
async def test_get_entity_options(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test get entity options."""
    with pytest.raises(HomeAssistantError, match="Unknown entity"):
        async_get_entity_options(hass, "light.not_in_registry")

    entry = entity_registry.async_get_or_create("climate", "test", "unique1")
    assert async_get_entity_options(hass, entry.entity_id) == snapshot

    async_set_entity_option(
        hass, entry.entity_id, recording_disabled_by=EntityRecordingDisabler.USER
    )
    async_set_entity_option(
        hass,
        "light.not_in_registry",
        recording_disabled_by=EntityRecordingDisabler.USER,
    )
    assert async_get_entity_options(hass, entry.entity_id) == snapshot
    assert async_get_entity_options(hass, "light.not_in_registry") == snapshot


@pytest.mark.parametrize(
    "hass_storage_data",
    [
        {
            "recorder.recorded_entities": {
                "data": {
                    "recorded_entities": {
                        "light.kitchen": {
                            "recording_disabled_by": "user",
                            "future_option": "unexpected_value",
                        },
                        "light.living_room": {
                            "recording_disabled_by": "my_dog",
                        },
                    },
                    "recorder_preferences": {
                        "entity_filter_imported": True,
                    },
                },
                "key": "recorder.recorded_entities",
                "minor_version": 1,
                "version": 1,
            },
        }
    ],
)
@pytest.mark.usefixtures("recorder_mock")
async def test_get_entity_options_data_from_the_future(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test get entity options from the future."""
    entry = entity_registry.async_get_or_create("climate", "test", "unique1")
    entity_registry.async_update_entity_options(
        entry.entity_id,
        recorder.DOMAIN,
        {"recording_disabled_by": "user", "unexpected_option": 42},
    )
    assert async_get_entity_options(hass, entry.entity_id) == snapshot

    entity_registry.async_update_entity_options(
        entry.entity_id,
        recorder.DOMAIN,
        {"recording_disabled_by": "my_dog"},
    )
    assert async_get_entity_options(hass, entry.entity_id) == snapshot

    assert async_get_entity_options(hass, "light.kitchen") == snapshot
    assert async_get_entity_options(hass, "light.living_room") == snapshot
