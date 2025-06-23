"""Test the solarlog config flow."""

from unittest.mock import AsyncMock

import pytest
from solarlog_cli.solarlog_exceptions import (
    SolarLogAuthenticationError,
    SolarLogConnectionError,
    SolarLogError,
)

from homeassistant.components.solarlog.const import CONF_HAS_PWD, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import HOST

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("test_connect")
async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_HAS_PWD: False},
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == HOST
    assert result2["data"][CONF_HOST] == "http://1.1.1.1"
    assert result2["data"][CONF_HAS_PWD] is False
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("test_connect")
async def test_user(
    hass: HomeAssistant,
    mock_solarlog_connector: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # tests with all provided
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_HAS_PWD: False}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception1", "error1", "exception2", "error2"),
    [
        (
            SolarLogConnectionError,
            {CONF_HOST: "cannot_connect"},
            SolarLogAuthenticationError,
            {CONF_HOST: "password_error"},
        ),
        (SolarLogError, {CONF_HOST: "unknown"}, SolarLogError, {CONF_HOST: "unknown"}),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    exception1: Exception,
    error1: dict[str, str],
    exception2: Exception,
    error2: dict[str, str],
    mock_solarlog_connector: AsyncMock,
) -> None:
    """Test we can handle Form exceptions."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_solarlog_connector.test_connection.side_effect = exception1

    # tests with connection error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: HOST, CONF_HAS_PWD: False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == error1

    # tests with password error
    mock_solarlog_connector.test_connection.side_effect = None
    mock_solarlog_connector.test_extended_data_available.side_effect = exception2

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: HOST, CONF_HAS_PWD: True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "password"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "pwd"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "password"
    assert result["errors"] == error2

    mock_solarlog_connector.test_extended_data_available.side_effect = None

    # tests with all provided
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "pwd"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_PASSWORD] == "pwd"


async def test_abort_if_already_setup(hass: HomeAssistant, test_connect: None) -> None:
    """Test we abort if the device is already setup."""

    MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST}).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: HOST, CONF_HAS_PWD: False},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("has_password", "password"),
    [
        (True, "pwd"),
        (False, ""),
    ],
)
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_solarlog_connector: AsyncMock,
    has_password: bool,
    password: str,
) -> None:
    """Test config flow options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=HOST,
        data={
            CONF_HOST: HOST,
            CONF_HAS_PWD: False,
        },
        minor_version=3,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # test with all data provided
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HAS_PWD: True, CONF_PASSWORD: password}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert len(mock_setup_entry.mock_calls) == 1

    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry
    assert entry.title == HOST
    assert entry.data[CONF_HAS_PWD] == has_password
    assert entry.data[CONF_PASSWORD] == password


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (SolarLogAuthenticationError, {CONF_HOST: "password_error"}),
        (SolarLogError, {CONF_HOST: "unknown"}),
    ],
)
async def test_reauth(
    hass: HomeAssistant,
    exception: Exception,
    error: dict[str, str],
    mock_solarlog_connector: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauth-flow works."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title=HOST,
        data={
            CONF_HOST: HOST,
            CONF_HAS_PWD: True,
            CONF_PASSWORD: "pwd",
        },
        minor_version=3,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_solarlog_connector.test_extended_data_available.side_effect = exception

    # tests with connection error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "other_pwd"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == error

    mock_solarlog_connector.test_extended_data_available.side_effect = None

    # tests with all information provided
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "other_pwd"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "other_pwd"
