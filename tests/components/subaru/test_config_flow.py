"""Test the Subaru config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.subaru.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.subaru.const import DOMAIN
from homeassistant.const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_PIN, CONF_USERNAME

from tests.common import mock_coro

TEST_USERNAME = "test@fake.com"
TEST_TITLE = TEST_USERNAME
TEST_PASSWORD = "test-password"
TEST_PIN = "1234"
TEST_DEVICE_ID = "Test Device ID"


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.subaru.config_flow.validate_input",
        return_value=mock_coro(
            {
                "title": TEST_TITLE,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_PIN: TEST_PIN,
                CONF_DEVICE_ID: "test",
            }
        ),
    ), patch(
        "homeassistant.components.subaru.async_setup", return_value=mock_coro(True)
    ) as mock_setup, patch(
        "homeassistant.components.subaru.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_PIN: TEST_PIN,
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == TEST_TITLE
    assert result2["data"] == {
        "title": TEST_TITLE,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PIN: TEST_PIN,
        CONF_DEVICE_ID: "test",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.subaru.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_PIN: TEST_PIN,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_credentials"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.subaru.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_PIN: TEST_PIN,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "connection_error"}
