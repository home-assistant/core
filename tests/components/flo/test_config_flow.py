"""Test the flo config flow."""
import json
import time

from homeassistant import config_entries, setup
from homeassistant.components.flo.const import DOMAIN

from .common import TEST_EMAIL_ADDRESS, TEST_PASSWORD, TEST_TOKEN, TEST_USER_ID


async def test_form(hass, aioclient_mock_fixture):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": TEST_USER_ID, "password": TEST_PASSWORD}
    )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Home"
    assert result2["data"] == {"username": TEST_USER_ID, "password": TEST_PASSWORD}
    await hass.async_block_till_done()


async def test_form_cannot_connect(hass, aioclient_mock):
    """Test we handle cannot connect error."""
    now = round(time.time())
    # Mocks a failed login response for flo.
    aioclient_mock.post(
        "https://api.meetflo.com/api/v1/users/auth",
        json=json.dumps(
            {
                "token": TEST_TOKEN,
                "tokenPayload": {
                    "user": {"user_id": TEST_USER_ID, "email": TEST_EMAIL_ADDRESS},
                    "timestamp": now,
                },
                "tokenExpiration": 86400,
                "timeNow": now,
            }
        ),
        headers={"Content-Type": "application/json"},
        status=400,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "test-username", "password": "test-password"}
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
