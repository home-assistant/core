"""Common helpers for FMD integration tests."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.fmd.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def get_mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for testing with artifacts (fmd_api 2.0.4+).

    Returns a MockConfigEntry that can be modified before being added to hass.
    """
    from homeassistant.const import CONF_ID, CONF_URL

    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test_user",
        data={
            CONF_URL: "https://fmd.example.com",
            CONF_ID: "test_user",
            "artifacts": {
                "base_url": "https://fmd.example.com",
                "fmd_id": "test_user",
                "access_token": "mock_access_token",
                "private_key": "-----BEGIN PRIVATE KEY-----\nMOCK_KEY\n-----END PRIVATE KEY-----",
                "password_hash": "mock_password_hash",
                "session_duration": 3600,
                "token_issued_at": 1234567890.0,
            },
            "polling_interval": 30,
            "allow_inaccurate_locations": False,
            "use_imperial": False,
        },
        entry_id="test_entry_id",
        unique_id="test_user",
    )


async def setup_integration(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Set up the FMD integration for testing.

    This is a helper function, not a fixture, so tests can call it directly.
    """

    # Mock async_add_executor_job to actually execute the callable
    # This is needed because device_tracker uses it to run decrypt_data_blob
    async def mock_executor_job(func, *args):
        return func(*args)

    config_entry = get_mock_config_entry()
    config_entry.add_to_hass(hass)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
