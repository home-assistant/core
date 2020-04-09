"""Test Mikrotik setup process."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.components import mikrotik
from homeassistant.setup import async_setup_component

from . import ENTRY_CONFIG, OLD_ENTRY_CONFIG
from .test_hub import setup_mikrotik_integration

from tests.common import mock_coro


async def test_setup_with_no_config(hass, api):
    """Test that we do not discover anything or try to set up a hub."""
    assert await async_setup_component(hass, mikrotik.DOMAIN, {}) is True
    assert mikrotik.DOMAIN not in hass.data


async def test_successful_config_entry(hass, api):
    """Test config entry successful setup."""
    await setup_mikrotik_integration(hass)
    assert hass.data[mikrotik.DOMAIN]


async def test_old_config_entry(hass, api):
    """Test converting  old config entry successfully."""
    await setup_mikrotik_integration(hass, config_entry=OLD_ENTRY_CONFIG)
    assert hass.data[mikrotik.DOMAIN]


async def test_config_fail_setup(hass, api):
    """Test that a failed setup will not store the config."""
    with patch.object(mikrotik, "Mikrotik") as mock_integration:
        mock_integration.return_value.async_setup.return_value = mock_coro(False)
        await setup_mikrotik_integration(hass)

    assert mikrotik.DOMAIN not in hass.data


async def test_successfull_integration_setup(hass, api):
    """Test successful setup."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ) as forward_entry_setup:
        mikrotik_mock = await setup_mikrotik_integration(hass)

        assert forward_entry_setup.mock_calls[0][1] == (
            mikrotik_mock.config_entry,
            "device_tracker",
        )

        assert len(mikrotik_mock.hubs) == len(ENTRY_CONFIG[mikrotik.CONF_HUBS])
        assert mikrotik_mock.option_detection_time == timedelta(
            seconds=mikrotik.DEFAULT_DETECTION_TIME
        )
        assert (
            mikrotik_mock.signal_update
            == f"{mikrotik.DOMAIN}-{mikrotik_mock.config_entry.entry_id}-data-updated"
        )


async def test_unload_entry(hass, api):
    """Test being able to unload an entry."""
    mikrotik_mock = await setup_mikrotik_integration(hass)
    assert hass.data[mikrotik.DOMAIN]

    assert await mikrotik.async_unload_entry(hass, mikrotik_mock.config_entry)
    assert not hass.data[mikrotik.DOMAIN]
