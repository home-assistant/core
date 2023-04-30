"""Test Lastfm config flow."""

from pylast import WSError

from homeassistant import data_entry_flow
from homeassistant.components.lastfm.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant

from . import CONF_DATA, patch_fetch_user, patch_setup_entry


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test user initialized flow."""
    with patch_fetch_user(), patch_setup_entry():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["data"] == CONF_DATA


async def test_flow_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test user initialized flow with invalid authentication."""
    with patch_fetch_user() as servicemock:
        servicemock.side_effect = WSError(
            "network",
            "status",
            "Invalid API key - You must be granted a valid key by last.fm",
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "invalid_auth"


async def test_flow_user_invalid_username(hass: HomeAssistant) -> None:
    """Test user initialized flow with invalid username."""
    with patch_fetch_user() as servicemock:
        servicemock.side_effect = WSError("network", "status", "User not found")
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "invalid_account"


async def test_flow_user_unknown(hass: HomeAssistant) -> None:
    """Test user initialized flow with unknown error."""
    with patch_fetch_user() as servicemock:
        servicemock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "unknown"


async def test_flow_user_unknown_lastfm(hass: HomeAssistant) -> None:
    """Test user initialized flow with unknown error from lastfm."""
    with patch_fetch_user() as servicemock:
        servicemock.side_effect = WSError("network", "status", "Something strange")
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "unknown"


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test user initialized flow with unknown error from lastfm."""
    with patch_fetch_user():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=CONF_DATA
        )
        await hass.async_block_till_done()
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "LastFM"
    assert result["data"] == {"api_key": "asdasdasdasdasd", "users": ["testaccount1"]}
