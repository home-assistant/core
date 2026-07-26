"""Test the Ridder HortiMaX Pro (HortOS) config flow."""

from unittest.mock import AsyncMock

from aiohortos import HortosAuthenticationError, HortosConnectionError, Organisation
import pytest

from homeassistant.components.hortimax.const import CONF_BASE_URL, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import API_KEY, BASE_URL, ORGANISATION_ID

from tests.common import MockConfigEntry

USER_INPUT = {CONF_API_KEY: API_KEY, CONF_BASE_URL: BASE_URL}


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
async def test_entry_without_organisation_has_no_unique_id(
    hass: HomeAssistant, mock_hortos_client: AsyncMock
) -> None:
    """Test an API that does not report an organisation still configures."""
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None


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


@pytest.mark.usefixtures("mock_hortos_client", "mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test re-authentication replaces the API key."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-api-key"
    # The base URL of the existing entry is kept.
    assert mock_config_entry.data[CONF_BASE_URL] == BASE_URL


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (HortosAuthenticationError("nope"), "invalid_auth"),
        (HortosConnectionError("boom"), "cannot_connect"),
        (RuntimeError("surprise"), "unknown"),
    ],
)
async def test_reauth_errors_recover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test re-authentication reports errors and can still be completed."""
    mock_config_entry.add_to_hass(hass)
    mock_hortos_client.authenticate.side_effect = side_effect

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_hortos_client.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_rejects_another_organisation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
) -> None:
    """Test a key for a different organisation cannot replace the entry.

    Accepting it would silently repoint the entry — and the entities and
    history hanging off it — at somebody else's greenhouse.
    """
    mock_config_entry.add_to_hass(hass)
    tokens = mock_hortos_client.authenticate.return_value
    mock_hortos_client.authenticate.return_value = type(tokens)(
        token=tokens.token,
        expires_at=tokens.expires_at,
        refresh_token=tokens.refresh_token,
        refresh_expires_at=tokens.refresh_expires_at,
        organisation=Organisation(id="1234", name="Someone else"),
    )

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "other-organisation-key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    # The original key is left untouched.
    assert mock_config_entry.data[CONF_API_KEY] == API_KEY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_entry_without_organisation_rejects_duplicates(
    hass: HomeAssistant, mock_hortos_client: AsyncMock
) -> None:
    """Test duplicates are still caught when there is no organisation id."""
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
    assert result["type"] is FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_without_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
) -> None:
    """Test re-authentication with a key that has no controllers."""
    mock_config_entry.add_to_hass(hass)
    mock_hortos_client.get_device_names.return_value = []

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}
