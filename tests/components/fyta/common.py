"""Common methods used across tests for Abode."""

from datetime import UTC, datetime
from unittest.mock import patch

from homeassistant.components.fyta.const import CONF_EXPIRATION, DOMAIN as FYTA_DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

USERNAME = "fyta_user"
PASSWORD = "fyta_pass"
ACCESS_TOKEN = "123xyz"
EXPIRATION = datetime.fromisoformat("2024-12-31T10:00:00").replace(tzinfo=UTC)
EXPIRATION_OLD = datetime.fromisoformat("2024-01-01T10:00:00").replace(tzinfo=UTC)


async def setup_platform(hass: HomeAssistant, platform: str) -> MockConfigEntry:
    """Set up the Fyta platform."""
    mock_entry = MockConfigEntry(
        domain=FYTA_DOMAIN,
        title="fyta_user",
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_EXPIRATION: EXPIRATION.isoformat(),
        },
        minor_version=2,
    )
    mock_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.fyta.PLATFORMS", [platform]),
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    return mock_entry


async def setup_platform_expired(hass: HomeAssistant, platform: str) -> MockConfigEntry:
    """Set up the Fyta platform with expired access token."""
    mock_entry = MockConfigEntry(
        domain=FYTA_DOMAIN,
        title="fyta_user",
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_EXPIRATION: EXPIRATION_OLD.isoformat(),
        },
        minor_version=2,
    )
    mock_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.fyta.PLATFORMS", [platform]),
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    return mock_entry
