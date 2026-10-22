"""Test the UniFi Protect utils."""

import pytest

from homeassistant.components.unifiprotect.const import (
    CONF_CONNECTION_MODE,
    CONF_OVERRIDE_CHOST,
    CONNECTION_MODE_API_KEY_ONLY,
    DOMAIN,
)
from homeassistant.components.unifiprotect.utils import (
    async_create_api_client,
    async_create_session_client,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from .utils import MockUFPFixture

from tests.common import MockConfigEntry


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


@pytest.mark.parametrize(
    ("connection_mode", "public_only"),
    [
        pytest.param({}, False, id="hybrid"),
        pytest.param(
            {CONF_CONNECTION_MODE: CONNECTION_MODE_API_KEY_ONLY}, True, id="public_only"
        ),
    ],
)
async def test_host_override_reaches_the_client(
    hass: HomeAssistant, connection_mode: dict[str, str], public_only: bool
) -> None:
    """The host override option has to reach the client in both modes.

    The library rewrites the host of the public RTSPS URLs only when the
    client carries the flag, and a public-only entry has no other stream
    source to fall back on.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 443,
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_API_KEY: "test-api-key",
            CONF_VERIFY_SSL: False,
            **connection_mode,
        },
        options={CONF_OVERRIDE_CHOST: True},
    )
    entry.add_to_hass(hass)

    protect = async_create_api_client(hass, entry)

    assert protect.is_public_only is public_only
    assert protect.override_connection_host is True
