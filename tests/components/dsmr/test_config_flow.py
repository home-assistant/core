"""Test the DSMR config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.dsmr import DOMAIN

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_import_usb(hass):
    """Test we can import."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "precision": 4,
        "reconnect_interval": 30,
    }

    with patch("homeassistant.components.dsmr.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=entry_data,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "/dev/ttyUSB0"
    assert result["data"] == entry_data


async def test_import_network(hass):
    """Test we can import from network."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry_data = {
        "host": "localhost",
        "port": "1234",
        "dsmr_version": "2.2",
        "precision": 4,
        "reconnect_interval": 30,
    }

    with patch("homeassistant.components.dsmr.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=entry_data,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "localhost:1234"
    assert result["data"] == entry_data


async def test_import_update(hass):
    """Test we can import."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "precision": 4,
        "reconnect_interval": 30,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=entry_data,
        unique_id="/dev/ttyUSB0",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=entry_data,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
