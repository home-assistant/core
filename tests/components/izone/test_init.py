"""Tests for iZone integration setup and unload."""

from unittest.mock import patch

from homeassistant.components.izone import discovery as izone_discovery
from homeassistant.components.izone.const import DATA_DISCOVERY_SERVICE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import async_install_discovery_service, create_mock_controller

from tests.common import MockConfigEntry


async def test_unload_last_entry_does_not_stop_discovery_when_controller_on_lan(
    hass: HomeAssistant,
) -> None:
    """Unload leaves discovery running so controllers stay discoverable on the LAN."""
    controller = create_mock_controller("000000001", "192.0.2.1")
    await async_install_discovery_service(hass, controller)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={},
        version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.climate.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert DATA_DISCOVERY_SERVICE in hass.data

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert DATA_DISCOVERY_SERVICE in hass.data


async def test_setup_entry_after_unload_reuses_discovery(
    hass: HomeAssistant,
) -> None:
    """A new entry setup reuses the discovery service left running after unload."""
    controller = create_mock_controller("000000001", "192.0.2.1")
    service = await async_install_discovery_service(hass, controller)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={},
        version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.climate.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert DATA_DISCOVERY_SERVICE in hass.data

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
    assert hass.data[DATA_DISCOVERY_SERVICE] is service


async def test_idle_stop_after_unload_when_no_controllers(
    hass: HomeAssistant,
) -> None:
    """Idle-stop clears discovery once the entry is gone and no controllers remain."""
    controller = create_mock_controller("000000001", "192.0.2.1")
    service = await async_install_discovery_service(hass, controller)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={},
        version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.climate.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    service.pi_disco.controllers.clear()

    await izone_discovery.async_maybe_stop_discovery_service(hass)
    await hass.async_block_till_done()

    assert DATA_DISCOVERY_SERVICE not in hass.data
