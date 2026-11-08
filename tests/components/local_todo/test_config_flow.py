"""Test the local_todo config flow."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.local_todo.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import STORAGE_KEY, TODO_NAME

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result.get("errors")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "todo_list_name": TODO_NAME,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TODO_NAME
    assert result2["data"] == {
        "todo_list_name": TODO_NAME,
        "storage_key": STORAGE_KEY,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_todo_list_name(
    hass: HomeAssistant, setup_integration: None, config_entry: MockConfigEntry
) -> None:
    """Test two todo-lists cannot be added with the same name."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result.get("errors")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            # Pick a name that has the same slugify value as an existing config entry
            "todo_list_name": "my tasks",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_options_flow_categories(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the categories are set from the options flow."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "categories"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"categories": ["Fresh, produce"]},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"categories": "invalid_category"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "categories": [
                " Fresh produce ",
                "Grocery",
                "",
                "Fresh produce",
                "Household",
            ]
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        "categories": ["Fresh produce", "Grocery", "Household"]
    }


@pytest.mark.parametrize("categories", [["Fresh produce", "Grocery"]])
async def test_options_flow_menu(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the options flow offers a menu when categories exist."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["categories", "rename_category"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "categories"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "categories"


@pytest.mark.parametrize("categories", [["Fresh produce", "Grocery"]])
@pytest.mark.parametrize(
    ("new_name", "error"),
    [
        pytest.param(" ", "invalid_category", id="empty"),
        pytest.param("Fruits, vegetables", "invalid_category", id="comma"),
        pytest.param("Grocery", "category_exists", id="exists"),
    ],
)
async def test_options_flow_rename_category_errors(
    hass: HomeAssistant, config_entry: MockConfigEntry, new_name: str, error: str
) -> None:
    """Test renaming a category validates the new name."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "rename_category"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "rename_category"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"category": "Fresh produce", "new_name": new_name}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"new_name": error}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"category": "Fresh produce", "new_name": "Produce"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {"categories": ["Produce", "Grocery"]}
