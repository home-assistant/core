"""Test template entity."""

from datetime import date, datetime, timedelta

from homeassistant.components.template import TriggerUpdateCoordinator, trigger_entity
from homeassistant.components.template.const import (
    CONF_ATTRIBUTES,
    CONF_AVAILABILITY,
    CONF_PICTURE,
)
from homeassistant.const import CONF_ICON, CONF_NAME
from homeassistant.core import State

from tests.common import mock_restore_cache_with_extra_data


async def test_trigger_entity_save_state(hass):
    """Test saving for a trigger entity."""
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


async def test_template_entity_restore_state(hass):
    """Test restoring for a template entity."""
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

    assert entity._rendered[CONF_AVAILABILITY] == "available"
    assert entity._rendered[CONF_ICON] == "icon"
    assert entity._rendered[CONF_PICTURE] == "entity picture"
    assert entity._rendered[CONF_NAME] == "friendly name"
    assert entity._rendered[CONF_ATTRIBUTES]
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
