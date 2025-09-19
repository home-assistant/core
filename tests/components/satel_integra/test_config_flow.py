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
    SUBENTRY_TYPE_OUTPUT,
    SUBENTRY_TYPE_PARTITION,
    SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
    SUBENTRY_TYPE_ZONE,
)
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigSubentry,
    ConfigSubentryData,
)
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONST_HOST = "192.168.0.2"
CONST_PORT = 7095
CONST_CODE = "1234"


@pytest.mark.parametrize(
    ("user_input", "entry_data", "entry_options"),
    [
        (
            {CONF_HOST: CONST_HOST, CONF_PORT: CONST_PORT, CONF_CODE: CONST_CODE},
            {CONF_HOST: CONST_HOST, CONF_PORT: CONST_PORT},
            {CONF_CODE: CONST_CODE},
        ),
        (
            {
                CONF_HOST: CONST_HOST,
            },
            {CONF_HOST: CONST_HOST, CONF_PORT: DEFAULT_PORT},
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
    assert result["title"] == CONST_HOST
    assert result["data"] == entry_data
    assert result["options"] == entry_options

    assert len(mock_setup_entry.mock_calls) == 1


async def test_setup_connection_failed(
    hass: HomeAssistant, mock_satel: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the setup flow when connection fails."""
    user_input = {CONF_HOST: CONST_HOST, CONF_PORT: CONST_PORT, CONF_CODE: CONST_CODE}

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
                CONF_HOST: CONST_HOST,
                CONF_PORT: CONST_PORT,
                CONF_CODE: CONST_CODE,
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
            {CONF_HOST: CONST_HOST, CONF_PORT: CONST_PORT},
            {CONF_CODE: CONST_CODE},
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
    assert result["title"] == CONST_HOST
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
        data={CONF_HOST: CONST_HOST, CONF_PORT: CONST_PORT, CONF_CODE: CONST_CODE},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("user_input", "entry_options"),
    [
        (
            {CONF_CODE: CONST_CODE},
            {CONF_CODE: CONST_CODE},
        ),
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
    ("subentry_type", "user_input", "subentry"),
    [
        (
            SUBENTRY_TYPE_PARTITION,
            {CONF_NAME: "Home", CONF_PARTITION_NUMBER: 1, CONF_ARM_HOME_MODE: 1},
            {
                "data": {
                    CONF_NAME: "Home",
                    CONF_ARM_HOME_MODE: 1,
                    CONF_PARTITION_NUMBER: 1,
                },
                "subentry_type": SUBENTRY_TYPE_PARTITION,
                "title": "Home",
                "unique_id": "partition_1",
            },
        ),
        (
            SUBENTRY_TYPE_ZONE,
            {
                CONF_NAME: "Backdoor",
                CONF_ZONE_TYPE: BinarySensorDeviceClass.DOOR,
                CONF_ZONE_NUMBER: 2,
            },
            {
                "data": {
                    CONF_NAME: "Backdoor",
                    CONF_ZONE_TYPE: BinarySensorDeviceClass.DOOR,
                    CONF_ZONE_NUMBER: 2,
                },
                "subentry_type": SUBENTRY_TYPE_ZONE,
                "title": "Backdoor",
                "unique_id": "zone_2",
            },
        ),
        (
            SUBENTRY_TYPE_OUTPUT,
            {
                CONF_NAME: "Power outage",
                CONF_ZONE_TYPE: BinarySensorDeviceClass.SAFETY,
                CONF_OUTPUT_NUMBER: 1,
            },
            {
                "data": {
                    CONF_NAME: "Power outage",
                    CONF_ZONE_TYPE: BinarySensorDeviceClass.SAFETY,
                    CONF_OUTPUT_NUMBER: 1,
                },
                "subentry_type": SUBENTRY_TYPE_OUTPUT,
                "title": "Power outage",
                "unique_id": "output_1",
            },
        ),
        (
            SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
            {
                CONF_NAME: "Gate",
                CONF_SWITCHABLE_OUTPUT_NUMBER: 3,
            },
            {
                "data": {
                    CONF_NAME: "Gate",
                    CONF_SWITCHABLE_OUTPUT_NUMBER: 3,
                },
                "subentry_type": SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
                "title": "Gate",
                "unique_id": "switchable_output_3",
            },
        ),
    ],
)
async def test_subentry_creation(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    config_entry: MockConfigEntry,
    subentry_type: str,
    user_input: dict[str, Any],
    subentry: dict[str, Any],
) -> None:
    """Test partitions options flow."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, subentry_type),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input,
    )

    assert len(config_entry.subentries) == 1

    subentry_id = list(config_entry.subentries)[0]

    subentry["subentry_id"] = subentry_id
    assert config_entry.subentries == {subentry_id: ConfigSubentry(**subentry)}


@pytest.mark.parametrize(
    (
        "user_input",
        "default_subentry_info",
        "subentry",
        "updated_subentry",
    ),
    [
        (
            {CONF_NAME: "New Home", CONF_ARM_HOME_MODE: 3},
            {
                "subentry_id": "ABCD",
                "subentry_type": SUBENTRY_TYPE_PARTITION,
                "unique_id": "partition_1",
            },
            ConfigSubentryData(
                data={
                    CONF_NAME: "Home",
                    CONF_ARM_HOME_MODE: 1,
                    CONF_PARTITION_NUMBER: 1,
                },
                title="Home",
            ),
            ConfigSubentryData(
                data={
                    CONF_NAME: "New Home",
                    CONF_ARM_HOME_MODE: 3,
                    CONF_PARTITION_NUMBER: 1,
                },
                title="New Home",
            ),
        ),
        (
            {CONF_NAME: "Backdoor", CONF_ZONE_TYPE: BinarySensorDeviceClass.DOOR},
            {
                "subentry_id": "ABCD",
                "subentry_type": SUBENTRY_TYPE_ZONE,
                "unique_id": "zone_1",
            },
            ConfigSubentryData(
                data={
                    CONF_NAME: "Zone 1",
                    CONF_ZONE_TYPE: BinarySensorDeviceClass.MOTION,
                    CONF_ZONE_NUMBER: 1,
                },
                title="Zone 1",
            ),
            ConfigSubentryData(
                data={
                    CONF_NAME: "Backdoor",
                    CONF_ZONE_TYPE: BinarySensorDeviceClass.DOOR,
                    CONF_ZONE_NUMBER: 1,
                },
                title="Backdoor",
            ),
        ),
        (
            {
                CONF_NAME: "Alarm Triggered",
                CONF_ZONE_TYPE: BinarySensorDeviceClass.PROBLEM,
            },
            {
                "subentry_id": "ABCD",
                "subentry_type": SUBENTRY_TYPE_OUTPUT,
                "unique_id": "output_1",
            },
            ConfigSubentryData(
                data={
                    CONF_NAME: "Output 1",
                    CONF_ZONE_TYPE: BinarySensorDeviceClass.SAFETY,
                    CONF_OUTPUT_NUMBER: 1,
                },
                title="Output 1",
            ),
            ConfigSubentryData(
                data={
                    CONF_NAME: "Alarm Triggered",
                    CONF_ZONE_TYPE: BinarySensorDeviceClass.PROBLEM,
                    CONF_OUTPUT_NUMBER: 1,
                },
                title="Alarm Triggered",
            ),
        ),
        (
            {CONF_NAME: "Gate Lock"},
            {
                "subentry_id": "ABCD",
                "subentry_type": SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
                "unique_id": "switchable_output_1",
            },
            ConfigSubentryData(
                data={
                    CONF_NAME: "Switchable Output 1",
                    CONF_SWITCHABLE_OUTPUT_NUMBER: 1,
                },
                title="Switchable Output 1",
            ),
            ConfigSubentryData(
                data={
                    CONF_NAME: "Gate Lock",
                    CONF_SWITCHABLE_OUTPUT_NUMBER: 1,
                },
                title="Gate Lock",
            ),
        ),
    ],
)
async def test_subentry_reconfigure(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_setup_entry: AsyncMock,
    config_entry: MockConfigEntry,
    user_input: dict[str, Any],
    default_subentry_info: dict[str, Any],
    subentry: ConfigSubentryData,
    updated_subentry: ConfigSubentryData,
) -> None:
    """Test subentry reconfiguration."""

    config_entry.add_to_hass(hass)
    config_entry.subentries = {
        default_subentry_info["subentry_id"]: ConfigSubentry(
            **default_subentry_info, **subentry
        )
    }

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, default_subentry_info["subentry_type"]),
        context={
            "source": SOURCE_RECONFIGURE,
            "subentry_id": default_subentry_info["subentry_id"],
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
    assert len(config_entry.subentries) == 1

    assert config_entry.subentries == {
        default_subentry_info["subentry_id"]: ConfigSubentry(
            **default_subentry_info, **updated_subentry
        )
    }


@pytest.mark.parametrize(
    ("subentry", "user_input", "error_field"),
    [
        (
            {
                "subentry_type": SUBENTRY_TYPE_PARTITION,
                "unique_id": "partition_1",
                "title": "Home",
            },
            {
                CONF_NAME: "Home",
                CONF_ARM_HOME_MODE: 1,
                CONF_PARTITION_NUMBER: 1,
            },
            CONF_PARTITION_NUMBER,
        ),
        (
            {
                "subentry_type": SUBENTRY_TYPE_ZONE,
                "unique_id": "zone_1",
                "title": "Zone 1",
            },
            {
                CONF_NAME: "Zone 1",
                CONF_ZONE_TYPE: BinarySensorDeviceClass.MOTION,
                CONF_ZONE_NUMBER: 1,
            },
            CONF_ZONE_NUMBER,
        ),
        (
            {
                "subentry_type": SUBENTRY_TYPE_OUTPUT,
                "unique_id": "output_1",
                "title": "Output 1",
            },
            {
                CONF_NAME: "Output 1",
                CONF_ZONE_TYPE: BinarySensorDeviceClass.SAFETY,
                CONF_OUTPUT_NUMBER: 1,
            },
            CONF_OUTPUT_NUMBER,
        ),
        (
            {
                "subentry_type": SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
                "unique_id": "switchable_output_1",
                "title": "Switchable Output 1",
            },
            {
                CONF_NAME: "Switchable Output 1",
                CONF_SWITCHABLE_OUTPUT_NUMBER: 1,
            },
            CONF_SWITCHABLE_OUTPUT_NUMBER,
        ),
    ],
)
async def test_cannot_create_same_subentry(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_setup_entry: AsyncMock,
    config_entry: MockConfigEntry,
    subentry: dict[str, any],
    user_input: dict[str, any],
    error_field: str,
) -> None:
    """Test subentry reconfiguration."""
    config_entry.add_to_hass(hass)
    config_entry.subentries = {
        "ABCD": ConfigSubentry(**subentry, **ConfigSubentryData({"data": user_input}))
    }

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, subentry["subentry_type"]),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {error_field: "already_configured"}
    assert len(config_entry.subentries) == 1


async def test_one_config_allowed(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that only one Satel Integra configuration is allowed."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
