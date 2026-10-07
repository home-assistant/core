"""Tests for the MAWAQIT config flow."""

from unittest.mock import AsyncMock, MagicMock

import httpx
from mawaqit import APIConnectionError, AuthenticationError, MawaqitError
import pytest

from homeassistant.components.mawaqit.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_EMAIL, CONF_PASSWORD, CONF_UUID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOSQUE_UUID, TOKEN

from tests.common import MockConfigEntry

USER_INPUT = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "password"}
REQUEST = httpx.Request("POST", "https://mawaqit.net/api/2.0/me")


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant, mock_mawaqit_client: MagicMock) -> None:
    """Test logging in and selecting a mosque."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mosques_coordinates"
    assert result["data_schema"].schema[CONF_UUID].container == {
        MOSQUE_UUID: "GRANDE MOSQUÉE DE PARIS (0.13 km)",
        "e5a23c75-9828-410d-81da-be3ac2fd5194": "Mosquée Bilal ben Rabah (1.27 km)",
    }
    mock_mawaqit_client.auth.login.assert_awaited_once_with(
        email="user@example.com", password="password"
    )
    mock_mawaqit_client.mosques.search.assert_awaited_once_with(
        lat=hass.config.latitude, lon=hass.config.longitude
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_UUID: MOSQUE_UUID}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "GRANDE MOSQUÉE DE PARIS"
    assert result["data"] == {CONF_API_KEY: TOKEN, CONF_UUID: MOSQUE_UUID}


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            AuthenticationError(
                "Invalid credentials.", httpx.Response(401, request=REQUEST), body=None
            ),
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(APIConnectionError(REQUEST), "cannot_connect", id="connection"),
        pytest.param(MawaqitError(), "cannot_connect", id="mawaqit_error"),
    ],
)
async def test_login_errors(
    hass: HomeAssistant,
    mock_mawaqit_client: MagicMock,
    side_effect: MawaqitError,
    error: str,
) -> None:
    """Test login errors are shown, and the flow recovers from them."""
    mock_mawaqit_client.auth.login.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_mawaqit_client.auth.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_UUID: MOSQUE_UUID}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("search", "reason"),
    [
        pytest.param(
            AsyncMock(side_effect=APIConnectionError(REQUEST)),
            "cannot_connect",
            id="connection",
        ),
        pytest.param(AsyncMock(return_value=[]), "no_mosque", id="no_mosque"),
    ],
)
async def test_search_aborts(
    hass: HomeAssistant,
    mock_mawaqit_client: MagicMock,
    search: AsyncMock,
    reason: str,
) -> None:
    """Test the flow aborts when no mosque can be found."""
    mock_mawaqit_client.mosques.search = search
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_mosque_without_distance(
    hass: HomeAssistant, mock_mawaqit_client: MagicMock
) -> None:
    """Test a mosque is shown by its name when the API gives no distance."""
    mosques = mock_mawaqit_client.mosques.search.return_value
    mosques[0] = mosques[0].model_copy(update={"proximity": None})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    options = result["data_schema"].schema[CONF_UUID].container
    assert options[MOSQUE_UUID] == "GRANDE MOSQUÉE DE PARIS"


async def test_single_instance(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test only one MAWAQIT entry can be added."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
