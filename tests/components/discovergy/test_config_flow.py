"""Test the Discovergy config flow."""
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from pydiscovergy.error import HTTPError, InvalidLogin
from pydiscovergy.models import ConsumerToken, RequestToken

from homeassistant import config_entries, setup
from homeassistant.components.discovergy.const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_SECRET,
    CONF_CONSUMER_KEY,
    CONF_CONSUMER_SECRET,
    DOMAIN,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


def get_discovergy_mock() -> MagicMock:
    """Return a MagicMock Discovergy instance for testing."""
    discovergy_mock = MagicMock()
    type(discovergy_mock).login = AsyncMock(
        return_value=RequestToken("rq-test-token", "rq-test-token-secret")
    )
    type(discovergy_mock).consumer_token = PropertyMock(
        return_value=ConsumerToken("test-key", "test-secret")
    )
    type(discovergy_mock).email = PropertyMock(return_value="test@example.com")

    return discovergy_mock


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch("pydiscovergy.Discovergy", return_value=get_discovergy_mock(),), patch(
        "homeassistant.components.discovergy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "test@example.com"
    assert result2["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test-password",
        CONF_ACCESS_TOKEN: "rq-test-token",
        CONF_ACCESS_TOKEN_SECRET: "rq-test-token-secret",
        CONF_CONSUMER_KEY: "test-key",
        CONF_CONSUMER_SECRET: "test-secret",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pydiscovergy.Discovergy.login",
        side_effect=InvalidLogin,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pydiscovergy.Discovergy.login",
        side_effect=HTTPError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}
