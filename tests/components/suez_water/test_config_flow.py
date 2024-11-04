"""Test the Suez Water config flow."""

from unittest.mock import AsyncMock

from pysuez.exception import PySuezError
import pytest

from homeassistant import config_entries
from homeassistant.components.suez_water.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_DATA

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, suez_client
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["result"].unique_id == "test-username"
    assert result["data"] == MOCK_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, suez_client
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    suez_client.check_credentials.return_value = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    suez_client.check_credentials.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["result"].unique_id == "test-username"
    assert result["data"] == MOCK_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we abort when entry is already configured."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error"), [(PySuezError, "cannot_connect"), (Exception, "unknown")]
)
async def test_form_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    suez_client,
    error: str,
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    suez_client.check_credentials.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    suez_client.check_credentials.return_value = True
    suez_client.check_credentials.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == MOCK_DATA
    assert len(mock_setup_entry.mock_calls) == 1
