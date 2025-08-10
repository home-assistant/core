"""Test config flow."""

from homeassistant.components.shopping_list.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_import(hass: HomeAssistant) -> None:
    """Test entry will be imported."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user(hass: HomeAssistant) -> None:
    """Test we can start a config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_confirm(hass: HomeAssistant) -> None:
    """Test we can finish a config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {}


async def test_onboarding_flow(hass: HomeAssistant) -> None:
    """Test the onboarding configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "onboarding"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Shopping list"
    assert result["data"] == {}
