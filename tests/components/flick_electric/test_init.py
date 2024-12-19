"""Test the Flick Electric config flow."""

from unittest.mock import patch

from pyflick.authentication import AuthException

from homeassistant.components.flick_electric.const import (
    CONF_ACCOUNT_ID,
    CONF_SUPPLY_NODE_REF,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_SOURCE, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONF = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_ACCOUNT_ID: "1234",
    CONF_SUPPLY_NODE_REF: "123",
}


async def test_init_auth_failure_triggers_auth(hass: HomeAssistant) -> None:
    """Test reauth flow is triggered when username/password is wrong."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={**CONF}, title="123 Fake St", unique_id="1234", version=2
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
            side_effect=AuthException,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_flow_init,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        mock_flow_init.assert_called_once_with(
            DOMAIN,
            context={
                CONF_SOURCE: SOURCE_REAUTH,
                "entry_id": entry.entry_id,
                "unique_id": entry.unique_id,
            },
            data=entry.data,
        )
        assert entry.state is ConfigEntryState.SETUP_ERROR
