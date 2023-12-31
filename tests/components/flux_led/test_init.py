"""Tests for the flux_led component."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import flux_led
from homeassistant.components.flux_led.const import (
    CONF_REMOTE_ACCESS_ENABLED,
    CONF_REMOTE_ACCESS_HOST,
    CONF_REMOTE_ACCESS_PORT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    CONF_HOST,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import (
    DEFAULT_ENTRY_TITLE,
    DHCP_DISCOVERY,
    FLUX_DISCOVERY,
    FLUX_DISCOVERY_PARTIAL,
    IP_ADDRESS,
    MAC_ADDRESS,
    MAC_ADDRESS_ONE_OFF,
    _mocked_bulb,
    _patch_discovery,
    _patch_wifibulb,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_single_broadcast_address")
async def test_configuring_flux_led_causes_discovery(hass: HomeAssistant) -> None:
    """Test that specifying empty config does discovery."""
    with patch(
        "homeassistant.components.flux_led.discovery.AIOBulbScanner.async_scan"
    ) as scan, patch(
        "homeassistant.components.flux_led.discovery.AIOBulbScanner.getBulbInfo"
    ) as discover:
        discover.return_value = [FLUX_DISCOVERY]
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

        assert len(scan.mock_calls) == 1
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert len(scan.mock_calls) == 2

        async_fire_time_changed(hass, utcnow() + flux_led.DISCOVERY_INTERVAL)
        await hass.async_block_till_done()
        assert len(scan.mock_calls) == 3


@pytest.mark.usefixtures("mock_multiple_broadcast_addresses")
async def test_configuring_flux_led_causes_discovery_multiple_addresses(
    hass: HomeAssistant,
) -> None:
    """Test that specifying empty config does discovery."""
    with patch(
        "homeassistant.components.flux_led.discovery.AIOBulbScanner.async_scan"
    ) as scan, patch(
        "homeassistant.components.flux_led.discovery.AIOBulbScanner.getBulbInfo"
    ) as discover:
        discover.return_value = [FLUX_DISCOVERY]
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

        assert len(scan.mock_calls) == 2
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert len(scan.mock_calls) == 4

        async_fire_time_changed(hass, utcnow() + flux_led.DISCOVERY_INTERVAL)
        await hass.async_block_till_done()
        assert len(scan.mock_calls) == 6


async def test_config_entry_reload(hass: HomeAssistant) -> None:
    """Test that a config entry can be reloaded."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=MAC_ADDRESS
    )
    config_entry.add_to_hass(hass)
    with _patch_discovery(), _patch_wifibulb():
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.LOADED
        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_config_entry_retry(hass: HomeAssistant) -> None:
    """Test that a config entry can be retried."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=MAC_ADDRESS
    )
    config_entry.add_to_hass(hass)
    with _patch_discovery(no_device=True), _patch_wifibulb(no_device=True):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_config_entry_retry_right_away_on_discovery(hass: HomeAssistant) -> None:
    """Test discovery makes the config entry reload if its in a retry state."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=MAC_ADDRESS
    )
    config_entry.add_to_hass(hass)
    with _patch_discovery(no_device=True), _patch_wifibulb(no_device=True):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.SETUP_RETRY

    with _patch_discovery(), _patch_wifibulb():
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.LOADED


async def test_coordinator_retry_right_away_on_discovery_already_setup(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test discovery makes the coordinator force poll if its already setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED

    entity_id = "light.bulb_rgbcw_ddeeff"
    assert entity_registry.async_get(entity_id).unique_id == MAC_ADDRESS
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    now = utcnow()
    bulb.async_update = AsyncMock(side_effect=RuntimeError)
    async_fire_time_changed(hass, now + timedelta(seconds=50))
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE
    bulb.async_update = AsyncMock()

    with _patch_discovery(), _patch_wifibulb():
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("discovery", "title"),
    [
        (FLUX_DISCOVERY, DEFAULT_ENTRY_TITLE),
        (FLUX_DISCOVERY_PARTIAL, DEFAULT_ENTRY_TITLE),
    ],
)
async def test_config_entry_fills_unique_id_with_directed_discovery(
    hass: HomeAssistant, discovery: dict[str, str], title: str
) -> None:
    """Test that the unique id is added if its missing via directed (not broadcast) discovery."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=None, title=IP_ADDRESS
    )
    config_entry.add_to_hass(hass)
    last_address = None

    async def _discovery(self, *args, address=None, **kwargs):
        # Only return discovery results when doing directed discovery
        nonlocal last_address
        last_address = address
        return [discovery] if address == IP_ADDRESS else []

    def _mock_getBulbInfo(*args, **kwargs):
        nonlocal last_address
        return [discovery] if last_address == IP_ADDRESS else []

    with patch(
        "homeassistant.components.flux_led.discovery.AIOBulbScanner.async_scan",
        new=_discovery,
    ), patch(
        "homeassistant.components.flux_led.discovery.AIOBulbScanner.getBulbInfo",
        new=_mock_getBulbInfo,
    ), _patch_wifibulb():
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.LOADED

    assert config_entry.unique_id == MAC_ADDRESS
    assert config_entry.title == title


async def test_time_sync_startup_and_next_day(hass: HomeAssistant) -> None:
    """Test that time is synced on startup and next day."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=MAC_ADDRESS
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.LOADED

    assert len(bulb.async_set_time.mock_calls) == 1
    async_fire_time_changed(hass, utcnow() + timedelta(hours=24))
    await hass.async_block_till_done()
    assert len(bulb.async_set_time.mock_calls) == 2


