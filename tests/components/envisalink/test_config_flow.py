"""Tests for the Envisalink config flow."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.envisalink.const import (
    CONF_EVL_PORT,
    CONF_EVL_VERSION,
    CONF_PANEL_TYPE,
    CONF_PANIC,
    CONF_PARTITION_NUMBER,
    CONF_PARTITIONNAME,
    CONF_PASS,
    CONF_USERNAME,
    CONF_ZONE_NUMBER,
    CONF_ZONENAME,
    CONF_ZONETYPE,
    DOMAIN,
    SUBENTRY_TYPE_PARTITION,
    SUBENTRY_TYPE_ZONE,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_CODE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from .conftest import (
    ALARM_ENTITY,
    KEYPAD_ENTITY,
    MOCK_DATA,
    MOCK_OPTIONS,
    MOCK_YAML_CONFIG,
    ZONE_ENTITY,
    setup_envisalink,
)

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_HOST: MOCK_DATA[CONF_HOST],
    CONF_EVL_PORT: MOCK_DATA[CONF_EVL_PORT],
    CONF_PANEL_TYPE: MOCK_DATA[CONF_PANEL_TYPE],
    CONF_EVL_VERSION: MOCK_DATA[CONF_EVL_VERSION],
    CONF_USERNAME: MOCK_DATA[CONF_USERNAME],
    CONF_PASS: MOCK_DATA[CONF_PASS],
}

CODE_INPUT = {CONF_CODE: "1234", CONF_PANIC: "Police"}


def _suggested_values(result: dict[str, Any]) -> dict[str, Any]:
    """Pull the values suggested to the user out of a form result."""
    return {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.envisalink.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_success(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test a successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "code"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CODE_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DATA[CONF_HOST]
    assert result["data"] == USER_INPUT
    assert result["options"] == CODE_INPUT


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_controller: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the user flow shows an error and allows retry on connection timeout."""
    mock_controller.start.side_effect = lambda: mock_controller.callback_login_timeout(
        None
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # The previously entered values are retained so the user doesn't have to
    # retype them to retry.
    assert _suggested_values(result) == USER_INPUT

    mock_controller.start.side_effect = lambda: mock_controller.callback_login_success(
        None
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "code"


async def test_user_flow_invalid_auth(
    hass: HomeAssistant, mock_controller: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the user flow shows an error when the panel rejects credentials."""
    mock_controller.start.side_effect = lambda: mock_controller.callback_login_failure(
        None
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_login_timeout(
    hass: HomeAssistant, mock_controller: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the user flow shows cannot_connect when no login response arrives.

    Regression test: the outer asyncio.timeout in async_connect_panel raises
    LoginTimeout (distinct from the library's own tolerate-and-retry
    timeout), which must be mapped to the same "cannot_connect" error as any
    other connection failure, not fall through to "unknown".
    """
    mock_controller.start.side_effect = None  # never resolves the connection

    with (
        patch("homeassistant.components.envisalink.LOGIN_RESPONSE_TIMEOUT", 0),
        patch("homeassistant.components.envisalink.DEFAULT_TIMEOUT", 0),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_unknown_error(
    hass: HomeAssistant, mock_controller: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the user flow shows an error on an unexpected connection failure."""
    mock_controller.start.side_effect = RuntimeError("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort the user flow if already configured.

    single_config_entry aborts the flow at init, before any step runs, so
    there's no form to submit input into first.
    """
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow_success(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test importing YAML configuration creates an entry with subentries."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_YAML_CONFIG[DOMAIN]
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_YAML_CONFIG[DOMAIN][CONF_HOST]
    assert result["data"][CONF_HOST] == MOCK_YAML_CONFIG[DOMAIN][CONF_HOST]
    assert result["options"][CONF_CODE] == MOCK_YAML_CONFIG[DOMAIN][CONF_CODE]

    subentries = result["subentries"]
    assert len(subentries) == 2

    partition_subentry = next(
        s for s in subentries if s["subentry_type"] == SUBENTRY_TYPE_PARTITION
    )
    assert partition_subentry["unique_id"] == f"{SUBENTRY_TYPE_PARTITION}_1"
    assert partition_subentry["data"][CONF_PARTITIONNAME] == "Main Home"

    zone_subentry = next(
        s for s in subentries if s["subentry_type"] == SUBENTRY_TYPE_ZONE
    )
    assert zone_subentry["unique_id"] == f"{SUBENTRY_TYPE_ZONE}_1"
    assert zone_subentry["data"][CONF_ZONENAME] == "Front Door"
    assert zone_subentry["data"][CONF_ZONETYPE] == "door"


async def test_import_flow_cannot_connect(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test the import flow aborts when the connection times out."""
    mock_controller.start.side_effect = lambda: mock_controller.callback_login_timeout(
        None
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_YAML_CONFIG[DOMAIN]
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_flow_invalid_auth(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test the import flow aborts when the panel rejects credentials."""
    mock_controller.start.side_effect = lambda: mock_controller.callback_login_failure(
        None
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_YAML_CONFIG[DOMAIN]
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_auth"


async def test_import_flow_invalid_zone_number(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test the import flow aborts when a YAML zone number is out of range.

    Regression test: pyenvisalink only tracks zones 1..64 for the default
    EVL version 3. A YAML config with an out-of-range zone number used to
    pass straight through import and only fail later, with a raw KeyError,
    when the platform tried to look up alarm_state["zone"][zone_number].
    """
    config = {
        **MOCK_YAML_CONFIG[DOMAIN],
        "zones": {65: {"name": "Out of Range", "type": "door"}},
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_zone_number"
    assert result["description_placeholders"] == {"number": "65", "max": "64"}


async def test_import_flow_invalid_partition_number(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test the import flow aborts when a YAML partition number is out of range.

    Regression test: pyenvisalink only ever tracks partitions 1..8. A YAML
    config with an out-of-range partition number used to pass straight
    through import and only fail later, with a raw KeyError, when the
    platform tried to look up alarm_state["partition"][partition_number].
    """
    config = {
        **MOCK_YAML_CONFIG[DOMAIN],
        "partitions": {9: {"name": "Out of Range"}},
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_partition_number"
    assert result["description_placeholders"] == {"number": "9", "max": "8"}


async def test_import_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort the import flow if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_YAML_CONFIG[DOMAIN]
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the options flow updates the code and panic type."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CODE: "9999", CONF_PANIC: "Fire"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_CODE: "9999", CONF_PANIC: "Fire"}


async def test_zone_subentry_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test adding a zone through the subentry flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_ZONE),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_ZONE_NUMBER: 5, CONF_ZONENAME: "Back Door", CONF_ZONETYPE: "door"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Back Door (5)"
    assert result["data"][CONF_ZONE_NUMBER] == 5


async def test_zone_subentry_number_out_of_range(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a zone number beyond the panel's capacity is rejected.

    Regression test: pyenvisalink only tracks zones 1..64 for EVL version 3
    (mock_config_entry's configured version). An out-of-range number used to
    pass schema validation and only fail later, with a raw KeyError, when
    the platform tried to look up alarm_state["zone"][zone_number] - which
    also crashed the whole config entry setup, not just this subentry.
    """
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_ZONE),
        context={"source": SOURCE_USER},
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_ZONE_NUMBER: 65, CONF_ZONENAME: "Back Door", CONF_ZONETYPE: "door"},
        )


async def test_zone_subentry_creates_entity_without_restart(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test a zone added through the subentry flow gets an entity right away.

    Regression test: adding a subentry doesn't reload the config entry on its
    own; without an update listener scheduling that reload, the new entity
    wouldn't appear until Home Assistant restarts.
    """
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA, options=MOCK_OPTIONS)
    assert await setup_envisalink(hass, entry)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ZONE), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_ZONE_NUMBER: 9, CONF_ZONENAME: "Back Door", CONF_ZONETYPE: "door"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.back_door") is not None


async def test_zone_subentry_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test adding a zone number that is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_ZONE),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_ZONE_NUMBER: 1, CONF_ZONENAME: "Duplicate", CONF_ZONETYPE: "door"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ZONE_NUMBER: "already_configured"}


async def test_zone_subentry_reconfigure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring an existing zone."""
    mock_config_entry.add_to_hass(hass)
    zone_subentry_id = next(
        subentry_id
        for subentry_id, subentry in mock_config_entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_ZONE
    )

    result = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, zone_subentry_id
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_ZONENAME: "Renamed Door", CONF_ZONETYPE: "window"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.subentries[zone_subentry_id].data[CONF_ZONENAME] == (
        "Renamed Door"
    )


async def test_zone_subentry_removal_removes_entity(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test removing a zone subentry reloads the entry and tears it down.

    Regression test: removal is promised alongside add/edit for subentries,
    but nothing previously verified that the reload path this relies on
    (see test_zone_subentry_creates_entity_without_restart) also runs on
    removal, dropping the removed zone's entity.
    """
    assert await setup_envisalink(hass)
    assert hass.states.get(ZONE_ENTITY) is not None

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    zone_subentry_id = next(
        subentry_id
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_ZONE
    )

    assert hass.config_entries.async_remove_subentry(entry, zone_subentry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ZONE_ENTITY) is None


async def test_partition_subentry_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test adding a partition through the subentry flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PARTITION),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_PARTITION_NUMBER: 2, CONF_PARTITIONNAME: "Garage"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garage (2)"
    assert result["data"][CONF_PARTITION_NUMBER] == 2


async def test_partition_subentry_number_out_of_range(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a partition number beyond the panel's capacity is rejected.

    Regression test: pyenvisalink only ever tracks partitions 1..8. An
    out-of-range number used to pass schema validation and only fail later,
    with a raw KeyError, when the platform tried to look up
    alarm_state["partition"][partition_number] - which also crashed the
    whole config entry setup, not just this subentry.
    """
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PARTITION),
        context={"source": SOURCE_USER},
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_PARTITION_NUMBER: 9, CONF_PARTITIONNAME: "Garage"},
        )


async def test_partition_subentry_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test adding a partition number that is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_PARTITION),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_PARTITION_NUMBER: 1, CONF_PARTITIONNAME: "Duplicate"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_PARTITION_NUMBER: "already_configured"}


async def test_partition_subentry_reconfigure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring an existing partition."""
    mock_config_entry.add_to_hass(hass)
    partition_subentry_id = next(
        subentry_id
        for subentry_id, subentry in mock_config_entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_PARTITION
    )

    result = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, partition_subentry_id
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_PARTITIONNAME: "Renamed Partition"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert (
        mock_config_entry.subentries[partition_subentry_id].data[CONF_PARTITIONNAME]
        == "Renamed Partition"
    )


async def test_partition_subentry_removal_removes_entities(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test removing a partition subentry reloads the entry and tears it down.

    Regression test: removal is promised alongside add/edit for subentries,
    but nothing previously verified that the reload path this relies on
    also runs on removal, dropping the removed partition's entities (alarm
    panel and keypad sensor).
    """
    assert await setup_envisalink(hass)
    assert hass.states.get(ALARM_ENTITY) is not None
    assert hass.states.get(KEYPAD_ENTITY) is not None

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    partition_subentry_id = next(
        subentry_id
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_PARTITION
    )

    assert hass.config_entries.async_remove_subentry(entry, partition_subentry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ALARM_ENTITY) is None
    assert hass.states.get(KEYPAD_ENTITY) is None
