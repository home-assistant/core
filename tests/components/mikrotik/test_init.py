"""Test Mikrotik setup process."""
from unittest.mock import Mock, patch

from homeassistant.components import mikrotik
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_coro

MOCK_ENTRY = MockConfigEntry(
    domain=mikrotik.DOMAIN,
    data={
        mikrotik.CONF_NAME: "Mikrotik",
        mikrotik.CONF_HOST: "0.0.0.0",
        mikrotik.CONF_USERNAME: "user",
        mikrotik.CONF_PASSWORD: "pass",
        mikrotik.CONF_PORT: 8278,
        mikrotik.CONF_VERIFY_SSL: False,
    },
)


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a hub."""
    assert await async_setup_component(hass, mikrotik.DOMAIN, {}) is True
    assert mikrotik.DOMAIN not in hass.data


async def test_successful_config_entry(hass):
    """Test config entry successfull setup."""
    entry = MOCK_ENTRY
    entry.add_to_hass(hass)
    mock_registry = Mock()

    with patch.object(mikrotik, "MikrotikHub") as mock_hub, patch(
        "homeassistant.helpers.device_registry.async_get_registry",
        return_value=mock_coro(mock_registry),
    ):
        mock_hub.return_value.async_setup.return_value = mock_coro(True)
        mock_hub.return_value.serial_num = "12345678"
        mock_hub.return_value.model = "RB750"
        mock_hub.return_value.hostname = "mikrotik"
        mock_hub.return_value.firmware = "3.65"
        assert await mikrotik.async_setup_entry(hass, entry) is True

    assert len(mock_hub.mock_calls) == 2
    p_hass, p_entry = mock_hub.mock_calls[0][1]

    assert p_hass is hass
    assert p_entry is entry

    assert len(mock_registry.mock_calls) == 1
    assert mock_registry.mock_calls[0][2] == {
        "config_entry_id": entry.entry_id,
        "connections": {("mikrotik", "12345678")},
        "manufacturer": mikrotik.ATTR_MANUFACTURER,
        "model": "RB750",
        "name": "mikrotik",
        "sw_version": "3.65",
    }


async def test_hub_fail_setup(hass):
    """Test that a failed setup still stores hub."""
    entry = MOCK_ENTRY
    entry.add_to_hass(hass)

    with patch.object(mikrotik, "MikrotikHub") as mock_hub:
        mock_hub.return_value.async_setup.return_value = mock_coro(False)
        assert await mikrotik.async_setup_entry(hass, entry) is False

    assert entry.entry_id in hass.data[mikrotik.DOMAIN]


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    entry = MOCK_ENTRY
    entry.add_to_hass(hass)

    with patch.object(mikrotik, "MikrotikHub") as mock_hub, patch(
        "homeassistant.helpers.device_registry.async_get_registry",
        return_value=mock_coro(Mock()),
    ):
        mock_hub.return_value.async_setup.return_value = mock_coro(True)
        mock_hub.return_value.serial_num = "12345678"
        mock_hub.return_value.model = "RB750"
        mock_hub.return_value.hostname = "mikrotik"
        mock_hub.return_value.firmware = "3.65"
        assert await mikrotik.async_setup_entry(hass, entry) is True

    assert len(mock_hub.return_value.mock_calls) == 1

    assert await mikrotik.async_unload_entry(hass, entry)
    assert entry.entry_id not in hass.data[mikrotik.DOMAIN]
