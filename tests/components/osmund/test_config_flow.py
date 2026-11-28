"""Test the Osmund config flow."""

from unittest.mock import AsyncMock

from osmund import (
    OsmundAccessError,
    OsmundAuthError,
    OsmundConnectionError,
    OsmundScopeError,
    OsmundUnavailableError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.osmund.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import KEY, LOCATIONS


@pytest.mark.usefixtures("mock_setup_entry", "mock_client")
async def test_create_entry(hass: HomeAssistant) -> None:
    """A key that reads the prices of a location creates the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: f" {KEY} "}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Osmund"
    assert result["data"] == {CONF_API_KEY: KEY}


@pytest.mark.parametrize(
    ("call", "exception", "error"),
    [
        pytest.param(
            "me", OsmundAuthError("Unauthorized"), "invalid_auth", id="invalid_auth"
        ),
        pytest.param(
            "me",
            OsmundUnavailableError("Too many requests", 42),
            "unavailable",
            id="unavailable",
        ),
        pytest.param(
            "me",
            OsmundConnectionError("Timeout"),
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(
            "locations",
            OsmundScopeError("Scope required"),
            "missing_scope",
            id="scope_refused",
        ),
        pytest.param(
            "locations", OsmundAccessError("Closed"), "no_access", id="access_refused"
        ),
        pytest.param("me", Exception("Boom"), "unknown", id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_errors_and_recovery(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    call: str,
    exception: Exception,
    error: str,
) -> None:
    """An error is shown on the form, and the next try can still succeed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    getattr(mock_client, call).side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: KEY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    getattr(mock_client, call).side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: KEY}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_a_key_that_is_not_an_osmund_key(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """A key that does not start with osm_ is refused before any call."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "sk_not_ours"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_API_KEY: "invalid_format"}
    mock_client.me.assert_not_called()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: KEY}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_a_key_that_cannot_read_prices(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """A key without the prices scope is refused."""
    key = mock_client.me.return_value
    mock_client.me.return_value = type(key)(
        name=key.name,
        prefix=key.prefix,
        scopes=frozenset({"consumption:read"}),
        expires_at=None,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: KEY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_scope"}

    mock_client.me.return_value = key
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: KEY}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_no_location_with_api_access(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """A customer without a location with API access cannot set it up."""
    mock_client.locations.return_value = [LOCATIONS[1]]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: KEY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_access"}

    mock_client.locations.return_value = LOCATIONS
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: KEY}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry", "mock_client")
async def test_only_one_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A key reads every location of a customer, so one entry is enough."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
