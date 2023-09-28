"""Test initialization of squeezebox component."""

from homeassistant.components.squeezebox import async_migrate_entry
from homeassistant.components.squeezebox.const import CONF_HTTPS, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

HOST = "192.168.1.2"
PORT = 9000
USERNAME = "user1"
PASSWORD = "password1"


async def test_async_migrate_entry(hass: HomeAssistant) -> None:
    """Test async_migrate_entry for the Logitech Squeezebox integration."""
    entry_data = {
        CONF_HOST: "192.168.1.2",
        CONF_PORT: 9000,
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
        "version": 1,
    }
    config_entry = MockConfigEntry(
        title="192.168.1.2",
        source="user",
        version=1,
        domain=DOMAIN,
        data=entry_data,
        entry_id="test_entry_id",
    )
    config_entry.add_to_hass(hass)

    assert config_entry.version == 1
    assert CONF_HTTPS not in config_entry.data

    result = await async_migrate_entry(hass, config_entry)

    assert result
    assert config_entry.version == 2
    assert CONF_HTTPS in config_entry.data
    assert config_entry.data[CONF_HOST] == HOST
    assert config_entry.data[CONF_PORT] == PORT
    assert config_entry.data[CONF_USERNAME] == USERNAME
    assert config_entry.data[CONF_PASSWORD] == PASSWORD
    assert config_entry.data[CONF_HTTPS] is False
