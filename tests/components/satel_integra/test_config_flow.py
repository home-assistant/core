"""Test the satel integra config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.satel_integra.config_flow import (
    ACTION_ADD,
    ACTION_DELETE,
    ACTION_EDIT,
    CONF_ACTION,
    CONF_ACTION_NUMBER,
    CONF_ARM_HOME_MODE,
    CONF_DEVICE_PARTITIONS,
    CONF_OUTPUTS,
    CONF_SWITCHABLE_OUTPUTS,
    CONF_ZONE_TYPE,
    CONF_ZONES,
)
from homeassistant.components.satel_integra.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONST_HOST = "192.168.0.2"
CONST_PORT = 7094


async def test_setup_flow(
    hass: HomeAssistant, mock_satel: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the setup flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: CONST_HOST, CONF_PORT: CONST_PORT, CONF_CODE: "1111"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == CONST_HOST
    assert result["data"] == {CONF_HOST: CONST_HOST, CONF_PORT: CONST_PORT}
    assert result["options"] == {CONF_CODE: "1111"}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the import flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "192.168.0.2",
            CONF_PORT: 7095,
            CONF_CODE: "3333",
            CONF_DEVICE_PARTITIONS: {
                "1": {CONF_NAME: "Partition Import 1", CONF_ARM_HOME_MODE: 1}
            },
            CONF_ZONES: {
                "1": {CONF_NAME: "Zone Import 1", CONF_ZONE_TYPE: "motion"},
                "2": {CONF_NAME: "Zone Import 2", CONF_ZONE_TYPE: "door"},
            },
            CONF_OUTPUTS: {
                "1": {CONF_NAME: "Output Import 1", CONF_ZONE_TYPE: "light"},
                "2": {CONF_NAME: "Output Import 2", CONF_ZONE_TYPE: "safety"},
            },
            CONF_SWITCHABLE_OUTPUTS: {
                "1": {CONF_NAME: "Switchable output Import 1"},
                "2": {CONF_NAME: "Switchable output Import 2"},
            },
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.0.2"
    assert result["data"] == {CONF_HOST: "192.168.0.2", CONF_PORT: 7095}
    assert result["options"] == {
        CONF_CODE: "3333",
        CONF_DEVICE_PARTITIONS: {
            "1": {CONF_NAME: "Partition Import 1", CONF_ARM_HOME_MODE: 1}
        },
        CONF_ZONES: {
            "1": {CONF_NAME: "Zone Import 1", CONF_ZONE_TYPE: "motion"},
            "2": {CONF_NAME: "Zone Import 2", CONF_ZONE_TYPE: "door"},
        },
        CONF_OUTPUTS: {
            "1": {CONF_NAME: "Output Import 1", CONF_ZONE_TYPE: "light"},
            "2": {CONF_NAME: "Output Import 2", CONF_ZONE_TYPE: "safety"},
        },
        CONF_SWITCHABLE_OUTPUTS: {
            "1": {CONF_NAME: "Switchable output Import 1"},
            "2": {CONF_NAME: "Switchable output Import 2"},
        },
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_general_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test general options flow."""
    entry, result = await _init_options_flow(hass, "general")

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_CODE: "2222"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_CODE] == "2222"

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "general"}
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_CODE] is None


