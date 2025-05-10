"""Test the Telegram config flow."""

from homeassistant.components.telegram import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import setup_dependencies


async def test_async_step_user(hass: HomeAssistant) -> None:
    """Test config flow form display."""

    await setup_dependencies(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
