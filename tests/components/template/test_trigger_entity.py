"""Test template entity."""

from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from homeassistant.components.template import TriggerUpdateCoordinator, trigger_entity
from homeassistant.components.template.const import (
    CONF_ATTRIBUTES,
    CONF_AVAILABILITY,
    CONF_PICTURE,
)
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    CONF_ICON,
    CONF_NAME,
)
from homeassistant.core import State
from homeassistant.helpers.restore_state import RestoreStateData, StoredState
import homeassistant.util.dt as dt_util

from tests.common import mock_restore_cache, mock_restore_cache_with_extra_data


async def test_trigger_entity_save_state(hass):
    """Test saving for a trigger-based template entity."""
    entity = trigger_entity.TriggerEntity(
        hass, TriggerUpdateCoordinator(hass, {}), {}, ["_additional_saved_data"]
    )
    entity.restore = True
    entity.hass = hass

    # Setup standard TriggerEntity templates
    _setup_rendered_templates(entity)
    entity._rendered[CONF_AVAILABILITY] = "availability"
    entity._rendered[CONF_ICON] = "icon"
    entity._rendered[CONF_PICTURE] = "entity picture"
    entity._rendered[CONF_NAME] = "friendly name"
    entity._rendered[CONF_ATTRIBUTES] = {"attr": "attribute"}

    entity._rendered["_date"] = date(year=2022, month=3, day=22)
    entity._rendered["_time"] = time(hour=10, minute=5, second=30)
    entity._rendered["_datetime"] = datetime(
        year=2022, month=3, day=22, hour=12, minute=00, second=00
    )
    entity._rendered["_timedelta"] = timedelta(days=1, seconds=5, milliseconds=0)

    setattr(entity, "_additional_saved_data", "additional saved data")

    restored_extra_data = entity.extra_restore_state_data.as_dict()

    assert len(restored_extra_data) == 10

    # Confirm standard TriggerEntity templates
    assert restored_extra_data[CONF_AVAILABILITY] == "availability"
    assert restored_extra_data[CONF_ICON] == "icon"
    assert restored_extra_data[CONF_PICTURE] == "entity picture"
    assert restored_extra_data[CONF_NAME] == "friendly name"
    assert restored_extra_data[CONF_ATTRIBUTES] == {"attr": "attribute"}

    # Confirm additional class items for date, datetime, and timedelta
    assert restored_extra_data["_date"] == {
        "__type": "<class 'datetime.date'>",
        "isoformat": "2022-03-22",
    }
    assert restored_extra_data["_time"] == {
        "__type": "<class 'datetime.time'>",
        "isoformat": "10:05:30",
    }
    assert restored_extra_data["_datetime"] == {
        "__type": "<class 'datetime.datetime'>",
        "isoformat": "2022-03-22T12:00:00",
    }
    assert restored_extra_data["_timedelta"] == {
        "__type": "<class 'datetime.timedelta'>",
        "total_seconds": 86405.0,
    }

    assert restored_extra_data["_additional_saved_data"] == "additional saved data"


async def test_trigger_entity_no_extra_data_save(hass):
    """Test not saving extra data for a trigger-based template entity."""
    entity = trigger_entity.TriggerEntity(
        hass, TriggerUpdateCoordinator(hass, {}), {}, ["_additional_saved_data"]
    )
    entity.restore = True
    entity._save_extra_data = False
    entity.hass = hass

    # Add additional template attribute to be stored.
    setattr(entity, "_additional_saved_data", "additional saved data")

    restored_extra_data = entity.extra_restore_state_data.as_dict()
    assert len(restored_extra_data) == 0


async def test_trigger_entity_save_no_restore_and_no_savestate(hass):
    """Test if entity is removed for saving state if no restore and not always saving state."""
    entity = trigger_entity.TriggerEntity(hass, TriggerUpdateCoordinator(hass, {}), {})
    entity.hass = hass
    entity.entity_id = "sensor.restore"
    entity.restore = False

    data = await RestoreStateData.async_get_instance(hass)

    # No entities or last states should currently be saved
    assert not data.entities
    assert not data.last_states

    data.last_states.update(
        {
            "sensor.restore": StoredState(
                State("sensor.restore", "on"), None, dt_util.utcnow()
            ),
        }
    )

    await entity.async_internal_added_to_hass()

    # No entities or last states should exist.
    assert not data.entities
    assert not data.last_states


async def test_trigger_entity_save_no_restore_and_yes_savestate(hass):
    """Test if entity is removed for saving state if no restore but always saving state."""
    entity = trigger_entity.TriggerEntity(
        hass, TriggerUpdateCoordinator(hass, {}), {}, always_save_state=True
    )
    entity.hass = hass
    entity.entity_id = "sensor.restore"
    entity.restore = False

    data = await RestoreStateData.async_get_instance(hass)

    # No entities or last states should currently be saved
    assert not data.entities
    assert not data.last_states

    data.last_states.update(
        {
            "sensor.restore": StoredState(
                State("sensor.restore", "on"), None, dt_util.utcnow()
            ),
        }
    )

    await entity.async_internal_added_to_hass()

    # No entities or last states should exist.
    assert data.entities["sensor.restore"]
    assert data.last_states["sensor.restore"]


