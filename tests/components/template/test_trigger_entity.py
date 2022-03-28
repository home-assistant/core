"""Test template entity."""

from datetime import date, datetime, timedelta
from unittest.mock import patch

from homeassistant.components.template import TriggerUpdateCoordinator, trigger_entity
from homeassistant.components.template.const import (
    CONF_ATTRIBUTES,
    CONF_AVAILABILITY,
    CONF_PICTURE,
)
from homeassistant.const import CONF_ICON, CONF_NAME
from homeassistant.core import State

from tests.common import mock_restore_cache, mock_restore_cache_with_extra_data


async def test_trigger_entity_save_state(hass):
    """Test saving for a template trigger entity."""
    entity = trigger_entity.TriggerRestoreEntity(
        hass, TriggerUpdateCoordinator(hass, {}), {}
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
    entity._rendered["_datetime"] = datetime(
        year=2022, month=3, day=22, hour=12, minute=00, second=00
    )
    entity._rendered["_timedelta"] = timedelta(days=1, seconds=5, milliseconds=0)

    setattr(entity, "_additional_saved_data", "additional saved data")

    restored_extra_data = entity.extra_restore_state_data.as_dict()

    assert len(restored_extra_data) == 9

    # Confirm standard TemplateEntity templates
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
    assert restored_extra_data["_datetime"] == {
        "__type": "<class 'datetime.datetime'>",
        "isoformat": "2022-03-22T12:00:00",
    }
    assert restored_extra_data["_timedelta"] == {
        "__type": "<class 'datetime.timedelta'>",
        "repr": {"days": 1, "seconds": 5, "microseconds": 0},
    }

    assert restored_extra_data["_additional_saved_data"] == "additional saved data"


async def test_trigger_entity_save_state_missing_attribute(hass):
    """Test saving for a template trigger entity."""
    entity = trigger_entity.TriggerRestoreEntity(
        hass, TriggerUpdateCoordinator(hass, {}), {}
    )
    entity.restore = True
    entity.hass = hass

    # Setup standard TriggerEntity templates
    entity._to_render_simple.append(CONF_NAME)
    entity._rendered[CONF_NAME] = "friendly name"
    entity.add_additional_data("_additional_saved_data")

    restored_extra_data = entity.extra_restore_state_data.as_dict()

    assert len(restored_extra_data) == 1
    assert restored_extra_data[CONF_NAME] == "friendly name"


async def test_trigger_entity_save_state_no_restore(hass):
    """Test saving for a template trigger entity that should not be restored."""
    entity = trigger_entity.TriggerRestoreEntity(
        hass, TriggerUpdateCoordinator(hass, {}), {}
    )
    entity.restore = False
    entity.hass = hass

    entity._to_render_simple.append(CONF_NAME)
    entity._to_render_complex.append("_date")
    entity._config[CONF_ATTRIBUTES] = {"attr": "dummy"}
    entity.add_additional_data("_additional_saved_data")
    setattr(entity, "_additional_saved_data", "additional saved data")

    entity._save_state = False
    restored_extra_data = entity.extra_restore_state_data.as_dict()
    assert len(restored_extra_data) == 0


async def test_trigger_entity_save_state_disabled(hass):
    """Test saving for a template trigger entity when saving is disabled."""
    entity = trigger_entity.TriggerRestoreEntity(
        hass, TriggerUpdateCoordinator(hass, {}), {}
    )
    entity.restore = True
    entity.hass = hass

    entity._to_render_simple.append(CONF_NAME)
    entity._to_render_complex.append("_date")
    entity._config[CONF_ATTRIBUTES] = {"attr": "dummy"}
    entity.add_additional_data("_additional_saved_data")
    setattr(entity, "_additional_saved_data", "additional saved data")

    entity._save_state = False
    restored_extra_data = entity.extra_restore_state_data.as_dict()
    assert len(restored_extra_data) == 0


async def test_trigger_entity_restore_state(hass):
    """Test restoring for a template trigger entity."""
    entity = trigger_entity.TriggerRestoreEntity(
        hass, TriggerUpdateCoordinator(hass, {}), {}
    )
    entity.hass = hass
    entity.restore = True
    entity.entity_id = "sensor.restore"

    _setup_rendered_templates(entity)

    fake_state = State("sensor.restore", "not used", {"attr": "not used"})
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                fake_state,
                {
                    CONF_AVAILABILITY: "available",
                    CONF_ICON: "icon",
                    CONF_PICTURE: "entity picture",
                    CONF_NAME: "friendly name",
                    "_date": {
                        "__type": "<class 'datetime.date'>",
                        "isoformat": "2022-03-22",
                    },
                    "_datetime": {
                        "__type": "<class 'datetime.datetime'>",
                        "isoformat": "2022-03-22T12:00:00",
                    },
                    "_timedelta": {
                        "__type": "<class 'datetime.timedelta'>",
                        "repr": {"days": 1, "seconds": 5, "microseconds": 0},
                    },
                    CONF_ATTRIBUTES: {"attr": "attribute"},
                    "_additional_saved_data": "additional saved data",
                },
            ),
        ),
    )

    await entity.restore_entity()

    assert len(entity._rendered) == 8
    assert entity._rendered[CONF_AVAILABILITY] == "available"
    assert entity._rendered[CONF_ICON] == "icon"
    assert entity._rendered[CONF_PICTURE] == "entity picture"
    assert entity._rendered[CONF_NAME] == "friendly name"

    assert entity._rendered[CONF_ATTRIBUTES]
    assert len(entity._rendered[CONF_ATTRIBUTES]) == 1
    assert entity._rendered[CONF_ATTRIBUTES]["attr"]
    assert entity._rendered[CONF_ATTRIBUTES]["attr"] == "attribute"

    assert entity._rendered["_date"] == date(year=2022, month=3, day=22)
    assert entity._rendered["_datetime"] == datetime(
        year=2022, month=3, day=22, hour=12, minute=00, second=00
    )
    assert entity._rendered["_timedelta"] == timedelta(
        days=1, seconds=5, milliseconds=0
    )
    assert getattr(entity, "_additional_saved_data", None) == "additional saved data"


