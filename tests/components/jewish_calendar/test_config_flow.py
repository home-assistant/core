"""Test the Jewish calendar config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries, setup
from homeassistant.components.jewish_calendar import (
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_DIASPORA,
    CONF_HAVDALAH_OFFSET_MINUTES,
    CONF_LANGUAGE,
    DEFAULT_DIASPORA,
    DEFAULT_LANGUAGE,
    DOMAIN,
    config_flow,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_step_user(hass: HomeAssistant) -> None:
    """Test user config."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    with (
        patch(
            "homeassistant.components.jewish_calendar.async_setup",
            return_value=True,
        ) as mock_setup,
        patch(
            "homeassistant.components.jewish_calendar.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": "JCalendar", "diaspora": True, "language": "hebrew"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == config_flow.DEFAULT_NAME
    assert result2["data"] == {
        "name": "JCalendar",
        "diaspora": True,
        "language": "hebrew",
        "location": {
            "latitude": hass.config.latitude,
            "longitude": hass.config.longitude,
        },
        "elevation": hass.config.elevation,
        "time_zone": hass.config.time_zone,
    }

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("diaspora", [True, False])
@pytest.mark.parametrize("language", ["hebrew", "english"])
async def test_import_no_options(hass: HomeAssistant, language, diaspora) -> None:
    """Test that the import step works."""
    conf = {
        DOMAIN: {CONF_NAME: "test", CONF_LANGUAGE: language, CONF_DIASPORA: diaspora}
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=conf.copy(),
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == config_flow.DEFAULT_NAME
    assert result["data"] == conf


async def test_import_with_options(hass: HomeAssistant) -> None:
    """Test that the import step works."""
    conf = {
        DOMAIN: {
            CONF_NAME: "test",
            CONF_DIASPORA: DEFAULT_DIASPORA,
            CONF_LANGUAGE: DEFAULT_LANGUAGE,
            CONF_CANDLE_LIGHT_MINUTES: 20,
            CONF_HAVDALAH_OFFSET_MINUTES: 50,
            CONF_LATITUDE: 31.76,
            CONF_LONGITUDE: 35.235,
        }
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=conf.copy(),
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == config_flow.DEFAULT_NAME
    assert result["data"] == conf


async def test_single_instance_allowed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already setup."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "single_instance_allowed"


async def test_options(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test updating options."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_CANDLE_LIGHT_MINUTES: 25,
            CONF_HAVDALAH_OFFSET_MINUTES: 34,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CANDLE_LIGHT_MINUTES] == 25
    assert result["data"][CONF_HAVDALAH_OFFSET_MINUTES] == 34