async def test_trigger_entity_save_yes_restore_and_no_savestate(hass):
    """Test if entity is removed for saving state if restore but not always saving state."""
    entity = trigger_entity.TriggerEntity(hass, TriggerUpdateCoordinator(hass, {}), {})
    entity.hass = hass
    entity.entity_id = "sensor.restore"
    entity.restore = True

    data = await RestoreStateData.async_get_instance(hass)

    # No entities or last states should currently be saved
    assert not data.entities
    assert not data.last_states

    data.last_states.update(
        {
            "sensor.restore": StoredState(
                State("sensor.restore", "on"), None, dt_util.utcnow()
            ),
        }
    )

    await entity.async_internal_added_to_hass()

    # No entities or last states should exist.
    assert data.entities["sensor.restore"]
    assert data.last_states["sensor.restore"]


async def test_trigger_entity_save_yes_restore_and_yes_savestate(hass):
    """Test if entity is removed for saving state if yes restore and always saving state."""
    entity = trigger_entity.TriggerEntity(
        hass, TriggerUpdateCoordinator(hass, {}), {}, always_save_state=True
    )
    entity.hass = hass
    entity.entity_id = "sensor.restore"
    entity.restore = True

    data = await RestoreStateData.async_get_instance(hass)

    # No entities or last states should currently be saved
    assert not data.entities
    assert not data.last_states

    data.last_states.update(
        {
            "sensor.restore": StoredState(
                State("sensor.restore", "on"), None, dt_util.utcnow()
            ),
        }
    )

    await entity.async_internal_added_to_hass()

    # No entities or last states should exist.
    assert data.entities["sensor.restore"]
    assert data.last_states["sensor.restore"]


async def test_trigger_entity_restore_state(hass):
    """Test restoring for a trigger-based template trigger entity."""
    entity = trigger_entity.TriggerEntity(
        hass, TriggerUpdateCoordinator(hass, {}), {}, ["_additional_saved_data"]
    )
    entity.hass = hass
    entity.restore = True
    entity.entity_id = "sensor.restore"

    _setup_rendered_templates(entity)

    fake_state = State(
        "sensor.restore",
        "not used",
        {
            ATTR_ICON: "icon",
            ATTR_ENTITY_PICTURE: "entity picture",
            ATTR_FRIENDLY_NAME: "friendly name",
            "attr": "attribute",
        },
    )
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                fake_state,
                {
                    CONF_AVAILABILITY: "available",
                    "_date": {
                        "__type": "<class 'datetime.date'>",
                        "isoformat": "2022-03-22",
                    },
                    "_time": {
                        "__type": "<class 'datetime.time'>",
                        "isoformat": "10:05:30",
                    },
                    "_datetime": {
                        "__type": "<class 'datetime.datetime'>",
                        "isoformat": "2022-03-22T12:00:00",
                    },
                    "_timedelta": {
                        "__type": "<class 'datetime.timedelta'>",
                        "total_seconds": 86405.0,
                    },
                    "_additional_saved_data": "additional saved data",
                },
            ),
        ),
    )

    _, extra_data = await entity.restore_entity()

    assert extra_data is not None
    assert entity._rendered[CONF_AVAILABILITY] == "available"
    assert entity._rendered[CONF_ICON] == "icon"
    assert CONF_ICON not in extra_data
    assert entity._rendered[CONF_PICTURE] == "entity picture"
    assert CONF_PICTURE not in extra_data
    assert entity._rendered[CONF_NAME] == "friendly name"
    assert CONF_NAME not in extra_data
    assert entity._rendered[CONF_ATTRIBUTES]
    assert len(entity._rendered[CONF_ATTRIBUTES]) == 1

    assert entity._rendered[CONF_ATTRIBUTES]["attr"] == "attribute"
    assert CONF_ATTRIBUTES not in extra_data

    assert entity._rendered["_date"] == date(year=2022, month=3, day=22)
    assert entity._rendered["_time"] == time(hour=10, minute=5, second=30)
    assert entity._rendered["_datetime"] == datetime(
        year=2022, month=3, day=22, hour=12, minute=00, second=00
    )
    assert entity._rendered["_timedelta"] == timedelta(
        days=1, seconds=5, milliseconds=0
    )
    assert getattr(entity, "_additional_saved_data", None) == "additional saved data"


async def test_trigger_entity_restore_no_restore(hass):
    """Test restoring for a trigger-based template trigger entity that should not be restored."""
    entity = trigger_entity.TriggerEntity(hass, TriggerUpdateCoordinator(hass, {}), {})
    entity.hass = hass
    entity.restore = False
    entity.entity_id = "sensor.restore"

    _setup_rendered_templates(entity)

    last_sensor_state, last_sensor_data = await entity.restore_entity()

    assert last_sensor_state is None
    assert last_sensor_data is None

    assert len(entity._rendered) == 0
    assert getattr(entity, "_additional_saved_data", None) is None


