"""Test EDL21 config flow."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.edl21 import config_flow
from homeassistant.components.edl21.const import (
    CONF_LIMIT_INTERVAL,
    CONF_SERIAL_PORT,
    CONF_UPDATE_INTERVAL,
    DEFAULT_LIMITED_UPDATE_INTERVAL,
    DEFAULT_TITLE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

VALID_CONFIG = {CONF_SERIAL_PORT: "/dev/ttyUSB1"}
VALID_CONFIG_WITH_INTERVAL = {
    CONF_SERIAL_PORT: "/dev/ttyUSB1",
    CONF_LIMIT_INTERVAL: True,
    CONF_UPDATE_INTERVAL: 10,
}
VALID_LEGACY_CONFIG = {CONF_NAME: "My Smart Meter", CONF_SERIAL_PORT: "/dev/ttyUSB1"}

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        VALID_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_TITLE
    assert result["data"][CONF_SERIAL_PORT] == VALID_CONFIG[CONF_SERIAL_PORT]
    assert result["data"][CONF_UPDATE_INTERVAL] == DEFAULT_UPDATE_INTERVAL


async def test_create_entry_with_update_interval(hass: HomeAssistant) -> None:
    """Test that a configured update interval is stored."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        VALID_CONFIG_WITH_INTERVAL,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_UPDATE_INTERVAL] == 10
    assert CONF_LIMIT_INTERVAL not in result["data"]


async def test_integration_already_exists(hass: HomeAssistant) -> None:
    """Test that a new entry must not have the same serial port as an existing entry."""

    MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test that a limited update interval can be set via the options flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    marker = next(m for m in result["data_schema"].schema if m == CONF_LIMIT_INTERVAL)
    assert marker.default() is False
    marker = next(m for m in result["data_schema"].schema if m == CONF_UPDATE_INTERVAL)
    assert marker.default() == DEFAULT_LIMITED_UPDATE_INTERVAL

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_LIMIT_INTERVAL: True, CONF_UPDATE_INTERVAL: 30},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_UPDATE_INTERVAL] == 30


async def test_options_flow_unchecks_limit(hass: HomeAssistant) -> None:
    """Test that unchecking the limit disables throttling (interval 0)."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG_WITH_INTERVAL)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_LIMIT_INTERVAL: False},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_UPDATE_INTERVAL] == DEFAULT_UPDATE_INTERVAL


async def test_options_flow_missing_interval_uses_default(hass: HomeAssistant) -> None:
    """Test that a checked limit without a number falls back to the schema default."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_LIMIT_INTERVAL: True},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_UPDATE_INTERVAL] == DEFAULT_LIMITED_UPDATE_INTERVAL


async def test_options_flow_out_of_range_interval_rejected(hass: HomeAssistant) -> None:
    """Test that the number selector range is enforced by schema validation."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_LIMIT_INTERVAL: True, CONF_UPDATE_INTERVAL: 5000},
        )

    assert entry.options == {}


async def test_options_flow_defaults_to_data_value(hass: HomeAssistant) -> None:
    """Test that the options flow prefills the limit and interval from the entry data."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG_WITH_INTERVAL)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    marker = next(m for m in result["data_schema"].schema if m == CONF_LIMIT_INTERVAL)
    assert marker.description == {"suggested_value": True}
    marker = next(m for m in result["data_schema"].schema if m == CONF_UPDATE_INTERVAL)
    assert marker.description == {"suggested_value": 10}


async def test_options_flow_backend_guard_shows_errors(hass: HomeAssistant) -> None:
    """Test the backend guard when an API client bypasses the form schema."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG)
    entry.add_to_hass(hass)

    flow = config_flow.EDL21ConfigFlow.async_get_options_flow(entry)
    flow.hass = hass
    flow.handler = entry.entry_id

    result = await flow.async_step_init(
        user_input={CONF_LIMIT_INTERVAL: True, CONF_UPDATE_INTERVAL: "abc"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_UPDATE_INTERVAL: "invalid_update_interval"}
    schema = result["data_schema"]
    marker = next(m for m in schema.schema if m == CONF_LIMIT_INTERVAL)
    assert marker.description == {"suggested_value": True}
    marker = next(m for m in schema.schema if m == CONF_UPDATE_INTERVAL)
    assert marker.description == {"suggested_value": "abc"}

    result = await flow.async_step_init(
        user_input={CONF_LIMIT_INTERVAL: True, CONF_UPDATE_INTERVAL: 30}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_UPDATE_INTERVAL: 30}


async def test_options_flow_backend_guard_rejects_zero(hass: HomeAssistant) -> None:
    """Test that 0 stays invalid when the limit checkbox is on."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG)
    entry.add_to_hass(hass)

    flow = config_flow.EDL21ConfigFlow.async_get_options_flow(entry)
    flow.hass = hass
    flow.handler = entry.entry_id

    result = await flow.async_step_init(
        user_input={CONF_LIMIT_INTERVAL: True, CONF_UPDATE_INTERVAL: 0}
    )

    assert result["errors"] == {CONF_UPDATE_INTERVAL: "invalid_update_interval"}
    assert entry.options == {}

    result = await flow.async_step_init(
        user_input={CONF_LIMIT_INTERVAL: True, CONF_UPDATE_INTERVAL: 30}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_UPDATE_INTERVAL: 30}


async def test_config_flow_backend_guard_shows_errors(hass: HomeAssistant) -> None:
    """Test the config flow guard when an API client bypasses the form schema."""
    flow = config_flow.EDL21ConfigFlow()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}

    result = await flow.async_step_user(
        user_input={
            CONF_SERIAL_PORT: "/dev/ttyUSB1",
            CONF_LIMIT_INTERVAL: True,
            CONF_UPDATE_INTERVAL: 5000,
        }
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_UPDATE_INTERVAL: "invalid_update_interval"}
    schema = result["data_schema"]
    marker = next(m for m in schema.schema if m == CONF_SERIAL_PORT)
    assert marker.description == {"suggested_value": "/dev/ttyUSB1"}
    marker = next(m for m in schema.schema if m == CONF_UPDATE_INTERVAL)
    assert marker.description == {"suggested_value": 5000}

    result = await flow.async_step_user(
        user_input={
            CONF_SERIAL_PORT: "/dev/ttyUSB1",
            CONF_LIMIT_INTERVAL: True,
            CONF_UPDATE_INTERVAL: 10,
        }
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_SERIAL_PORT: "/dev/ttyUSB1",
        CONF_UPDATE_INTERVAL: 10,
    }
