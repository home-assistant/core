"""Test the Birthday config flow."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.birthday.const import (
    CONF_DAY,
    CONF_MONTH,
    CONF_PERSON,
    CONF_YEAR,
    DOMAIN,
    SUBENTRY_TYPE_BIRTHDAY,
)
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.freeze_time("2025-01-10 12:00:00")

ALICE = {CONF_PERSON: "Alice", CONF_DAY: 15, CONF_MONTH: 6, CONF_YEAR: 1990}
BOB = {CONF_PERSON: "Bob", CONF_DAY: 10, CONF_MONTH: 3}


def _titles(entry: MockConfigEntry) -> list[str]:
    return sorted(subentry.title for subentry in entry.subentries.values())


async def test_user_flow_single_birthday(hass: HomeAssistant) -> None:
    """Test creating the entry with one birthday."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], ALICE)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Birthdays"
    assert result["data"] == {}
    entry = result["result"]
    assert _titles(entry) == ["Alice – 15/06/1990"]
    subentry = next(iter(entry.subentries.values()))
    assert subentry.subentry_type == SUBENTRY_TYPE_BIRTHDAY
    assert dict(subentry.data) == ALICE


async def test_user_flow_without_year(hass: HomeAssistant) -> None:
    """Test a birthday without year."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], BOB)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert _titles(entry) == ["Bob – 10/03"]
    assert dict(next(iter(entry.subentries.values())).data) == BOB


async def test_user_flow_add_another(hass: HomeAssistant) -> None:
    """Test adding several birthdays in the initial flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**ALICE, "add_another": True}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], BOB)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert _titles(result["result"]) == ["Alice – 15/06/1990", "Bob – 10/03"]


async def test_user_flow_duplicate_name(hass: HomeAssistant) -> None:
    """Test the same name cannot be added twice (case insensitive)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**ALICE, "add_another": True}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**ALICE, CONF_PERSON: "alice"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_PERSON: "name_exists"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], BOB)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert _titles(result["result"]) == ["Alice – 15/06/1990", "Bob – 10/03"]


ERROR_CASES = [
    pytest.param(
        {CONF_PERSON: "   ", CONF_DAY: 1, CONF_MONTH: 1},
        {CONF_PERSON: "name_empty"},
        id="empty_name",
    ),
    pytest.param(
        {CONF_PERSON: "A", CONF_DAY: 1, CONF_MONTH: 1, CONF_YEAR: 1899},
        {CONF_YEAR: "invalid_year"},
        id="year_too_old",
    ),
    pytest.param(
        {CONF_PERSON: "A", CONF_DAY: 1, CONF_MONTH: 1, CONF_YEAR: 2026},
        {CONF_YEAR: "invalid_year"},
        id="year_in_future",
    ),
    pytest.param(
        {CONF_PERSON: "A", CONF_DAY: 1, CONF_MONTH: 13},
        {CONF_MONTH: "invalid_month"},
        id="month_too_high",
    ),
    pytest.param(
        {CONF_PERSON: "A", CONF_DAY: 0, CONF_MONTH: 0},
        {CONF_MONTH: "invalid_month", CONF_DAY: "invalid_day"},
        id="day_and_month_zero",
    ),
    pytest.param(
        {CONF_PERSON: "A", CONF_DAY: 1, CONF_MONTH: 0},
        {CONF_MONTH: "invalid_month"},
        id="month_zero",
    ),
    pytest.param(
        {CONF_PERSON: "A", CONF_DAY: 31, CONF_MONTH: 4},
        {CONF_DAY: "invalid_day"},
        id="day_too_high",
    ),
    pytest.param(
        {CONF_PERSON: "A", CONF_DAY: 0, CONF_MONTH: 4},
        {CONF_DAY: "invalid_day"},
        id="day_zero",
    ),
    pytest.param(
        {CONF_PERSON: "A", CONF_DAY: 29, CONF_MONTH: 2, CONF_YEAR: 2001},
        {CONF_DAY: "not_leap_year"},
        id="feb_29_not_leap",
    ),
    pytest.param(
        {CONF_PERSON: "A", CONF_DAY: 30, CONF_MONTH: 2, CONF_YEAR: 2000},
        {CONF_DAY: "invalid_day"},
        id="feb_30_leap",
    ),
    pytest.param(
        {CONF_PERSON: " ", CONF_DAY: 32, CONF_MONTH: 1, CONF_YEAR: 1800},
        {
            CONF_PERSON: "name_empty",
            CONF_YEAR: "invalid_year",
            CONF_DAY: "invalid_day",
        },
        id="multiple_errors",
    ),
]


@pytest.mark.parametrize(("user_input", "errors"), ERROR_CASES)
async def test_user_flow_errors(
    hass: HomeAssistant, user_input: dict[str, Any], errors: dict[str, str]
) -> None:
    """Test validation errors in the config flow, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == errors

    result = await hass.config_entries.flow.async_configure(result["flow_id"], ALICE)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_error_placeholders(hass: HomeAssistant) -> None:
    """Test the description placeholders used by the error messages."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PERSON: "A", CONF_DAY: 31, CONF_MONTH: 4}
    )
    assert result["description_placeholders"] == {
        "min_year": "1900",
        "max_year": "2025",
        "max_day": "30",
        "year": "",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PERSON: "A", CONF_DAY: 29, CONF_MONTH: 2, CONF_YEAR: 2001},
    )
    assert result["description_placeholders"]["year"] == "2001"
    assert result["description_placeholders"]["max_day"] == "28"


async def test_user_flow_feb_29_without_year(hass: HomeAssistant) -> None:
    """Test 29 February is accepted when the year is unknown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PERSON: "Leap", CONF_DAY: 29, CONF_MONTH: 2}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert _titles(result["result"]) == ["Leap – 29/02"]


