"""Test the Coronavirus config flow."""
from unittest.mock import MagicMock, patch

from aiohttp import ClientError

from homeassistant import config_entries, setup
from homeassistant.components.coronavirus.const import DOMAIN, OPTION_WORLDWIDE
from homeassistant.core import HomeAssistant


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"country": OPTION_WORLDWIDE},
    )
    assert result2["type"] == "create_entry"
    assert result2["title"] == "Worldwide"
    assert result2["result"].unique_id == OPTION_WORLDWIDE
    assert result2["data"] == {
        "country": OPTION_WORLDWIDE,
    }
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 4


@patch(
    "coronavirus.get_cases",
    side_effect=ClientError,
)
async def test_abort_on_connection_error(
    mock_get_cases: MagicMock, hass: HomeAssistant
) -> None:
    """Test we abort on connection error."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert "type" in result
    assert result["type"] == "abort"
    assert "reason" in result
    assert result["reason"] == "cannot_connect"
