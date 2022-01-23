"""Test the bemfa config flow."""
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.bemfa.const import CONF_UID, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_FORM


async def test_user_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    http_api = MagicMock()
    type(http_api).async_fetch_all_topics = AsyncMock(return_value={})
    with patch(
        "homeassistant.components.bemfa.config_flow.BemfaHttp",
        return_value=http_api,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_UID: "11111111112222222222333333333344",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] is None
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_form_invalid_uid(hass: HomeAssistant) -> None:
    """Test we handle invalid uid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_UID: "invalid_uid",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_uid"}
