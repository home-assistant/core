"""Tests for the authentication library."""

from homeassistant.components.nest import DATA_NEST_CONFIG, DOMAIN, async_get_auth

from .common import CONFIG_ENTRY_ID, async_setup_sdm_platform


async def test_auth_creds(hass):
    """Tests the authentication library can create creds correctly."""
    await async_setup_sdm_platform(hass, "")
    config_entry = hass.config_entries.async_get_entry(CONFIG_ENTRY_ID)
    auth = await async_get_auth(hass, hass.data[DOMAIN][DATA_NEST_CONFIG], config_entry)

    access_token = await auth.async_get_access_token()
    assert "some-token" == access_token

    creds = await auth.async_get_creds()
    assert "example@service.iam.gserviceaccount.com" == creds.service_account_email
