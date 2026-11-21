"""Test the Sharp Aquos TV config flow."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.aquostv.const import CONF_POWER_ON_ENABLED, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import HOST

USER_INPUT = {
    CONF_HOST: HOST,
    CONF_PORT: 10002,
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "password",
}


@pytest.mark.usefixtures("mock_tv")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test a successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sharp Aquos TV"
    assert result["data"] == USER_INPUT


@pytest.mark.parametrize(
    ("exception", "error"),
    [(OSError, "cannot_connect"), (RuntimeError, "unknown")],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_tv: MagicMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test errors are shown and the flow can recover."""
    mock_tv.info.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_tv.info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_tv")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a TV can only be configured once."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("power_on_enabled", [True, False])
@pytest.mark.usefixtures("mock_tv")
async def test_import_flow(hass: HomeAssistant, power_on_enabled: bool) -> None:
    """Test importing the YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            **USER_INPUT,
            CONF_NAME: "Living room",
            CONF_POWER_ON_ENABLED: power_on_enabled,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room"
    assert result["data"] == USER_INPUT
    assert result["options"] == {CONF_POWER_ON_ENABLED: power_on_enabled}


async def test_import_flow_tv_unreachable(
    hass: HomeAssistant, mock_tv: MagicMock
) -> None:
    """Test the import does not require the TV to be reachable."""
    mock_tv.info.side_effect = OSError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            **USER_INPUT,
            CONF_NAME: "Living room",
            CONF_POWER_ON_ENABLED: True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_tv")
async def test_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring the connection settings."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PORT: 10003, CONF_USERNAME: "user", CONF_PASSWORD: "secret"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_HOST: HOST,
        CONF_PORT: 10003,
        CONF_USERNAME: "user",
        CONF_PASSWORD: "secret",
    }


@pytest.mark.parametrize(
    ("exception", "error"),
    [(OSError, "cannot_connect"), (RuntimeError, "unknown")],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tv: MagicMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test errors are shown when reconfiguring and the flow can recover."""
    mock_config_entry.add_to_hass(hass)
    mock_tv.info.side_effect = exception
    result = await mock_config_entry.start_reconfigure_flow(hass)
    user_input = {CONF_PORT: 10003, CONF_USERNAME: "user", CONF_PASSWORD: "secret"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_tv.info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
