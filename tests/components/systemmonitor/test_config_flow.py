"""Test the systemmonitor config flow."""
from __future__ import annotations

from unittest.mock import patch
import uuid

from homeassistant import config_entries
from homeassistant.components.systemmonitor.const import CONF_ARG, CONF_INDEX, DOMAIN
from homeassistant.const import CONF_NAME, CONF_TYPE, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.systemmonitor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_TYPE: "network_in",
                CONF_ARG: "eth0",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["version"] == 1
    assert result2["options"] == {
        "sensor": [
            {
                CONF_TYPE: "network_in",
                CONF_ARG: "eth0",
                CONF_NAME: "Network in eth0",
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
            }
        ],
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_fails(hass: HomeAssistant) -> None:
    """Test config flow error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_TYPE: "network_in",
        },
    )

    assert result2["errors"] == {"base": "missing_arg"}

    with patch(
        "homeassistant.components.systemmonitor.async_setup_entry",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_TYPE: "network_in",
                CONF_ARG: "eth0",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Systemmonitor"
    assert result3["options"] == {
        "sensor": [
            {
                CONF_TYPE: "network_in",
                CONF_ARG: "eth0",
                CONF_NAME: "Network in eth0",
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
            }
        ],
    }


async def test_options_add_remove_sensor_flow(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test options flow to add and remove a sensor."""

    assert len(hass.states.async_all()) == 1

    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_sensor"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "add_sensor"

    with patch(
        "homeassistant.components.systemmonitor.config_flow.uuid.uuid1",
        return_value=uuid.UUID("3699ef88-69e6-11ed-a1eb-0242ac120003"),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_TYPE: "disk_free",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "sensor": [
            {
                CONF_TYPE: "network_in",
                CONF_ARG: "eth0",
                CONF_NAME: "Network in eth0",
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
            },
            {
                CONF_TYPE: "disk_free",
                CONF_NAME: "Disk free",
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120003",
            },
        ],
    }

    await hass.async_block_till_done()

    # Check the entity was updated, with the new entity
    assert len(hass.states.async_all()) == 2

    # Now remove the original sensor
    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "remove_sensor"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "remove_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_INDEX: ["0"],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "sensor": [
            {
                CONF_TYPE: "disk_free",
                CONF_NAME: "Disk free",
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120003",
            },
        ],
    }

    await hass.async_block_till_done()

    # Check the original entity was removed, with only the new entity left
    assert len(hass.states.async_all()) == 1


async def test_options_edit_sensor_flow(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test options flow to edit a sensor."""

    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "select_edit_sensor"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "select_edit_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_INDEX: "0"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "edit_sensor"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_TYPE: "network_in",
            CONF_ARG: "eth1",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "sensor": [
            {
                CONF_TYPE: "network_in",
                CONF_ARG: "eth1",
                CONF_NAME: "Network in eth1",
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
            },
        ],
    }

    await hass.async_block_till_done()

    # Check the entity was updated
    assert len(hass.states.async_all()) == 1
