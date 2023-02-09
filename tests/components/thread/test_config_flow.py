"""Test the Thread config flow."""
from unittest.mock import patch

from homeassistant.components import thread
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_import(hass: HomeAssistant) -> None:
    """Test the import flow."""
    with patch(
        "homeassistant.components.thread.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            thread.DOMAIN, context={"source": "import"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Thread"
    assert result["data"] == {}
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(thread.DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {}
    assert config_entry.title == "Thread"
    assert config_entry.unique_id is None
