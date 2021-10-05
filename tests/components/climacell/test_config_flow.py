"""Test the ClimaCell config flow."""
import logging

from homeassistant import data_entry_flow
from homeassistant.components.climacell.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def test_user_flow_minimum_fields(hass: HomeAssistant) -> None:
    """Test user config flow with minimum fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "tomorrowio"
