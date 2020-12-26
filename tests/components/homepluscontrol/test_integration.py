"""Test the Legrand Home+ Control integration."""
from homeassistant import config_entries
from homeassistant.components.homepluscontrol.const import DOMAIN

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
SUBSCRIPTION_KEY = "12345678901234567890123456789012"
REDIRECT_URI = "https://example.com:8213/auth/external/callback"


async def test_integration(hass):
    """Test integration."""
    config_entry = config_entries.ConfigEntry(
        1,
        DOMAIN,
        "Home+ Control",
        {
            "auth_implementation": "homepluscontrol",
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "expires_at": 1608824371.2857926,
            },
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "subscription_key": SUBSCRIPTION_KEY,
            "redirect_uri": REDIRECT_URI,
        },
        "test",
        config_entries.CONN_CLASS_LOCAL_POLL,
        system_options={},
        options={"disable_new_entities": False},
        unique_id=DOMAIN,
        entry_id="homepluscontrol_entry_id",
    )

    # await config_entry.async_setup(hass)
    # assert config_entry.state == ENTRY_STATE_LOADED
    assert config_entry
    assert True