async def test_trigger_entity_restore_no_restore(hass):
    """Test restoring for a template trigger entity that should not be restored."""
    entity = trigger_entity.TriggerRestoreEntity(
        hass, TriggerUpdateCoordinator(hass, {}), {}
    )
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
    """Test restoring for a template trigger entity that has no saved state."""
    entity = trigger_entity.TriggerRestoreEntity(
        hass, TriggerUpdateCoordinator(hass, {}), {}
    )
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
    """Test restoring for a template trigger entity that has no extra data."""
    entity = trigger_entity.TriggerRestoreEntity(
        hass, TriggerUpdateCoordinator(hass, {}), {}
    )
    entity.hass = hass
    entity.restore = True
    entity.entity_id = "sensor.restore"

    _setup_rendered_templates(entity)

    fake_state = State("sensor.restore", "not used", {"attr": "not used"})
    mock_restore_cache(hass, [fake_state])

    last_sensor_state, last_sensor_data = await entity.restore_entity()
    assert last_sensor_state is not None
    assert last_sensor_data is None

    assert len(entity._rendered) == 0
    assert hasattr(entity, "_additional_saved_data") is False


async def test_trigger_entity_restore_missing_attributes(hass):
    """Test restoring for a template trigger entity with missing attributes."""
    entity = trigger_entity.TriggerRestoreEntity(
        hass, TriggerUpdateCoordinator(hass, {}), {}
    )
    entity.hass = hass
    entity.restore = True
    entity.entity_id = "sensor.restore"

    entity._to_render_simple.append(CONF_NAME)
    entity._to_render_simple.append("_date")
    entity._config[CONF_ATTRIBUTES] = {
        "attr1": "attribute1",
        "attr2": "attribute2",
    }
    entity.add_additional_data("_additional_saved_data")

    fake_state = State("sensor.restore", "not used", {"attr": "not used"})
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                fake_state,
                {
                    CONF_NAME: "friendly name",
                    CONF_ATTRIBUTES: {"attr1": "attribute1"},
                },
            ),
        ),
    )

    last_sensor_state, last_sensor_data = await entity.restore_entity()
    assert last_sensor_state is not None
    assert last_sensor_data is not None

    assert len(entity._rendered) == 2
    assert entity._rendered[CONF_NAME] == "friendly name"

    assert entity._rendered[CONF_ATTRIBUTES]

    assert len(entity._rendered[CONF_ATTRIBUTES]) == 1
    assert entity._rendered[CONF_ATTRIBUTES]["attr1"]
    assert entity._rendered[CONF_ATTRIBUTES]["attr1"] == "attribute1"

    assert hasattr(entity, "_additional_saved_data") is False


async def test_template_entity_restore_exceptions(hass):
    """Test restoring for a template entity where writing state results in TypeError or ValueError exception."""
    entity = trigger_entity.TriggerRestoreEntity(
        hass, TriggerUpdateCoordinator(hass, {}), {}
    )
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

    entity._save_state = True
    with patch(
        "homeassistant.helpers.entity.Entity.async_write_ha_state",
        side_effect=TypeError,
    ):
        last_sensor_state, last_sensor_data = await entity.restore_entity()
        assert last_sensor_state is not None
        assert last_sensor_data is not None
        assert entity._save_state is False

    entity._save_state = True
    with patch(
        "homeassistant.helpers.entity.Entity.async_write_ha_state",
        side_effect=ValueError,
    ):
        last_sensor_state, last_sensor_data = await entity.restore_entity()
        assert last_sensor_state is not None
        assert last_sensor_data is not None
        assert entity._save_state is False


def _setup_rendered_templates(entity):
    """Trigger Entity templates setup."""

    entity._to_render_simple.append(CONF_AVAILABILITY)
    entity._to_render_simple.append(CONF_ICON)
    entity._to_render_simple.append(CONF_PICTURE)
    entity._to_render_simple.append(CONF_NAME)
    entity._to_render_simple.append("_date")
    entity._to_render_complex.append("_datetime")
    entity._to_render_complex.append("_timedelta")

    entity._config[CONF_ATTRIBUTES] = {"attr": "dummy"}
    entity.add_additional_data("_additional_saved_data")
