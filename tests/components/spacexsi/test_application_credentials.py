"""Verify registration and lookup through Home Assistant's credential platform."""

import pytest
from spacexai_subscription_client.const import GROK_CLI_OAUTH_CLIENT_ID, TOKEN_URL

from homeassistant.components import application_credentials
from homeassistant.components.spacexsi.const import AUTH_IMPLEMENTATION, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    async_get_config_entry_implementation,
)
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures("mock_spacexai_subscription_client")
async def test_fixed_public_client_registration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Import once without an app-registration dialog and resolve a stored entry."""
    await setup_integration(hass, mock_config_entry)
    credentials = hass.data[application_credentials.DATA_COMPONENT]
    before = credentials.async_items()
    assert len(before) == 1
    assert before[0]["client_id"] == GROK_CLI_OAUTH_CLIENT_ID
    assert before[0]["client_secret"] == ""
    assert before[0]["auth_domain"] == before[0]["id"] == AUTH_IMPLEMENTATION

    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert credentials.async_items() == before

    implementation = await async_get_config_entry_implementation(
        hass, mock_config_entry
    )
    assert isinstance(implementation, application_credentials.AuthImplementation)
    assert implementation.client_id == GROK_CLI_OAUTH_CLIENT_ID
    assert implementation.client_secret == ""
    assert implementation.token_url == TOKEN_URL


@pytest.mark.usefixtures("mock_spacexai_subscription_client")
async def test_shared_credential_removal_and_readd(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Protect shared credentials, then recreate deleted unused credentials on add."""
    await setup_integration(hass, mock_config_entry)
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="other-account",
        data=dict(mock_config_entry.data),
    )
    await setup_integration(hass, other_entry)
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "application_credentials/delete",
            "application_credentials_id": AUTH_IMPLEMENTATION,
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await client.send_json(
        {
            "id": 2,
            "type": "application_credentials/delete",
            "application_credentials_id": AUTH_IMPLEMENTATION,
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"

    assert await hass.config_entries.async_remove(other_entry.entry_id)
    await client.send_json(
        {
            "id": 3,
            "type": "application_credentials/delete",
            "application_credentials_id": AUTH_IMPLEMENTATION,
        }
    )
    assert (await client.receive_json())["success"]
    assert not hass.data[application_credentials.DATA_COMPONENT].async_items()

    replacement = MockConfigEntry(
        domain=DOMAIN,
        unique_id="replacement-account",
        data=dict(mock_config_entry.data),
    )
    await setup_integration(hass, replacement)
    implementation = await async_get_config_entry_implementation(hass, replacement)
    assert implementation.client_id == GROK_CLI_OAUTH_CLIENT_ID
    assert len(hass.data[application_credentials.DATA_COMPONENT].async_items()) == 1


@pytest.mark.usefixtures("mock_spacexai_subscription_client")
async def test_existing_public_client_credential(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reuse a normal UI credential for the fixed client, ignoring another client."""
    assert await async_setup_component(hass, "application_credentials", {})
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "application_credentials/create",
            "domain": DOMAIN,
            "client_id": GROK_CLI_OAUTH_CLIENT_ID,
            "client_secret": "",
        }
    )
    assert (await client.receive_json())["success"]
    await client.send_json(
        {
            "id": 2,
            "type": "application_credentials/create",
            "domain": DOMAIN,
            "client_id": "unrelated-client",
            "client_secret": "",
        }
    )
    assert (await client.receive_json())["success"]

    await setup_integration(hass, mock_config_entry)
    implementation = await async_get_config_entry_implementation(
        hass, mock_config_entry
    )
    assert implementation.client_id == GROK_CLI_OAUTH_CLIENT_ID
    assert len(hass.data[application_credentials.DATA_COMPONENT].async_items()) == 2
