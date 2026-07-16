"""Tests for iZone integration setup and unload."""

import asyncio
from unittest.mock import patch

from homeassistant.components.izone import discovery as izone_discovery
from homeassistant.components.izone.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import async_install_discovery_service, create_mock_controller

from tests.common import MockConfigEntry


async def test_unload_last_entry_does_not_stop_discovery_when_controller_on_lan(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unload leaves discovery running so controllers stay discoverable on the LAN."""
    controller = create_mock_controller("000000001", "192.0.2.1")
    service = await async_install_discovery_service(hass, controller)

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.climate.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    service.pi_disco.close.assert_not_awaited()
    assert service.remove_stop_listener is not None


async def test_setup_entry_after_unload_reuses_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A new entry setup reuses the discovery service left running after unload."""
    controller = create_mock_controller("000000001", "192.0.2.1")
    service = await async_install_discovery_service(hass, controller)

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.climate.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    service.pi_disco.close.assert_not_awaited()

    second = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000002",
        data={},
        version=2,
    )
    second.add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.climate.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()

    assert second.state is ConfigEntryState.LOADED
    assert await izone_discovery.async_start_discovery_service(hass) is service
    service.pi_disco.start_discovery.assert_awaited_once()
    service.pi_disco.close.assert_not_awaited()


async def test_idle_stop_after_unload_when_no_controllers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Idle-stop clears discovery once the entry is gone and no controllers remain."""
    with patch(
        "homeassistant.components.izone.discovery.DISCOVERY_IDLE_SECONDS",
        0,
    ):
        controller = create_mock_controller("000000001", "192.0.2.1")
        service = await async_install_discovery_service(hass, controller)

        mock_config_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.izone.climate.async_setup_entry",
            return_value=True,
        ):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.config_entries.async_remove(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        service.pi_disco.controllers.clear()

        # call_later(0) → maybe_stop task; drain until discovery closes.
        for _ in range(5):
            if service.remove_stop_listener is None:
                break
            await asyncio.sleep(0)
            await hass.async_block_till_done()

    service.pi_disco.close.assert_awaited_once()
    assert service.remove_stop_listener is None
