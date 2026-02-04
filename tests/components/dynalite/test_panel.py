"""Test websocket commands for the panel."""

from unittest.mock import patch

from homeassistant import setup
from homeassistant.components import dynalite, frontend
from homeassistant.components.cover import DEVICE_CLASSES
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_get_config(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Get the config via websocket."""
    host = "1.2.3.4"
    port = 765

    entry = MockConfigEntry(
        domain=dynalite.DOMAIN,
        data={CONF_HOST: host, CONF_PORT: port},
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
        "config": {entry_id: {CONF_HOST: host, CONF_PORT: port}},
        "default": {
            "DEFAULT_NAME": dynalite.const.DEFAULT_NAME,
            "DEFAULT_PORT": dynalite.const.DEFAULT_PORT,
            "DEVICE_CLASSES": DEVICE_CLASSES,
        },
    }


async def test_save_config(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Save the config via websocket."""
    host1 = "1.2.3.4"
    port1 = 765
    host2 = "5.6.7.8"
    port2 = 432
    host3 = "5.3.2.1"
    port3 = 543

    entry1 = MockConfigEntry(
        domain=dynalite.DOMAIN,
        data={CONF_HOST: host1, CONF_PORT: port1},
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
        data={CONF_HOST: host2, CONF_PORT: port2},
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
            "config": {CONF_HOST: host3, CONF_PORT: port3},
        }
    )

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {}

    existing_entry = hass.config_entries.async_get_entry(entry1.entry_id)
    assert existing_entry.data == {CONF_HOST: host1, CONF_PORT: port1}
    modified_entry = hass.config_entries.async_get_entry(entry2.entry_id)
    assert modified_entry.data[CONF_HOST] == host3
    assert modified_entry.data[CONF_PORT] == port3


async def test_save_config_invalid_entry(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Try to update nonexistent entry."""
    host1 = "1.2.3.4"
    port1 = 765
    host2 = "5.6.7.8"
    port2 = 432

    entry = MockConfigEntry(
        domain=dynalite.DOMAIN,
        data={CONF_HOST: host1, CONF_PORT: port1},
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
            "config": {CONF_HOST: host2, CONF_PORT: port2},
        }
    )

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"error": True}

    existing_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert existing_entry.data == {CONF_HOST: host1, CONF_PORT: port1}


async def test_panel_registration(hass: HomeAssistant) -> None:
    """Test that the dynalite panel is registered with correct module URL format."""
    with (
        patch(
            "homeassistant.components.dynalite.panel.locate_dir",
            return_value="/mock/path",
        ),
        patch(
            "homeassistant.components.dynalite.panel.get_build_id", return_value="1.2.3"
        ),
    ):
        result = await setup.async_setup_component(hass, dynalite.DOMAIN, {})
        assert result
        await hass.async_block_till_done()

    panels = hass.data.get(frontend.DATA_PANELS, {})
    assert dynalite.DOMAIN in panels

    panel = panels[dynalite.DOMAIN]

    # Verify the panel configuration
    assert panel.frontend_url_path == dynalite.DOMAIN
    assert panel.config_panel_domain == dynalite.DOMAIN
    assert panel.require_admin is True

    # Verify the module_url uses dash format (entrypoint-1.2.3.js) not dot format
    module_url = panel.config["_panel_custom"]["module_url"]
    assert module_url == "/dynalite_static/entrypoint-1.2.3.js"
    assert "entrypoint.1.2.3.js" not in module_url  # Ensure wrong format is not used
