"""Unit tests for the Todoist calendar platform."""
from unittest.mock import patch

from homeassistant import setup
from homeassistant.components.todoist.calendar import DOMAIN
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity


@patch("homeassistant.components.todoist.calendar.TodoistAPIAsync")
async def test_calendar_entity_unique_id(
    todoist_api, hass: HomeAssistant, api, entity_registry: er.EntityRegistry
) -> None:
    """Test unique id is set to project id."""
    todoist_api.return_value = api
    assert await setup.async_setup_component(
        hass,
        "calendar",
        {
            "calendar": {
                "platform": DOMAIN,
                CONF_TOKEN: "token",
            }
        },
    )
    await hass.async_block_till_done()

    entity = entity_registry.async_get("calendar.name")
    assert entity.unique_id == "12345"


@patch("homeassistant.components.todoist.calendar.TodoistAPIAsync")
async def test_update_entity_for_custom_project_with_labels_on(
    todoist_api, hass: HomeAssistant, api
) -> None:
    """Test that the calendar's state is on for a custom project using labels."""
    todoist_api.return_value = api
    assert await setup.async_setup_component(
        hass,
        "calendar",
        {
            "calendar": {
                "platform": DOMAIN,
                CONF_TOKEN: "token",
                "custom_projects": [{"name": "All projects", "labels": ["Label1"]}],
            }
        },
    )
    await hass.async_block_till_done()

    await async_update_entity(hass, "calendar.all_projects")
    state = hass.states.get("calendar.all_projects")
    assert state.attributes["labels"] == ["Label1"]
    assert state.state == "on"


@patch("homeassistant.components.todoist.calendar.TodoistAPIAsync")
async def test_calendar_custom_project_unique_id(
    todoist_api, hass: HomeAssistant, api, entity_registry: er.EntityRegistry
) -> None:
    """Test unique id is None for any custom projects."""
    todoist_api.return_value = api
    assert await setup.async_setup_component(
        hass,
        "calendar",
        {
            "calendar": {
                "platform": DOMAIN,
                CONF_TOKEN: "token",
                "custom_projects": [{"name": "All projects"}],
            }
        },
    )
    await hass.async_block_till_done()

    entity = entity_registry.async_get("calendar.all_projects")
    assert entity is None

    state = hass.states.get("calendar.all_projects")
    assert state.state == "off"