async def test_single_instance(
    hass: HomeAssistant, mock_empty_config_entry: MockConfigEntry
) -> None:
    """Test only one entry is allowed."""
    mock_empty_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_subentry_add(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test adding a single birthday."""
    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TYPE_BIRTHDAY),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_PERSON: "Carol", CONF_DAY: 5, CONF_MONTH: 12, CONF_YEAR: 1985},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Carol – 05/12/1985"
    assert "Carol – 05/12/1985" in _titles(init_integration)
    assert len(init_integration.subentries) == 5


async def test_subentry_add_another(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test adding several birthdays in a row."""
    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TYPE_BIRTHDAY),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_PERSON: "Carol", CONF_DAY: 5, CONF_MONTH: 12, "add_another": True},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    assert len(init_integration.subentries) == 5

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_PERSON: "Dave", CONF_DAY: 6, CONF_MONTH: 12}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(init_integration.subentries) == 6
    titles = _titles(init_integration)
    assert "Carol – 05/12" in titles
    assert "Dave – 06/12" in titles


async def test_subentry_add_errors(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test validation errors when adding a birthday."""
    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TYPE_BIRTHDAY),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_PERSON: "ALICE", CONF_DAY: 1, CONF_MONTH: 1}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_PERSON: "name_exists"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_PERSON: "Carol", CONF_DAY: 31, CONF_MONTH: 11}
    )
    assert result["errors"] == {CONF_DAY: "invalid_day"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_PERSON: "Carol", CONF_DAY: 30, CONF_MONTH: 11}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_subentry_reconfigure(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test editing a birthday."""
    subentry = next(
        s
        for s in init_integration.subentries.values()
        if s.data[CONF_PERSON] == "Alice"
    )

    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TYPE_BIRTHDAY),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry.subentry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert "add_another" not in result["data_schema"].schema

    # Keeping the same name is fine, the flow ignores the edited birthday
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_PERSON: "Alice", CONF_DAY: 16, CONF_MONTH: 6, CONF_YEAR: 1990},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    updated = init_integration.subentries[subentry.subentry_id]
    assert updated.title == "Alice – 16/06/1990"
    assert dict(updated.data) == {
        CONF_PERSON: "Alice",
        CONF_DAY: 16,
        CONF_MONTH: 6,
        CONF_YEAR: 1990,
    }


async def test_subentry_reconfigure_errors(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test validation errors when editing a birthday."""
    subentry = next(
        s
        for s in init_integration.subentries.values()
        if s.data[CONF_PERSON] == "Alice"
    )

    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TYPE_BIRTHDAY),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry.subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_PERSON: "bob", CONF_DAY: 15, CONF_MONTH: 6}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {CONF_PERSON: "name_exists"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_PERSON: "Alice", CONF_DAY: 15, CONF_MONTH: 6}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert init_integration.subentries[subentry.subentry_id].title == "Alice – 15/06"