async def test_trigger_entity_restore_no_state(hass):
    """Test restoring for a trigger-based template trigger entity that has no saved state."""
    entity = trigger_entity.TriggerEntity(hass, TriggerUpdateCoordinator(hass, {}), {})
    entity.hass = hass
    entity.restore = True
    entity.entity_id = "sensor.restore"

    _setup_rendered_templates(entity)

    last_sensor_state, last_sensor_data = await entity.restore_entity()

    assert last_sensor_state is None
    assert last_sensor_data is None

    assert len(entity._rendered) == 0
    assert getattr(entity, "_additional_saved_data", None) is None


async def test_trigger_entity_restore_no_extra_data(hass):
    """Test restoring for a trigger-based template trigger entity that has no extra data."""
    entity = trigger_entity.TriggerEntity(
        hass, TriggerUpdateCoordinator(hass, {}), {}, ["_additional_saved_data"]
    )
    entity.hass = hass
    entity.restore = True
    entity.entity_id = "sensor.restore"

    _setup_rendered_templates(entity)

    fake_state = State("sensor.restore", "not used", {"attr": "attribute"})
    mock_restore_cache(hass, [fake_state])

    last_sensor_state, last_sensor_data = await entity.restore_entity()
    assert last_sensor_state is not None
    assert last_sensor_data is None

    assert len(entity._rendered) == 1
    assert entity._rendered[CONF_ATTRIBUTES]
    assert len(entity._rendered[CONF_ATTRIBUTES]) == 1
    assert entity._rendered[CONF_ATTRIBUTES]["attr"] == "attribute"
    assert hasattr(entity, "_additional_saved_data") is False


async def test_trigger_entity_restore_missing_attributes(hass):
    """Test restoring for a trigger-based template trigger entity with missing attributes."""
    entity = trigger_entity.TriggerEntity(
        hass,
        TriggerUpdateCoordinator(hass, {}),
        {},
        ["_additional_saved_data", "missing_data"],
    )
    entity.hass = hass
    entity.restore = True
    entity.entity_id = "sensor.restore"

    entity._to_render_simple.append(CONF_NAME)
    entity._to_render_simple.append("_date")
    entity._config[CONF_ATTRIBUTES] = {
        "attr1": "attribute",
        "attr2": "attribute",
    }

    fake_state = State(
        "sensor.restore", "not used", {"attr1": "attribute1", "attr3": "attribute3"}
    )
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                fake_state,
                {
                    "_additional_saved_data": "data",
                },
            ),
        ),
    )

    last_sensor_state, last_sensor_data = await entity.restore_entity()
    assert last_sensor_state is not None
    assert last_sensor_data is not None

    assert len(entity._rendered) == 1
    assert entity._rendered[CONF_ATTRIBUTES]
    assert len(entity._rendered[CONF_ATTRIBUTES]) == 1
    assert entity._rendered[CONF_ATTRIBUTES]["attr1"]
    assert entity._rendered[CONF_ATTRIBUTES]["attr1"] == "attribute1"

    assert getattr(entity, "_additional_saved_data") == "data"
    assert hasattr(entity, "missing_data") is False


async def test_trigger_entity_restore_exceptions(hass):
    """Test restoring for a trigger-based template entity where writing state results in TypeError or ValueError exception."""
    entity = trigger_entity.TriggerEntity(hass, TriggerUpdateCoordinator(hass, {}), {})
    entity.hass = hass
    entity.restore = True
    entity.entity_id = "sensor.restore"

    entity._to_render_simple.append(CONF_NAME)

    fake_state = State("sensor.restore", "not used", {"attr": "not used"})
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                fake_state,
                {
                    CONF_NAME: "friendly name",
                },
            ),
        ),
    )

    entity._save_extra_data = True
    with patch(
        "homeassistant.helpers.entity.Entity.async_write_ha_state",
        side_effect=TypeError,
    ):
        last_sensor_state, last_sensor_data = await entity.restore_entity()
        assert last_sensor_state is not None
        assert last_sensor_data is not None
        assert entity._save_extra_data is False

    entity._save_extra_data = True
    with patch(
        "homeassistant.helpers.entity.Entity.async_write_ha_state",
        side_effect=ValueError,
    ):
        last_sensor_state, last_sensor_data = await entity.restore_entity()
        assert last_sensor_state is not None
        assert last_sensor_data is not None
        assert entity._save_extra_data is False


def _setup_rendered_templates(entity):
    """Trigger-based Template Entity templates setup."""

    entity._to_render_simple.append(CONF_AVAILABILITY)
    entity._to_render_simple.append(CONF_ICON)
    entity._to_render_simple.append(CONF_PICTURE)
    entity._to_render_simple.append(CONF_NAME)
    entity._to_render_simple.append("_date")
    entity._to_render_complex.append("_datetime")
    entity._to_render_complex.append("_timedelta")

    entity._config = {
        CONF_AVAILABILITY: "",
        ATTR_ICON: "",
        CONF_PICTURE: "",
        CONF_NAME: "",
        CONF_ATTRIBUTES: {"attr": "dummy"},
    }

    entity._extra_save_rendered.extend(["_date", "_time", "_datetime", "_timedelta"])
