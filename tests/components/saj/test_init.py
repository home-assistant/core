"""Tests for safe mode integration."""
from unittest.mock import AsyncMock, patch

from homeassistant.components.saj import (
    DOMAIN,
    SAJDataUpdateCoordinator,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry


async def test_setup_and_unload(hass):
    """Test entry setup and unload."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "",
            CONF_TYPE: "wifi",
            CONF_HOST: "192.168.0.32",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin",
        },
    )
    with patch(
        "homeassistant.components.saj.coordinator._init_pysaj", return_value=AsyncMock()
    ):
        assert await async_setup_entry(hass, config_entry)
        inverter = hass.data[DOMAIN][config_entry.entry_id]
        assert isinstance(inverter, SAJDataUpdateCoordinator)

        assert await async_unload_entry(hass, config_entry)
        assert hass.data[DOMAIN] == {}