async def test_options_partitions_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test partitions options flow."""
    entry, result = await _init_options_flow(hass, "partitions")

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_ACTION_NUMBER: 1, CONF_ACTION: ACTION_ADD}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "partition_details"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_NAME: "Partition 1", CONF_ARM_HOME_MODE: 2}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_DEVICE_PARTITIONS] == {
        "1": {CONF_NAME: "Partition 1", CONF_ARM_HOME_MODE: 2}
    }

    # Check partition can only be added once
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "partitions"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 1, CONF_ACTION: ACTION_ADD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "partitions"
    assert result["errors"] == {"base": "partition_exists"}

    # Check only existing partitions can be edited
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 2, CONF_ACTION: ACTION_EDIT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "partitions"
    assert result["errors"] == {"base": "unknown_partition"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 1, CONF_ACTION: ACTION_EDIT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "partition_details"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "Partition 1 Update", CONF_ARM_HOME_MODE: 3},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_DEVICE_PARTITIONS] == {
        "1": {CONF_NAME: "Partition 1 Update", CONF_ARM_HOME_MODE: 3}
    }

    # Check only existing partitions can be deleted
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "partitions"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 2, CONF_ACTION: ACTION_DELETE},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "partitions"
    assert result["errors"] == {"base": "unknown_partition"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 1, CONF_ACTION: ACTION_DELETE},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_DEVICE_PARTITIONS] == {}


async def test_options_zones_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test zones options flow."""
    entry, result = await _init_options_flow(hass, "zones")

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_ACTION_NUMBER: 1, CONF_ACTION: ACTION_ADD}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zone_details"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_NAME: "Zone 1", CONF_ZONE_TYPE: "motion"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_ZONES] == {
        "1": {CONF_NAME: "Zone 1", CONF_ZONE_TYPE: "motion"}
    }

    # Check zones can only be added once
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "zones"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 1, CONF_ACTION: ACTION_ADD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zones"
    assert result["errors"] == {"base": "zone_exists"}

    # Check only existing zones can be edited
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 2, CONF_ACTION: ACTION_EDIT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zones"
    assert result["errors"] == {"base": "unknown_zone"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 1, CONF_ACTION: ACTION_EDIT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zone_details"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "Zone 1 Update", CONF_ZONE_TYPE: "motion"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_ZONES] == {
        "1": {CONF_NAME: "Zone 1 Update", CONF_ZONE_TYPE: "motion"}
    }

    # Check only existing zones can be deleted
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "zones"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 2, CONF_ACTION: ACTION_DELETE},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zones"
    assert result["errors"] == {"base": "unknown_zone"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 1, CONF_ACTION: ACTION_DELETE},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_ZONES] == {}


async def test_options_outputs_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test outputs options flow."""
    entry, result = await _init_options_flow(hass, "outputs")

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_ACTION_NUMBER: 1, CONF_ACTION: ACTION_ADD}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "output_details"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_NAME: "Output 1", CONF_ZONE_TYPE: "motion"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_OUTPUTS] == {
        "1": {CONF_NAME: "Output 1", CONF_ZONE_TYPE: "motion"}
    }

    # Check outputs can only be added once
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "outputs"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 1, CONF_ACTION: ACTION_ADD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "outputs"
    assert result["errors"] == {"base": "output_exists"}

    # Check only existing outputs can be edited
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 2, CONF_ACTION: ACTION_EDIT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "outputs"
    assert result["errors"] == {"base": "unknown_output"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 1, CONF_ACTION: ACTION_EDIT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "output_details"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "Output 1 Update", CONF_ZONE_TYPE: "motion"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_OUTPUTS] == {
        "1": {CONF_NAME: "Output 1 Update", CONF_ZONE_TYPE: "motion"}
    }

    # Check only existing outputs can be deleted
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "outputs"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 2, CONF_ACTION: ACTION_DELETE},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "outputs"
    assert result["errors"] == {"base": "unknown_output"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 1, CONF_ACTION: ACTION_DELETE},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_OUTPUTS] == {}


async def test_options_switchable_outputs_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test switchable outputs options flow."""
    entry, result = await _init_options_flow(hass, "switchable_outputs")

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_ACTION_NUMBER: 1, CONF_ACTION: ACTION_ADD}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "switchable_output_details"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_NAME: "Switchable output 1"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SWITCHABLE_OUTPUTS] == {
        "1": {CONF_NAME: "Switchable output 1"}
    }

    # Check switchable outputs can only be added once
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "switchable_outputs"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 1, CONF_ACTION: ACTION_ADD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "switchable_outputs"
    assert result["errors"] == {"base": "switchable_output_exists"}

    # Check only existing switchable outputs can be edited
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 2, CONF_ACTION: ACTION_EDIT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "switchable_outputs"
    assert result["errors"] == {"base": "unknown_switchable_output"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 1, CONF_ACTION: ACTION_EDIT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "switchable_output_details"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "Switchable output 1 Update"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SWITCHABLE_OUTPUTS] == {
        "1": {CONF_NAME: "Switchable output 1 Update"}
    }

    # Check only existing switchable outputs can be deleted
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "switchable_outputs"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 2, CONF_ACTION: ACTION_DELETE},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "switchable_outputs"
    assert result["errors"] == {"base": "unknown_switchable_output"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ACTION_NUMBER: 1, CONF_ACTION: ACTION_DELETE},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SWITCHABLE_OUTPUTS] == {}


async def _init_options_flow(hass: HomeAssistant, menu_step: str):
    """Initialize the options flow and navigate to a step."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": menu_step}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == menu_step

    return entry, result
