"""Tests for Instucture sensor platform."""


from unittest.mock import MagicMock

from homeassistant.components.instructure.const import (
    ANNOUNCEMENTS_KEY,
    ASSIGNMENTS_KEY,
    CONVERSATIONS_KEY,
    DOMAIN,
    GRADES_KEY,
    QUICK_LINKS_KEY,
)
from homeassistant.components.instructure.sensor import (
    SENSOR_DESCRIPTIONS,
    datetime_process,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get,
)

from . import (
    MOCK_ANNOUNCEMENTS,
    MOCK_ASSIGNMENTS,
    MOCK_CONVERSATIONS,
    MOCK_GRADES,
    MOCK_QUICK_LINKS,
)

from tests.common import MockConfigEntry


async def test_all_sensors_registered(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test that all sensors are registered."""
    entity_registry = hass.config_entries.flow.hass.data["entity_registry"]
    sensor_names = [
        "sensor.test_assignment",
        "sensor.test_announcement",
        "sensor.test_conversation",
        "sensor.test_grade",
        "calendar.canvas_calendar_assignments",
    ]
    for sensor_name in sensor_names:
        entity = entity_registry.async_get(sensor_name)
        assert entity is not None, f"{sensor_name}"


async def test_remove_sensors(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test removing entities from the coordinator."""
    entity_registry = async_get(hass)

    sensor_entity_ids = [
        "sensor.test_assignment",
        "sensor.test_announcement",
        "sensor.test_conversation",
        "sensor.test_grade",
        "calendar.canvas_calendar_assignments",
    ]

    # Iterate over each sensor entity
    for entity_id in sensor_entity_ids:
        assert entity_registry.async_is_registered(entity_id)

        entity_registry.async_remove(entity_id)

        assert not entity_registry.async_is_registered(entity_id)

    all_entities = async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(all_entities) == 0


async def test_assignment_sensor(
    hass: HomeAssistant,
    mock_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test getting data from coordinator."""
    assignment_sensor_entity = hass.data[DOMAIN][mock_config_entry.entry_id][
        "entities"
    ]["assignments"]["assignment-1"]
    unique_id = assignment_sensor_entity.unique_id
    coordinator = hass.data["instructure"][mock_config_entry.entry_id]["coordinator"]
    entity_description = SENSOR_DESCRIPTIONS[ASSIGNMENTS_KEY]

    value_fn = entity_description.value_fn(
        coordinator.data[entity_description.key][unique_id]
    )
    due_date = MOCK_ASSIGNMENTS["assignment-1"]["due_at"]

    # EntityDescription Test
    assert value_fn == datetime_process(due_date)
    assert entity_description.device_name == "Upcoming Assignments"
    assert entity_description.key == ASSIGNMENTS_KEY
    avabl_fn = entity_description.avabl_fn(
        coordinator.data[entity_description.key][unique_id]
    )
    assert avabl_fn is True
    name_fn = entity_description.name_fn(
        coordinator.data[entity_description.key][unique_id]
    )
    assert name_fn == coordinator.data[entity_description.key][unique_id]["name"]
    attr_fn = entity_description.attr_fn(
        coordinator.data[entity_description.key][unique_id], {}
    )
    assert "Link" in attr_fn

    # CanvasSensorEntity Test
    assert (
        assignment_sensor_entity.name
        == assignment_sensor_entity._get_name()
        == "Test Assignment"
    )
    assert (
        assignment_sensor_entity.available
        == assignment_sensor_entity._get_available()
        is True
    )
    assert (
        assignment_sensor_entity.native_value
        == assignment_sensor_entity._get_native_value()
        == datetime_process(due_date)
    )
    assert (
        assignment_sensor_entity.extra_state_attributes
        == assignment_sensor_entity._get_extra_state_attributes()
        == {"Link": "https://canvas.example.com/assignments/1"}
    )
    assert assignment_sensor_entity._attr_unique_id == unique_id

    assert assignment_sensor_entity._attr_device_info == DeviceInfo(
        identifiers={(DOMAIN, "Upcoming Assignments")},
        name="Upcoming Assignments",
        manufacturer="Canvas",
        entry_type=DeviceEntryType.SERVICE,
    )

    assert (
        len(hass.data[DOMAIN][mock_config_entry.entry_id]["entities"][ASSIGNMENTS_KEY])
        == 1
    )
    assert (
        "sensor.test_assignment"
        not in hass.data[DOMAIN][mock_config_entry.entry_id]["entities"][
            ASSIGNMENTS_KEY
        ]
    )


async def test_announcements_sensor(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the Announcements sensor."""
    announcements_sensor_entity = hass.data[DOMAIN][mock_config_entry.entry_id][
        "entities"
    ]["announcements"]["announcement-1"]
    unique_id = announcements_sensor_entity.unique_id
    coordinator = hass.data["instructure"][mock_config_entry.entry_id]["coordinator"]
    entity_description = SENSOR_DESCRIPTIONS[ANNOUNCEMENTS_KEY]
    # Test the Entity Description
    value_fn_result = entity_description.value_fn(
        coordinator.data[entity_description.key][unique_id]
    )
    read_state = MOCK_ANNOUNCEMENTS["announcement-1"]["read_state"]
    assert value_fn_result == read_state
    assert entity_description.device_name == "Announcements"
    avabl_fn_result = entity_description.avabl_fn(
        coordinator.data[entity_description.key][unique_id]
    )
    assert avabl_fn_result is True
    name_fn_result = entity_description.name_fn(
        coordinator.data[entity_description.key][unique_id]
    )
    assert name_fn_result == "Test Announcement"
    attr_fn = entity_description.attr_fn(
        coordinator.data[entity_description.key][unique_id], {}
    )
    assert attr_fn["Link"] == "https://canvas.example.com/announcements/1"
    assert datetime_process("2023-12-01T09:00:00Z") == attr_fn["Post Time"]

    # Test the CanvasSensorEntity
    assert (
        announcements_sensor_entity.name
        == announcements_sensor_entity._get_name()
        == "Test Announcement"
    )
    assert (
        announcements_sensor_entity.available
        == announcements_sensor_entity._get_available()
        is True
    )
    assert (
        announcements_sensor_entity.native_value
        == announcements_sensor_entity._get_native_value()
        == "unread"
    )
    assert (
        announcements_sensor_entity.extra_state_attributes
        == announcements_sensor_entity._get_extra_state_attributes()
        == {
            "Link": "https://canvas.example.com/announcements/1",
            "Post Time": "01 Dec 09:00",
        }
    )


async def test_conversations_sensor(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the Conversations sensor."""
    conversations_sensor_entity = hass.data[DOMAIN][mock_config_entry.entry_id][
        "entities"
    ]["conversations"]["conversation-1"]
    unique_id = conversations_sensor_entity.unique_id
    coordinator = hass.data["instructure"][mock_config_entry.entry_id]["coordinator"]
    entity_description = SENSOR_DESCRIPTIONS[CONVERSATIONS_KEY]

    value_fn_result = entity_description.value_fn(
        coordinator.data[entity_description.key][unique_id]
    )
    workflow_state = MOCK_CONVERSATIONS["conversation-1"]["workflow_state"]
    assert value_fn_result == workflow_state

    assert entity_description.device_name == "Inbox"

    avabl_fn_result = entity_description.avabl_fn(
        coordinator.data[entity_description.key][unique_id]
    )
    assert avabl_fn_result is True

    name_fn_result = entity_description.name_fn(
        coordinator.data[entity_description.key][unique_id]
    )
    assert name_fn_result == "Test Conversation"

    attr_fn_result = entity_description.attr_fn(
        coordinator.data[entity_description.key][unique_id], {}
    )
    assert attr_fn_result["Course"] == "Test Course"
    assert attr_fn_result["Initial Sender"] == "Test Sender"
    assert attr_fn_result["Last Message"] == "This is a test message."
    assert (
        datetime_process("2023-12-05T15:30:00Z") == attr_fn_result["Last Message Time"]
    )

    # Test the CanvasSensorEntity
    assert (
        conversations_sensor_entity.name
        == conversations_sensor_entity._get_name()
        == "Test Conversation"
    )
    assert (
        conversations_sensor_entity.available
        == conversations_sensor_entity._get_available()
        is True
    )
    assert (
        conversations_sensor_entity.native_value
        == conversations_sensor_entity._get_native_value()
        == "unread"
    )
    assert (
        conversations_sensor_entity.extra_state_attributes
        == conversations_sensor_entity._get_extra_state_attributes()
        == {
            "Course": "Test Course",
            "Initial Sender": "Test Sender",
            "Last Message": "This is a test message.",
            "Last Message Time": "05 Dec 15:30",
        }
    )


async def test_grades_sensor(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the Grades sensor."""
    grades_sensor_entity = hass.data[DOMAIN][mock_config_entry.entry_id]["entities"][
        "grades"
    ]["grade-1"]
    unique_id = grades_sensor_entity.unique_id
    coordinator = hass.data["instructure"][mock_config_entry.entry_id]["coordinator"]
    entity_description = SENSOR_DESCRIPTIONS[GRADES_KEY]

    value_fn_result = entity_description.value_fn(
        coordinator.data[entity_description.key][unique_id]
    )
    grade = MOCK_GRADES["grade-1"]["grade"]
    assert value_fn_result == grade

    assert entity_description.device_name == "Grades"

    avabl_fn_result = entity_description.avabl_fn(
        coordinator.data[entity_description.key][unique_id]
    )
    assert avabl_fn_result is True

    name_fn_result = entity_description.name_fn(
        coordinator.data[entity_description.key][unique_id]
    )
    assert name_fn_result == "Test Grade"

    attr_fn_result = entity_description.attr_fn(
        coordinator.data[entity_description.key][unique_id], {}
    )
    assert attr_fn_result["Score"] == 95
    assert attr_fn_result["Submission Type"] == "online_text_entry"

    # Test the CanvasSensorEntity
    assert grades_sensor_entity.name == grades_sensor_entity._get_name() == "Test Grade"
    assert (
        grades_sensor_entity.available == grades_sensor_entity._get_available() is True
    )
    assert (
        grades_sensor_entity.native_value
        == grades_sensor_entity._get_native_value()
        == "A"
    )
    assert (
        grades_sensor_entity.extra_state_attributes
        == grades_sensor_entity._get_extra_state_attributes()
        == {"Score": 95, "Submission Type": "online_text_entry"}
    )


async def test_quick_links_sensor(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the Quick Links sensor."""

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
    coordinator.data[QUICK_LINKS_KEY] = MOCK_QUICK_LINKS
    new_data = {
        ASSIGNMENTS_KEY: {},
        ANNOUNCEMENTS_KEY: {},
        CONVERSATIONS_KEY: {},
        GRADES_KEY: {},
        QUICK_LINKS_KEY: MOCK_QUICK_LINKS,
    }

    coordinator.update_entities(new_data)
    quick_links_sensor_entity = hass.data[DOMAIN][mock_config_entry.entry_id][
        "entities"
    ]["quick_links"]["quick-links-1"]

    unique_id = quick_links_sensor_entity.unique_id

    entity_description = SENSOR_DESCRIPTIONS[QUICK_LINKS_KEY]

    value_fn_result = entity_description.value_fn(
        coordinator.data[entity_description.key][unique_id]
    )
    assert value_fn_result == ""

    assert entity_description.device_name == "Quick links"

    avabl_fn_result = entity_description.avabl_fn(
        coordinator.data[entity_description.key][unique_id]
    )
    assert avabl_fn_result is True

    name_fn_result = entity_description.name_fn(
        coordinator.data[entity_description.key][unique_id]
    )
    assert name_fn_result == "Test Quick Links"

    attr_fn_result = entity_description.attr_fn(
        coordinator.data[entity_description.key][unique_id], {}
    )
    assert attr_fn_result["URL"] == "https://canvas.example.com/quicklinks/1"

    # Test the CanvasSensorEntity
    assert (
        quick_links_sensor_entity.name
        == quick_links_sensor_entity._get_name()
        == "Test Quick Links"
    )
    assert (
        quick_links_sensor_entity.available
        == quick_links_sensor_entity._get_available()
        is True
    )
    assert (
        quick_links_sensor_entity.native_value
        == quick_links_sensor_entity._get_native_value()
        == ""
    )
    assert (
        quick_links_sensor_entity.extra_state_attributes
        == quick_links_sensor_entity._get_extra_state_attributes()
        == {"URL": "https://canvas.example.com/quicklinks/1"}
    )
