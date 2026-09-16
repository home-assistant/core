"""Test the Ridder HortiMaX Pro (HortOS) config flow."""

from unittest.mock import AsyncMock

from aiohortos import HortosAuthenticationError, HortosConnectionError, Organisation
import pytest

from homeassistant.components.hortimax.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import API_KEY, ORGANISATION_ID

from tests.common import MockConfigEntry

USER_INPUT = {CONF_API_KEY: API_KEY}


@pytest.mark.usefixtures("mock_hortos_client", "mock_setup_entry")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Test the happy path creates an entry keyed on the organisation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ridder HortiMaX Pro"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == ORGANISATION_ID


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (HortosAuthenticationError("nope"), "invalid_auth"),
        (HortosConnectionError("boom"), "cannot_connect"),
        (RuntimeError("surprise"), "unknown"),
    ],
)
async def test_errors_recover(
    hass: HomeAssistant,
    mock_hortos_client: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test every error is shown and the flow can still be completed."""
    mock_hortos_client.authenticate.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_hortos_client.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_no_devices_recovers(
    hass: HomeAssistant, mock_hortos_client: AsyncMock
) -> None:
    """Test an API key without controllers is rejected."""
    mock_hortos_client.get_device_names.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}

    mock_hortos_client.get_device_names.return_value = ["HOR00000000.000"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_missing_organisation_is_an_error(
    hass: HomeAssistant, mock_hortos_client: AsyncMock
) -> None:
    """Test an entry is never created without the id it is keyed on."""
    tokens = mock_hortos_client.authenticate.return_value
    mock_hortos_client.authenticate.return_value = type(tokens)(
        token=tokens.token,
        expires_at=tokens.expires_at,
        refresh_token=tokens.refresh_token,
        refresh_expires_at=tokens.refresh_expires_at,
        organisation=Organisation(id=None),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    mock_hortos_client.authenticate.return_value = tokens
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ORGANISATION_ID


@pytest.mark.usefixtures("mock_hortos_client", "mock_setup_entry")
async def test_duplicate_organisation_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same organisation cannot be configured twice."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
