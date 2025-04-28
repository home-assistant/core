"""Test the init file for the Insteon component."""

from unittest.mock import patch

import pytest

from homeassistant.components import insteon
from homeassistant.components.insteon.const import CONF_DEV_PATH, DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import MOCK_USER_INPUT_PLM
from .mock_devices import MockDevices

from tests.common import MockConfigEntry


async def mock_successful_connection(*args, **kwargs):
    """Return a successful connection."""
    return True


async def mock_failed_connection(*args, **kwargs):
    """Return a failed connection."""
    raise ConnectionError("Connection failed")


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up the entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)

    with (
        patch.object(insteon, "async_connect", new=mock_successful_connection),
        patch.object(insteon, "async_close") as mock_close,
        patch.object(insteon, "devices", new=MockDevices()),
    ):
        assert await async_setup_component(
            hass,
            insteon.DOMAIN,
            {},
        )
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        assert insteon.devices.async_save.call_count == 1
        assert mock_close.called


async def test_setup_entry_failed_connection(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setting up the entry with a failed connection."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)

    with (
        patch.object(insteon, "async_connect", new=mock_failed_connection),
        patch.object(insteon, "devices", new=MockDevices(connected=False)),
    ):
        assert await async_setup_component(
            hass,
            insteon.DOMAIN,
            {},
        )
        assert "Could not connect to Insteon modem" in caplog.text


async def test_import_frontend_dev_url(hass: HomeAssistant) -> None:
    """Test importing a dev_url config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_USER_INPUT_PLM, options={CONF_DEV_PATH: "/some/path"}
    )
    config_entry.add_to_hass(hass)

    with (
        patch.object(insteon, "async_connect", new=mock_successful_connection),
        patch.object(insteon, "async_close") as mock_close,
        patch.object(insteon, "devices", new=MockDevices()),
    ):
        assert await async_setup_component(
            hass,
            insteon.DOMAIN,
            {},
        )
        await hass.async_block_till_done()
        assert hass.data[DOMAIN][CONF_DEV_PATH] == "/some/path"
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        assert insteon.devices.async_save.call_count == 1
        assert mock_close.called
