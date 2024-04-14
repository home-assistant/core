"""Test websocket commands for the panel."""

from unittest.mock import patch

from homeassistant.components import dynalite
from homeassistant.components.cover import DEVICE_CLASSES
from homeassistant.const import CONF_PORT

from tests.common import MockConfigEntry


async def test_get_config(hass, hass_ws_client):
    """Get the config via websocket."""
    host = "1.2.3.4"
    port = 765

    entry = MockConfigEntry(
        domain=dynalite.DOMAIN,
        data={dynalite.CONF_HOST: host, CONF_PORT: port},
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 24,
            "type": "dynalite/get-config",
        }
    )

    msg = await client.receive_json()
    assert msg["success"]
    result = msg["result"]
    entry_id = entry.entry_id
    assert result == {
        "config": {entry_id: {dynalite.CONF_HOST: host, CONF_PORT: port}},
        "default": {
            "DEFAULT_NAME": dynalite.const.DEFAULT_NAME,
            "DEFAULT_PORT": dynalite.const.DEFAULT_PORT,
            "DEVICE_CLASSES": DEVICE_CLASSES,
        },
    }


async def test_save_config(hass, hass_ws_client):
    """Save the config via websocket."""
    host1 = "1.2.3.4"
    port1 = 765
    host2 = "5.6.7.8"
    port2 = 432
    host3 = "5.3.2.1"
    port3 = 543

    entry1 = MockConfigEntry(
        domain=dynalite.DOMAIN,
        data={dynalite.CONF_HOST: host1, CONF_PORT: port1},
    )
    entry1.add_to_hass(hass)
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry1.entry_id)
        await hass.async_block_till_done()
    entry2 = MockConfigEntry(
        domain=dynalite.DOMAIN,
        data={dynalite.CONF_HOST: host2, CONF_PORT: port2},
    )
    entry2.add_to_hass(hass)
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry2.entry_id)
        await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 24,
            "type": "dynalite/save-config",
            "entry_id": entry2.entry_id,
            "config": {dynalite.CONF_HOST: host3, CONF_PORT: port3},
        }
    )

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {}

    existing_entry = hass.config_entries.async_get_entry(entry1.entry_id)
    assert existing_entry.data == {dynalite.CONF_HOST: host1, CONF_PORT: port1}
    modified_entry = hass.config_entries.async_get_entry(entry2.entry_id)
    assert modified_entry.data[dynalite.CONF_HOST] == host3
    assert modified_entry.data[CONF_PORT] == port3


async def test_save_config_invalid_entry(hass, hass_ws_client):
    """Try to update nonexistent entry."""
    host1 = "1.2.3.4"
    port1 = 765
    host2 = "5.6.7.8"
    port2 = 432

    entry = MockConfigEntry(
        domain=dynalite.DOMAIN,
        data={dynalite.CONF_HOST: host1, CONF_PORT: port1},
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 24,
            "type": "dynalite/save-config",
            "entry_id": "junk",
            "config": {dynalite.CONF_HOST: host2, CONF_PORT: port2},
        }
    )

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"error": True}

    existing_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert existing_entry.data == {dynalite.CONF_HOST: host1, CONF_PORT: port1}
