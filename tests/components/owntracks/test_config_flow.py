"""Tests for OwnTracks config flow."""
from unittest.mock import patch

from homeassistant.setup import async_setup_component
from tests.common import mock_coro


async def test_config_flow_import(hass):
    """Test that we automatically create a config flow."""
    assert not hass.config_entries.async_entries("owntracks")
    assert await async_setup_component(hass, "owntracks", {"owntracks": {}})
    await hass.async_block_till_done()
    assert hass.config_entries.async_entries("owntracks")


async def test_config_flow_unload(hass):
    """Test unloading a config flow."""
    with patch(
        "homeassistant.config_entries.ConfigEntries" ".async_forward_entry_setup"
    ) as mock_forward:
        result = await hass.config_entries.flow.async_init(
            "owntracks", context={"source": "import"}, data={}
        )

    assert len(mock_forward.mock_calls) == 1
    entry = result["result"]

    assert mock_forward.mock_calls[0][1][0] is entry
    assert mock_forward.mock_calls[0][1][1] == "device_tracker"
    assert entry.data["webhook_id"] in hass.data["webhook"]

    with patch(
        "homeassistant.config_entries.ConfigEntries" ".async_forward_entry_unload",
        return_value=mock_coro(),
    ) as mock_unload:
        assert await hass.config_entries.async_unload(entry.entry_id)

    assert len(mock_unload.mock_calls) == 1
    assert mock_forward.mock_calls[0][1][0] is entry
    assert mock_forward.mock_calls[0][1][1] == "device_tracker"
    assert entry.data["webhook_id"] not in hass.data["webhook"]


async def test_with_cloud_sub(hass):
    """Test creating a config flow while subscribed."""
    with patch(
        "homeassistant.components.cloud.async_active_subscription", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_create_cloudhook",
        return_value=mock_coro("https://hooks.nabu.casa/ABCD"),
    ):
        result = await hass.config_entries.flow.async_init(
            "owntracks", context={"source": "user"}, data={}
        )

    entry = result["result"]
    assert entry.data["cloudhook"]
    assert (
        result["description_placeholders"]["webhook_url"]
        == "https://hooks.nabu.casa/ABCD"
    )
