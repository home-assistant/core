"""Test the hausbus config flow."""
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.hausbus.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .helpers import create_configuration

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form_user(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form and create hausbus configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await create_configuration(hass, result)

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Haus-Bus"
    assert result2["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1
