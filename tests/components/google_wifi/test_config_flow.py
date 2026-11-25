"""Test the Google Wifi config flow."""

from unittest.mock import AsyncMock, patch

from googlewifiapi.exception import GoogleWifiClientError, GoogleWifiDataValidationError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.google_wifi import CONF_HOST, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.usefixtures("mock_success")
async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.1"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Google Wifi"
    assert result["data"] == {CONF_HOST: "192.168.86.1"}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_success")
async def test_import(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test importing a configuration."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "192.168.86.1",
            CONF_NAME: "Test Wifi",
            "monitored_conditions": ["uptime"],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Wifi"
    assert result["data"] == {
        CONF_HOST: "192.168.86.1",
        CONF_NAME: "Test Wifi",
        "monitored_conditions": ["uptime"],
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_success")
async def test_import_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "192.168.86.1"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_success")
async def test_user_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.1"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (GoogleWifiClientError(), "cannot_connect"),
        (GoogleWifiDataValidationError(), "unknown"),
    ],
)
async def test_user_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test user flow handles an unreachable or invalid response."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.google_wifi.config_flow.GoogleWifiAPI.async_update",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.86.1"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    with patch(
        "homeassistant.components.google_wifi.config_flow.GoogleWifiAPI.async_update",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.86.1"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (GoogleWifiClientError(), "cannot_connect"),
        (GoogleWifiDataValidationError(), "unknown"),
    ],
)
async def test_import_cannot_connect(
    hass: HomeAssistant,
    exception: Exception,
    reason: str,
) -> None:
    """Test YAML import handles an unreachable or invalid response."""
    with patch(
        "homeassistant.components.google_wifi.config_flow.GoogleWifiAPI.async_update",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: "192.168.86.1"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
