"""Test the Sensibo config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, PropertyMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from pysensibo import SensiboClient

DOMAIN = "sensibo"

TEST_DEVICES: list = ["all", "kalle", "olle"]


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient",
        new_callable=AsyncMock,
    ) as mock_sensibo, patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_devices",
        return_value=TEST_DEVICES,
        new_callable=AsyncMock,
    ), patch(
        "homeassistant.components.sensibo.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Sensibo@Home",
                CONF_API_KEY: "1234567890",
            },
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "id"
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] is None

    with patch(
        "homeassistant.components.sensibo.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"id": "all"}
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "Sensibo@Home"
    assert result3["data"] == {
        "name": "Sensibo@Home",
        "api_key": "1234567890",
        "id": ["all"],
    }

    assert len(mock_sensibo.mock_calls) == 2
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test a successful import of yaml."""

    with patch(
        "homeassistant.components.sensibo.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_NAME: "Sensibo@Home",
                CONF_API_KEY: "1234567890",
                CONF_ID: ["all"],
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Sensibo@Home"
    assert result2["data"] == {
        "name": "Sensibo@Home",
        "api_key": "1234567890",
        "id": ["all"],
    }
    assert len(mock_setup_entry.mock_calls) == 1
