"""Common tests for Husqvarna Automower module."""
from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

USER_ID = "123"


async def setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Create the Nuki device."""

    token = load_fixture("jwt.js", DOMAIN)

    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Husqvarna Automower of Erika Mustermann",
        data={
            "auth_implementation": "husqvarna_automower_433e5fdf_5129_452c_ba7f_fadce3213042",
            "token": {
                "access_token": token,
                "scope": "iam:read amc:api",
                "expires_in": 86399,
                "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
                "provider": "husqvarna",
                "user_id": USER_ID,
                "token_type": "Bearer",
                "expires_at": 1697753347,
            },
        },
        unique_id=USER_ID,
        entry_id="automower_test",
    )
    return entry
