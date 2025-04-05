"""Define fixtures for volvo unit tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from yarl import URL

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.volvo.const import CONF_VIN, DOMAIN, SCOPES
from homeassistant.components.volvo.volvo_connected.auth import AUTHORIZE_URL
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from .const import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture
async def config_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    setup_credentials: None,
) -> config_entries.ConfigFlowResult:
    """Initialize a new config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URI,
        },
    )

    result_url = URL(result["url"])
    assert f"{result_url.origin()}{result_url.path}" == AUTHORIZE_URL
    assert result_url.query["response_type"] == "code"
    assert result_url.query["client_id"] == CLIENT_ID
    assert result_url.query["redirect_uri"] == REDIRECT_URI
    assert result_url.query["state"] == state
    assert result_url.query["code_challenge"]
    assert result_url.query["code_challenge_method"] == "S256"
    assert result_url.query["scope"] == " ".join(SCOPES)

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    return result


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="YV123456789",
        data={
            CONF_API_KEY: "abcdef0123456879abcdef",
            CONF_VIN: "YV123456789",
            CONF_TOKEN: {CONF_ACCESS_TOKEN: "mock-access-token"},
        },
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.volvo.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup
