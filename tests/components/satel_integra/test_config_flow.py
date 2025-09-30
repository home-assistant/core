"""Test the satel integra config flow."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.satel_integra.const import (
    CONF_ARM_HOME_MODE,
    CONF_DEVICE_PARTITIONS,
    CONF_OUTPUT_NUMBER,
    CONF_OUTPUTS,
    CONF_PARTITION_NUMBER,
    CONF_SWITCHABLE_OUTPUT_NUMBER,
    CONF_SWITCHABLE_OUTPUTS,
    CONF_ZONE_NUMBER,
    CONF_ZONE_TYPE,
    CONF_ZONES,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigSubentry,
)
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    MOCK_CONFIG_DATA,
    MOCK_CONFIG_OPTIONS,
    MOCK_OUTPUT_SUBENTRY,
    MOCK_PARTITION_SUBENTRY,
    MOCK_SWITCHABLE_OUTPUT_SUBENTRY,
    MOCK_ZONE_SUBENTRY,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("user_input", "entry_data", "entry_options"),
    [
        (
            {**MOCK_CONFIG_DATA, **MOCK_CONFIG_OPTIONS},
            MOCK_CONFIG_DATA,
            MOCK_CONFIG_OPTIONS,
        ),
        (
            {CONF_HOST: MOCK_CONFIG_DATA[CONF_HOST]},
            {CONF_HOST: MOCK_CONFIG_DATA[CONF_HOST], CONF_PORT: DEFAULT_PORT},
            {CONF_CODE: None},
        ),
    ],
)
async def test_setup_flow(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_setup_entry: AsyncMock,
    user_input: dict[str, Any],
    entry_data: dict[str, Any],
    entry_options: dict[str, Any],
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
        user_input,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_CONFIG_DATA[CONF_HOST]
    assert result["data"] == entry_data
    assert result["options"] == entry_options

    assert len(mock_setup_entry.mock_calls) == 1


async def test_setup_connection_failed(
    hass: HomeAssistant, mock_satel: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the setup flow when connection fails."""
    user_input = MOCK_CONFIG_DATA

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_satel.return_value.connect.return_value = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_satel.return_value.connect.return_value = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("import_input", "entry_data", "entry_options"),
    [
        (
            {
                CONF_HOST: MOCK_CONFIG_DATA[CONF_HOST],
                CONF_PORT: MOCK_CONFIG_DATA[CONF_PORT],
                CONF_CODE: MOCK_CONFIG_OPTIONS[CONF_CODE],
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
            MOCK_CONFIG_DATA,
            MOCK_CONFIG_OPTIONS,
        )
    ],
)
async def test_import_flow(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_setup_entry: AsyncMock,
    import_input: dict[str, Any],
    entry_data: dict[str, Any],
    entry_options: dict[str, Any],
) -> None:
    """Test the import flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=import_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_CONFIG_DATA[CONF_HOST]
    assert result["data"] == entry_data
    assert result["options"] == entry_options

    assert len(result["subentries"]) == 7

    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_connection_failure(
    hass: HomeAssistant, mock_satel: AsyncMock
) -> None:
    """Test the import flow."""

    mock_satel.return_value.connect.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=MOCK_CONFIG_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("user_input", "entry_options"),
    [
        (MOCK_CONFIG_OPTIONS, MOCK_CONFIG_OPTIONS),
        ({}, {CONF_CODE: None}),
    ],
)
async def test_options_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    user_input: dict[str, Any],
    entry_options: dict[str, Any],
) -> None:
    """Test general options flow."""

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == entry_options


@pytest.mark.parametrize(
    ("user_input", "subentry"),
    [
        (MOCK_PARTITION_SUBENTRY.data, MOCK_PARTITION_SUBENTRY),
        (MOCK_ZONE_SUBENTRY.data, MOCK_ZONE_SUBENTRY),
        (MOCK_OUTPUT_SUBENTRY.data, MOCK_OUTPUT_SUBENTRY),
        (MOCK_SWITCHABLE_OUTPUT_SUBENTRY.data, MOCK_SWITCHABLE_OUTPUT_SUBENTRY),
    ],
)
async def test_subentry_creation(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry: MockConfigEntry,
    user_input: dict[str, Any],
    subentry: ConfigSubentry,
) -> None:
    """Test partitions options flow."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, subentry.subentry_type),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_config_entry.subentries) == 1

    subentry_id = list(mock_config_entry.subentries)[0]

    subentry_result = {
        **subentry.as_dict(),
        "subentry_id": subentry_id,
    }
    assert mock_config_entry.subentries.get(subentry_id) == ConfigSubentry(
        **subentry_result
    )


@pytest.mark.parametrize(
    (
        "user_input",
        "subentry",
    ),
    [
        (
            {CONF_NAME: "New Home", CONF_ARM_HOME_MODE: 3},
            MOCK_PARTITION_SUBENTRY,
        ),
        (
            {CONF_NAME: "Backdoor", CONF_ZONE_TYPE: BinarySensorDeviceClass.DOOR},
            MOCK_ZONE_SUBENTRY,
        ),
        (
            {
                CONF_NAME: "Alarm Triggered",
                CONF_ZONE_TYPE: BinarySensorDeviceClass.PROBLEM,
            },
            MOCK_OUTPUT_SUBENTRY,
        ),
        (
            {CONF_NAME: "Gate Lock"},
            MOCK_SWITCHABLE_OUTPUT_SUBENTRY,
        ),
    ],
)
async def test_subentry_reconfigure(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    user_input: dict[str, Any],
    subentry: ConfigSubentry,
) -> None:
    """Test subentry reconfiguration."""

    mock_config_entry_with_subentries.add_to_hass(hass)

    assert await hass.config_entries.async_setup(
        mock_config_entry_with_subentries.entry_id
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (
            mock_config_entry_with_subentries.entry_id,
            subentry.subentry_type,
        ),
        context={
            "source": SOURCE_RECONFIGURE,
            "subentry_id": subentry.subentry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert len(mock_config_entry_with_subentries.subentries) == 4

    subentry_result = {
        **subentry.as_dict(),
        "data": {**subentry.data, **user_input},
        "title": user_input.get(CONF_NAME),
    }

    assert mock_config_entry_with_subentries.subentries.get(
        subentry.subentry_id
    ) == ConfigSubentry(**subentry_result)


@pytest.mark.parametrize(
    ("subentry", "error_field"),
    [
        (MOCK_PARTITION_SUBENTRY, CONF_PARTITION_NUMBER),
        (MOCK_ZONE_SUBENTRY, CONF_ZONE_NUMBER),
        (MOCK_OUTPUT_SUBENTRY, CONF_OUTPUT_NUMBER),
        (MOCK_SWITCHABLE_OUTPUT_SUBENTRY, CONF_SWITCHABLE_OUTPUT_NUMBER),
    ],
)
async def test_cannot_create_same_subentry(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    subentry: dict[str, Any],
    error_field: str,
) -> None:
    """Test subentry reconfiguration."""
    mock_config_entry_with_subentries.add_to_hass(hass)

    assert await hass.config_entries.async_setup(
        mock_config_entry_with_subentries.entry_id
    )
    await hass.async_block_till_done()

    mock_setup_entry.reset_mock()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry_with_subentries.entry_id, subentry.subentry_type),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**subentry.data}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {error_field: "already_configured"}
    assert len(mock_config_entry_with_subentries.subentries) == 4

    assert len(mock_setup_entry.mock_calls) == 0


async def test_same_host_config_disallowed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that only one Satel Integra configuration is allowed."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
