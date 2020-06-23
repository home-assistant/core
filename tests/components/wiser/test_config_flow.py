"""Test the Wiser Heating Component for Home Assistant config flow."""
from wiserHeatingAPI.wiserHub import (
    WiserHubAuthenticationException,
    WiserHubTimeoutException,
)

from homeassistant import config_entries, setup
from homeassistant.components.wiser.const import DOMAIN

from tests.async_mock import MagicMock, patch

MOCK_CREDENTIALS = {"host": "1.1.1.1", "password": "test-password"}
MOCK_HUBNAME = "WISER12345678"


def _get_mock_wiser_api(getWiserHubName=None):
    mock_wiser = MagicMock()
    if isinstance(getWiserHubName, Exception):
        type(mock_wiser).getWiserHubName = MagicMock(side_effect=getWiserHubName)
    else:
        type(mock_wiser).getWiserHubName = MagicMock(return_value=getWiserHubName)
    return mock_wiser


async def test_form(hass):
    """Test we can setup though the user path."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_wiser_api = _get_mock_wiser_api(getWiserHubName=MOCK_HUBNAME)

    with patch(
        "homeassistant.components.wiser.config_flow.wiserHub",
        return_value=mock_wiser_api,
    ), patch(
        "homeassistant.components.wiser.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.wiser.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CREDENTIALS,
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == MOCK_HUBNAME

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.wiser.config_flow.wiserHub",
        side_effect=WiserHubAuthenticationException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CREDENTIALS,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "auth_failure"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.wiser.config_flow.wiserHub",
        side_effect=WiserHubTimeoutException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CREDENTIALS,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "timeout_error"}
