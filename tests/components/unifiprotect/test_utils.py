"""Test the UniFi Protect utils."""

from homeassistant.components.unifiprotect.const import (
    CONF_CONNECTION_MODE,
    CONNECTION_MODE_API_KEY_ONLY,
)
from homeassistant.components.unifiprotect.utils import async_create_session_client
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .utils import MockUFPFixture


async def test_session_client_is_full_access_for_api_key_only_entry(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """A session clear on an API-key-only entry goes through a full client.

    A public-only client carries no username, so its ``clear_session`` returns
    early and a session stored before the mode switch would survive.
    """
    hass.config_entries.async_update_entry(
        ufp.entry,
        data={**ufp.entry.data, CONF_CONNECTION_MODE: CONNECTION_MODE_API_KEY_ONLY},
    )

    protect = async_create_session_client(hass, ufp.entry)

    assert protect is not None
    assert not protect.is_public_only


async def test_session_client_none_without_credentials(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """An entry created in API-key-only mode has no session to clear."""
    data = {k: v for k, v in ufp.entry.data.items() if k != CONF_PASSWORD}
    hass.config_entries.async_update_entry(
        ufp.entry,
        data={**data, CONF_CONNECTION_MODE: CONNECTION_MODE_API_KEY_ONLY},
    )

    assert async_create_session_client(hass, ufp.entry) is None
