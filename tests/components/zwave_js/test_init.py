"""Test the Z-Wave JS init module."""
from homeassistant.config_entries import ENTRY_STATE_LOADED, ENTRY_STATE_NOT_LOADED


async def test_entry_setup_unload(hass, client, integration):
    """Test the integration set up and unload."""
    entry = integration

    assert client.connect.call_count == 1
    assert client.register_on_initialized.call_count == 1
    assert client.register_on_disconnect.call_count == 1
    assert client.register_on_connect.call_count == 1
    assert entry.state == ENTRY_STATE_LOADED

    await hass.config_entries.async_unload(entry.entry_id)

    assert client.disconnect.call_count == 1
    assert client.register_on_initialized.return_value.call_count == 1
    assert client.register_on_disconnect.return_value.call_count == 1
    assert client.register_on_connect.return_value.call_count == 1
    assert entry.state == ENTRY_STATE_NOT_LOADED
