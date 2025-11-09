"""Test the Photo Frame config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.photo_frame.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {}

    with patch(
        "homeassistant.components.photo_frame.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Random Photo",
                "media": {"media_content_id": "1234", "media_content_type": ""},
            },
        )
        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Random Photo"
    assert result.get("data") == {
        "name": "Random Photo",
        "media": {"media_content_id": "1234", "media_content_type": ""},
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {
        "name": "Random Photo",
        "media": {"media_content_id": "1234", "media_content_type": ""},
    }
    assert config_entry.title == "Random Photo"
