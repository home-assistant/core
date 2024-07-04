"""Test deCONZ component setup process."""

import asyncio
from collections.abc import Callable
from unittest.mock import patch

from homeassistant.components.deconz import (
    DeconzHub,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.deconz.const import DOMAIN as DECONZ_DOMAIN
from homeassistant.components.deconz.errors import AuthenticationRequired, CannotConnect
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

from tests.test_util.aiohttp import AiohttpClientMocker

ENTRY1_HOST = "1.2.3.4"
ENTRY1_PORT = 80
ENTRY1_API_KEY = "1234567890ABCDEF"
ENTRY1_BRIDGEID = "12345ABC"
ENTRY1_UUID = "456DEF"

ENTRY2_HOST = "2.3.4.5"
ENTRY2_PORT = 80
ENTRY2_API_KEY = "1234567890ABCDEF"
ENTRY2_BRIDGEID = "23456DEF"
ENTRY2_UUID = "789ACE"


async def setup_entry(hass, entry):
    """Test that setup entry works."""
    with (
        patch.object(DeconzHub, "async_setup", return_value=True),
        patch.object(DeconzHub, "async_update_device_registry", return_value=True),
    ):
        assert await async_setup_entry(hass, entry) is True


async def test_setup_entry_successful(
    hass: HomeAssistant, config_entry_setup: ConfigEntry
) -> None:
    """Test setup entry is successful."""
    assert hass.data[DECONZ_DOMAIN]
    assert config_entry_setup.entry_id in hass.data[DECONZ_DOMAIN]
    assert hass.data[DECONZ_DOMAIN][config_entry_setup.entry_id].master


async def test_setup_entry_fails_config_entry_not_ready(
    hass: HomeAssistant, config_entry_factory: Callable[[], ConfigEntry]
) -> None:
    """Failed authentication trigger a reauthentication flow."""
    with patch(
        "homeassistant.components.deconz.get_deconz_api",
        side_effect=CannotConnect,
    ):
        await config_entry_factory()

    assert hass.data[DECONZ_DOMAIN] == {}


async def test_setup_entry_fails_trigger_reauth_flow(
    hass: HomeAssistant, config_entry_factory: Callable[[], ConfigEntry]
) -> None:
    """Failed authentication trigger a reauthentication flow."""
    with (
        patch(
            "homeassistant.components.deconz.get_deconz_api",
            side_effect=AuthenticationRequired,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_flow_init,
    ):
        await config_entry_factory()
        mock_flow_init.assert_called_once()

    assert hass.data[DECONZ_DOMAIN] == {}


async def test_setup_entry_multiple_gateways(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: ConfigEntry,
) -> None:
    """Test setup entry is successful with multiple gateways."""
    aioclient_mock.clear_requests()

    data = {"config": {"bridgeid": "01234E56789B"}}
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry2 = await setup_deconz_integration(
            hass,
            aioclient_mock,
            entry_id="2",
            unique_id="01234E56789B",
        )

    assert len(hass.data[DECONZ_DOMAIN]) == 2
    assert hass.data[DECONZ_DOMAIN][config_entry_setup.entry_id].master
    assert not hass.data[DECONZ_DOMAIN][config_entry2.entry_id].master


async def test_unload_entry(
    hass: HomeAssistant, config_entry_setup: ConfigEntry
) -> None:
    """Test being able to unload an entry."""
    assert hass.data[DECONZ_DOMAIN]

    assert await async_unload_entry(hass, config_entry_setup)
    assert not hass.data[DECONZ_DOMAIN]


async def test_unload_entry_multiple_gateways(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: ConfigEntry,
) -> None:
    """Test being able to unload an entry and master gateway gets moved."""
    aioclient_mock.clear_requests()

    data = {"config": {"bridgeid": "01234E56789B"}}
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry2 = await setup_deconz_integration(
            hass,
            aioclient_mock,
            entry_id="2",
            unique_id="01234E56789B",
        )

    assert len(hass.data[DECONZ_DOMAIN]) == 2

    assert await async_unload_entry(hass, config_entry_setup)

    assert len(hass.data[DECONZ_DOMAIN]) == 1
    assert hass.data[DECONZ_DOMAIN][config_entry2.entry_id].master


async def test_unload_entry_multiple_gateways_parallel(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: ConfigEntry,
) -> None:
    """Test race condition when unloading multiple config entries in parallel."""
    aioclient_mock.clear_requests()

    data = {"config": {"bridgeid": "01234E56789B"}}
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry2 = await setup_deconz_integration(
            hass,
            aioclient_mock,
            entry_id="2",
            unique_id="01234E56789B",
        )

    assert len(hass.data[DECONZ_DOMAIN]) == 2

    await asyncio.gather(
        hass.config_entries.async_unload(config_entry_setup.entry_id),
        hass.config_entries.async_unload(config_entry2.entry_id),
    )

    assert len(hass.data[DECONZ_DOMAIN]) == 0
