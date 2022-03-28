"""Test template entity."""
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.template import template_entity
from homeassistant.core import State
from homeassistant.helpers import template

from tests.common import mock_restore_cache, mock_restore_cache_with_extra_data


async def test_template_entity_requires_hass_set(hass):
    """Test template entity requires hass to be set before accepting templates."""
    entity = template_entity.TemplateEntity(hass)

    with pytest.raises(AssertionError):
        entity.add_template_attribute("_hello", template.Template("Hello"))

    entity.hass = object()
    entity.add_template_attribute("_hello", template.Template("Hello", None))

    tpl_with_hass = template.Template("Hello", entity.hass)
    entity.add_template_attribute("_hello", tpl_with_hass)

    # Because hass is set in `add_template_attribute`, both templates match `tpl_with_hass`
    assert len(entity._template_attrs.get(tpl_with_hass, [])) == 2


async def test_template_entity_save_state(hass):
    """Test saving for a template entity."""
    entity = template_entity.TemplateRestoreEntity(hass)
    entity.restore = True
    entity.hass = hass

    # Setup standard TemplateEntity templates
    _setup_attribute_templates(entity)
    setattr(entity, "_attr_available", "availability")
    setattr(entity, "_attr_icon", "icon")
    setattr(entity, "_attr_entity_picture", "entity picture")
    setattr(entity, "_attr_name", "friendly name")
    entity._attr_extra_state_attributes = {"attr": "attribute"}

    # Add additional class items to be stored for date, datetime, and timedelta
    setattr(entity, "_date", date(year=2022, month=3, day=22))
    setattr(
        entity,
        "_datetime",
        datetime(year=2022, month=3, day=22, hour=12, minute=00, second=00),
    )
    setattr(entity, "_timedelta", timedelta(days=1, seconds=5, milliseconds=0))

    # Add additional template attribute to be stored.
    entity.add_template_attribute("_hello", template.Template("{{ 'Hello' }}"))
    setattr(entity, "_hello", "Hello")

    # Add additional static attribute that is not to be stored.
    entity.add_template_attribute("_hellostatic", template.Template("Hello"))
    setattr(entity, "_hellostatic", "Hello")

    restored_extra_data = entity.extra_restore_state_data.as_dict()

    assert len(restored_extra_data) == 8
    # Confirm standard TemplateEntity templates
    assert restored_extra_data["_attr_available"] == "availability"
    assert restored_extra_data["_attr_icon"] == "icon"
    assert restored_extra_data["_attr_entity_picture"] == "entity picture"
    assert restored_extra_data["_attr_name"] == "friendly name"

    # Confirm additional template attribute
    assert restored_extra_data["_hello"] == "Hello"

    # Confirm additional static template attribute is not saved
    with pytest.raises(KeyError):
        assert restored_extra_data["_hellostatic"]

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


async def test_template_entity_save_state_no_restore(hass):
    """Test saving for a template entity that should not be restored."""
    entity = template_entity.TemplateRestoreEntity(hass)
    entity.restore = True
    entity.hass = hass

    # Setup standard TemplateEntity templates

    entity._attribute_templates = {"attr": template.Template("{{ 'attribute }}")}
    entity._add_all_template_attributes()
    entity.add_additional_data("_date")

    _setup_attribute_templates(entity)
    entity._attr_extra_state_attributes = {"attr": "attribute"}

    # Add additional class items to be stored for date, datetime, and timedelta
    setattr(entity, "_date", date(year=2022, month=3, day=22))

    entity.restore = False
    restored_extra_data = entity.extra_restore_state_data.as_dict()
    assert len(restored_extra_data) == 0


async def test_template_entity_save_state_disabled(hass):
    """Test saving for a template entity when saving is disabled."""
    entity = template_entity.TemplateRestoreEntity(hass)
    entity.restore = True
    entity.hass = hass

    # Setup standard TemplateEntity templates

    entity._attribute_templates = {"attr": template.Template("{{ 'attribute }}")}
    entity._add_all_template_attributes()
    entity.add_additional_data("_date")

    _setup_attribute_templates(entity)
    entity._attr_extra_state_attributes = {"attr": "attribute"}

    # Add additional class items to be stored for date, datetime, and timedelta
    setattr(entity, "_date", date(year=2022, month=3, day=22))

    entity._save_state = False
    restored_extra_data = entity.extra_restore_state_data.as_dict()
    assert len(restored_extra_data) == 0


async def test_template_entity_restore_state(hass):
    """Test restoring for a template entity."""
    entity = template_entity.TemplateRestoreEntity(hass)
    entity.hass = hass
    entity.restore = True
    entity.entity_id = "sensor.restore"

    _setup_attribute_templates(entity)

    entity.add_additional_data("_attr_state")
    entity._attr_extra_state_attributes = {"attr": None}

    setattr(entity, "_date", None)

    setattr(entity, "_datetime", None)

    setattr(entity, "_timedelta", None)

    fake_state = State("sensor.restore", "not used", {"attr": "attribute"})
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                fake_state,
                {
                    "_attr_state": "restored",
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
                },
            ),
        ),
    )

    await entity.restore_entity()

    assert entity.state == "restored"

    attributes = entity.extra_state_attributes
    assert attributes

    assert attributes["attr"]
    assert attributes["attr"] == "attribute"

    assert getattr(entity, "_date") == date(year=2022, month=3, day=22)
    assert getattr(entity, "_datetime") == datetime(
        year=2022, month=3, day=22, hour=12, minute=00, second=00
    )
    assert getattr(entity, "_timedelta") == timedelta(days=1, seconds=5, milliseconds=0)


