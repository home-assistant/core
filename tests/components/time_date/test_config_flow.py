"""Test the Time & Date config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.time_date.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ("sensor",))
async def test_config_flow(hass: HomeAssistant, platform) -> None:
    """Test the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.time_date.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"display_option": "date_time"},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Date & Time"
    assert result["data"] == {}
    assert result["options"] == {"display_option": "date_time"}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {"display_option": "date_time"}
    assert config_entry.title == "Date & Time"


@pytest.mark.parametrize("platform", ("sensor",))
async def test_options(hass: HomeAssistant, platform) -> None:
    """Test reconfiguring."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"display_option": "date_time"},
        title="Time & Date",
    )
    config_entry.add_to_hass(hass)

    # Time & Date has no options flow
    with pytest.raises(data_entry_flow.UnknownHandler):
        await hass.config_entries.options.async_init(config_entry.entry_id)


async def test_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test we abort if already setup."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"display_option": "date_time"},
        title="Time & Date",
        unique_id="date_time",
    )

    config_entry.add_to_hass(hass)

    # Try creating another date_time sensor - should fail
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"display_option": "date_time"},
    )
    await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # Try creating a date sensor - should be allowed
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.time_date.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"display_option": "date"},
        )
        await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY


async def test_single_instance_allowed_import(hass: HomeAssistant) -> None:
    """Test we abort if already setup."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"display_option": "date_time"},
        title="Time & Date",
        unique_id="date_time",
    )

    config_entry.add_to_hass(hass)

    # Try creating another date_time sensor - should fail
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={"display_option": "date_time"},
    )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(
    hass: HomeAssistant,
) -> None:
    """Test the import configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={"display_option": "time_date"},
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Time & Date"
    assert result["data"] == {}
    assert result["options"] == {"display_option": "time_date"}