async def test_unique_id_migrate_when_mac_discovered(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test unique id migrated when mac discovered."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_REMOTE_ACCESS_HOST: "any",
            CONF_REMOTE_ACCESS_ENABLED: True,
            CONF_REMOTE_ACCESS_PORT: 1234,
            CONF_HOST: IP_ADDRESS,
            CONF_NAME: DEFAULT_ENTRY_TITLE,
        },
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(no_device=True), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    assert not config_entry.unique_id
    assert (
        entity_registry.async_get("light.bulb_rgbcw_ddeeff").unique_id
        == config_entry.entry_id
    )
    assert (
        entity_registry.async_get("switch.bulb_rgbcw_ddeeff_remote_access").unique_id
        == f"{config_entry.entry_id}_remote_access"
    )

    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        entity_registry.async_get("light.bulb_rgbcw_ddeeff").unique_id
        == config_entry.unique_id
    )
    assert (
        entity_registry.async_get("switch.bulb_rgbcw_ddeeff_remote_access").unique_id
        == f"{config_entry.unique_id}_remote_access"
    )


async def test_unique_id_migrate_when_mac_discovered_via_discovery(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test unique id migrated when mac discovered via discovery and the mac address from dhcp was one off."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_REMOTE_ACCESS_HOST: "any",
            CONF_REMOTE_ACCESS_ENABLED: True,
            CONF_REMOTE_ACCESS_PORT: 1234,
            CONF_HOST: IP_ADDRESS,
            CONF_NAME: DEFAULT_ENTRY_TITLE,
        },
        unique_id=MAC_ADDRESS_ONE_OFF,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(no_device=True), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    assert config_entry.unique_id == MAC_ADDRESS_ONE_OFF
    assert (
        entity_registry.async_get("light.bulb_rgbcw_ddeeff").unique_id
        == MAC_ADDRESS_ONE_OFF
    )
    assert (
        entity_registry.async_get("switch.bulb_rgbcw_ddeeff_remote_access").unique_id
        == f"{MAC_ADDRESS_ONE_OFF}_remote_access"
    )

    for _ in range(2):
        with _patch_discovery(), _patch_wifibulb(device=bulb):
            await hass.config_entries.async_reload(config_entry.entry_id)
            await hass.async_block_till_done()

        assert (
            entity_registry.async_get("light.bulb_rgbcw_ddeeff").unique_id
            == config_entry.unique_id
        )
        assert (
            entity_registry.async_get(
                "switch.bulb_rgbcw_ddeeff_remote_access"
            ).unique_id
            == f"{config_entry.unique_id}_remote_access"
        )


async def test_name_removed_when_it_matches_entry_title(hass: HomeAssistant) -> None:
    """Test name is removed when it matches the entry title."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_REMOTE_ACCESS_HOST: "any",
            CONF_REMOTE_ACCESS_ENABLED: True,
            CONF_REMOTE_ACCESS_PORT: 1234,
            CONF_HOST: IP_ADDRESS,
            CONF_NAME: DEFAULT_ENTRY_TITLE,
        },
        title=DEFAULT_ENTRY_TITLE,
    )
    config_entry.add_to_hass(hass)
    with _patch_discovery(), _patch_wifibulb():
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()
    assert CONF_NAME not in config_entry.data


async def test_entry_is_reloaded_when_title_changes(hass: HomeAssistant) -> None:
    """Test the entry gets reloaded when the title changes."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_REMOTE_ACCESS_HOST: "any",
            CONF_REMOTE_ACCESS_ENABLED: True,
            CONF_REMOTE_ACCESS_PORT: 1234,
            CONF_HOST: IP_ADDRESS,
        },
        title=DEFAULT_ENTRY_TITLE,
    )
    config_entry.add_to_hass(hass)
    with _patch_discovery(), _patch_wifibulb():
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

        hass.config_entries.async_update_entry(config_entry, title="Shop Light")
        assert config_entry.title == "Shop Light"
        await hass.async_block_till_done()

    assert (
        hass.states.get("light.bulb_rgbcw_ddeeff").attributes[ATTR_FRIENDLY_NAME]
        == "Shop Light"
    )