async def test_template_entity_restore_state_no_restore(hass):
    """Test restoring for a template entity that should not be restored."""
    entity = template_entity.TemplateRestoreEntity(hass)
    entity.hass = hass
    entity.restore = False
    entity.entity_id = "sensor.restore"

    entity._icon_template = template.Template("{{ 'icon' }}")
    entity._attribute_templates = {"attr": template.Template("{{ 'attribute }}")}

    entity._add_all_template_attributes()

    entity.add_additional_data("_attr_state")
    entity._attr_extra_state_attributes = {"attr": None}
    entity.add_additional_data("_date")
    setattr(entity, "_date", None)

    fake_state = State("sensor.restore", "not used", {"attr": "attribute"})
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                fake_state,
                {
                    "_attr_state": "restored",
                    "_date": "date",
                },
            ),
        ),
    )

    await entity.restore_entity()

    last_sensor_state, last_sensor_data = await entity.restore_entity()

    assert last_sensor_state is None
    assert last_sensor_data is None


async def test_template_entity_restore_no_state(hass):
    """Test restore template entity that has no saved state."""
    entity = template_entity.TemplateRestoreEntity(hass)
    entity.hass = hass
    entity.restore = True
    entity.entity_id = "sensor.restore"

    entity._icon_template = template.Template("{{ 'icon' }}")
    entity._attribute_templates = {"attr": template.Template("{{ 'attribute }}")}

    entity._add_all_template_attributes()

    entity.add_additional_data("_attr_state")
    entity._attr_extra_state_attributes = {"attr": None}
    entity.add_additional_data("_date")
    setattr(entity, "_date", None)

    last_sensor_state, last_sensor_data = await entity.restore_entity()

    assert last_sensor_state is None
    assert last_sensor_data is None

    assert entity.state == "unknown"
    assert entity.icon is None

    attributes = entity.extra_state_attributes
    assert attributes

    assert attributes["attr"] is None
    assert getattr(entity, "_date") is None


async def test_template_entity_restore_no_extra_data(hass):
    """Test restoring for a template entity where there is no extra data."""
    entity = template_entity.TemplateRestoreEntity(hass)
    entity.hass = hass
    entity.restore = True
    entity.entity_id = "sensor.restore"

    entity._icon_template = template.Template("{{ 'icon' }}")
    entity._attribute_templates = {"attr": template.Template("{{ 'attribute }}")}

    entity._add_all_template_attributes()

    entity.add_additional_data("_attr_state")
    entity._attr_extra_state_attributes = {"attr": None}
    entity.add_additional_data("_date")
    setattr(entity, "_date", None)

    fake_state = State("sensor.restore", "not used", {"attr": "attribute"})
    mock_restore_cache(hass, [fake_state])

    last_sensor_state, last_sensor_data = await entity.restore_entity()
    assert last_sensor_state is not None
    assert last_sensor_data is None

    assert entity.state == "unknown"

    attributes = entity.extra_state_attributes
    assert attributes

    assert attributes["attr"]
    assert attributes["attr"] == "attribute"
    assert getattr(entity, "_date") is None


async def test_template_entity_restore_missing_attributes(hass):
    """Test restoring for a template entity with missing attributes.."""
    entity = template_entity.TemplateRestoreEntity(hass)
    entity.hass = hass
    entity.restore = True
    entity.entity_id = "sensor.restore"

    entity._attribute_templates = {
        "attr1": template.Template("{{ 'attribute1 }}"),
        "attr2": template.Template("{{ 'attribute2 }}"),
    }
    entity.add_additional_data("_attr_state")
    entity.add_additional_data("_date")
    entity.add_additional_data("undefined_attribute")
    setattr(entity, "_date", None)

    entity._add_all_template_attributes()
    fake_state = State("sensor.restore", "not used", {"attr1": "attribute1"})
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                fake_state,
                {
                    "_attr_state": "restored",
                    "undefined_attribute": "defined",
                },
            ),
        ),
    )

    last_sensor_state, last_sensor_data = await entity.restore_entity()
    assert last_sensor_state is not None
    assert last_sensor_data is not None

    assert entity.state == "restored"

    attributes = entity.extra_state_attributes
    assert attributes

    assert attributes["attr1"]
    assert attributes["attr1"] == "attribute1"
    with pytest.raises(KeyError):
        assert attributes["attr2"]

    assert getattr(entity, "_date") is None
    assert getattr(entity, "undefined_attribute", None) == "defined"


async def test_template_entity_restore_exceptions(hass):
    """Test restoring for a template entity where writing state results in TypeError or ValueError exception."""
    entity = template_entity.TemplateRestoreEntity(hass)
    entity.hass = hass
    entity.restore = True
    entity.entity_id = "sensor.restore"

    entity._icon_template = template.Template("{{ 'icon' }}")
    entity._attribute_templates = {"attr": template.Template("{{ 'attribute }}")}

    entity._add_all_template_attributes()

    fake_state = State("sensor.restore", "not used", {"attr": "attribute"})
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                fake_state,
                {
                    "_attr_state": "restored",
                    "_date": "date",
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


def _setup_attribute_templates(entity):
    """Template Entity templates setup."""

    entity._availability_template = template.Template("{{ 'availability' }}")
    entity._icon_template = template.Template("{{ 'icon' }}")
    entity._entity_picture_template = template.Template("{{ 'picture' }}")
    entity._friendly_name_template = template.Template("{{ 'friendly name' }}")

    entity._attribute_templates = {"attr": template.Template("{{ 'attribute }}")}

    entity._add_all_template_attributes()

    entity.add_additional_data("_date")
    entity.add_additional_data("_datetime")
    entity.add_additional_data("_timedelta")
