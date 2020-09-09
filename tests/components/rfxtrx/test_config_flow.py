"""Test the Tado config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.rfxtrx import DOMAIN

from tests.common import MockConfigEntry


async def test_import(hass):
    """Test we can import."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={"host": None, "port": None, "device": "/dev/tty123", "debug": False},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "RFXTRX"
    assert result["data"] == {
        "host": None,
        "port": None,
        "device": "/dev/tty123",
        "debug": False,
    }


async def test_import_update(hass):
    """Test we can import."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": None, "port": None, "device": "/dev/tty123", "debug": False},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={"host": None, "port": None, "device": "/dev/tty123", "debug": True},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert entry.data["debug"]
