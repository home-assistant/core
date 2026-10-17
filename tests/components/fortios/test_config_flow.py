"""Tests for FortiOS configuration and reauthentication."""

from unittest.mock import MagicMock

from aiofortiosapi import FortiOSAuthenticationError, FortiOSConnectionError
import pytest

from homeassistant.components.fortios.client import UnsupportedVersion
from homeassistant.components.fortios.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import USER_INPUT

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Validate credentials and persist device identity."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == "FGT123456"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (FortiOSAuthenticationError(), "invalid_auth"),
        (FortiOSConnectionError(), "cannot_connect"),
        (UnsupportedVersion(), "unsupported_version"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_errors(
    hass: HomeAssistant, mock_client: MagicMock, exception: Exception, error: str
) -> None:
    """Show an actionable error for failed validation."""
    mock_client.connect.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    mock_client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "FGT123456"


@pytest.mark.usefixtures("mock_client")
@pytest.mark.parametrize("source", [SOURCE_USER, SOURCE_IMPORT])
async def test_duplicate(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, source: str
) -> None:
    """Repeated user setup and YAML imports do not duplicate entries."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry", "mock_client")
async def test_import(hass: HomeAssistant) -> None:
    """Preserve the configured consider-home period on import."""
    data = USER_INPUT | {"consider_home": 300}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=data
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == data
    assert result["result"].unique_id == "FGT123456"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A replacement token updates the existing entry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=USER_INPUT,
    )
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "replacement"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_TOKEN] == "replacement"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (FortiOSAuthenticationError(), "invalid_auth"),
        (FortiOSConnectionError(), "cannot_connect"),
        (UnsupportedVersion(), "unsupported_version"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Rejected replacement credentials leave the original token intact and allow retry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=USER_INPUT,
    )
    mock_client.connect.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "replacement"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert mock_config_entry.data[CONF_TOKEN] == USER_INPUT[CONF_TOKEN]
    mock_client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "replacement"}
    )
    assert result["reason"] == "reauth_successful"


async def test_reauth_different_device(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Never update an existing entry using credentials for a different device."""
    mock_config_entry.add_to_hass(hass)
    mock_client.connect.return_value = "OTHER-SERIAL"
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=USER_INPUT,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "replacement"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data[CONF_TOKEN] == USER_INPUT[CONF_TOKEN]


@pytest.mark.usefixtures("mock_client")
async def test_duplicate_serial(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A changed hostname does not duplicate a device with the same serial."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_INPUT | {"host": "other-name"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
