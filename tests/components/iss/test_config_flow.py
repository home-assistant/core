"""Test iss config flow."""

from unittest.mock import patch

from homeassistant.components.iss.const import (
    CONF_PEOPLE_UPDATE_HOURS,
    CONF_POSITION_UPDATE_SECONDS,
    CONF_TLE_SOURCES,
    DEFAULT_PEOPLE_UPDATE_HOURS,
    DEFAULT_POSITION_UPDATE_SECONDS,
    DEFAULT_TLE_SOURCES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test we can finish a config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    with patch("homeassistant.components.iss.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result.get("type") is FlowResultType.CREATE_ENTRY
        assert result.get("result").data == {}


async def test_options_flow_tle_sources(hass: HomeAssistant) -> None:
    """Test options flow with TLE source configuration."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_PEOPLE_UPDATE_HOURS: DEFAULT_PEOPLE_UPDATE_HOURS,
            CONF_POSITION_UPDATE_SECONDS: DEFAULT_POSITION_UPDATE_SECONDS,
            CONF_SHOW_ON_MAP: False,
            CONF_TLE_SOURCES: ["mstl", "celestrak"],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["tle_sources"] == ["mstl", "celestrak"]


async def test_integration_already_exists(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""

    MockConfigEntry(
        domain=DOMAIN,
        data={},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={}
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "single_instance_allowed"


async def test_options(hass: HomeAssistant) -> None:
    """Test options flow."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )

    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.iss.async_setup_entry", return_value=True):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        optionflow = await hass.config_entries.options.async_init(config_entry.entry_id)

        configured = await hass.config_entries.options.async_configure(
            optionflow["flow_id"],
            user_input={
                CONF_SHOW_ON_MAP: True,
            },
        )

        assert configured.get("type") is FlowResultType.CREATE_ENTRY
        expected_options = {
            CONF_SHOW_ON_MAP: True,
            CONF_PEOPLE_UPDATE_HOURS: DEFAULT_PEOPLE_UPDATE_HOURS,
            CONF_POSITION_UPDATE_SECONDS: DEFAULT_POSITION_UPDATE_SECONDS,
            CONF_TLE_SOURCES: DEFAULT_TLE_SOURCES,
        }
        assert config_entry.options == expected_options


async def test_options_validation_errors(hass: HomeAssistant) -> None:
    """Test options flow validation errors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.iss.async_setup_entry", return_value=True):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        # Test invalid people update hours (too low)
        optionflow = await hass.config_entries.options.async_init(config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            optionflow["flow_id"],
            user_input={
                CONF_PEOPLE_UPDATE_HOURS: 0,  # Invalid: below minimum
                CONF_POSITION_UPDATE_SECONDS: 60,
            },
        )
        assert result["type"] == "form"
        assert result["errors"]["people_update_hours"] == "min_people_update_hours"

        # Test invalid position update seconds (too low)
        result = await hass.config_entries.options.async_configure(
            optionflow["flow_id"],
            user_input={
                CONF_PEOPLE_UPDATE_HOURS: 24,
                CONF_POSITION_UPDATE_SECONDS: 0,  # Invalid: below minimum
            },
        )
        assert result["type"] == "form"
        assert (
            result["errors"]["position_update_seconds"] == "min_position_update_seconds"
        )
