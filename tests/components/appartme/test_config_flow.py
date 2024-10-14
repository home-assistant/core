"""Tests for the Appartme config flow."""

from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.appartme.const import DOMAIN
from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_full_flow(hass):
    """Test the full config flow."""

    # Set up the application_credentials component
    assert await async_setup_component(hass, "application_credentials", {})
    await hass.async_block_till_done()

    # Import application credentials
    await hass.components.application_credentials.async_import_client_credential(
        hass=hass,
        domain=DOMAIN,
        credential=ClientCredential(
            client_id="test-client-id",
            client_secret="test-client-secret",
        ),
    )

    # Mock authorization server
    with patch(
        "homeassistant.components.appartme.application_credentials.async_get_authorization_server",
        return_value=AuthorizationServer(
            authorize_url="https://example.com/authorize",
            token_url="https://example.com/token",
        ),
    ):
        # Initiate the config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Assert that we reach the external step
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "pick_implementation"


async def test_options_flow(hass):
    """Test the options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": {"access_token": "test-access-token"}},
        options={"update_interval": 60},
    )
    config_entry.add_to_hass(hass)

    # Initiate the options flow
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    # Submit valid options
    with patch(
        "homeassistant.components.appartme.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"update_interval": "120"}
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert config_entry.options == {"update_interval": 120}

    # Submit invalid options (non-integer)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"update_interval": "invalid"}
    )
    assert result["errors"] == {"update_interval": "invalid_int"}

    # Submit invalid options (below minimum)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"update_interval": "10"}
    )
    assert result["errors"] == {"update_interval": "interval_too_short"}
