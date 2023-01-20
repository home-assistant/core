"""Test the Thread config flow."""
from unittest.mock import patch

from homeassistant.components import thread
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


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


async def test_config_flow_single_entry(hass: HomeAssistant) -> None:
    """Test only a single entry is allowed."""
    config_entry = MockConfigEntry(
        data={},
        domain=thread.DOMAIN,
        options={},
        title="Thread",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_yellow.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            thread.DOMAIN, context={"source": "import"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    mock_setup_entry.assert_not_called()
