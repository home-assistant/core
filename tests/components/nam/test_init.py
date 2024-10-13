"""Test init of Nettigo Air Monitor integration."""

from unittest.mock import patch

from nettigo_air_monitor import ApiError, AuthFailedError

from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_PLATFORM
from homeassistant.components.nam.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test a successful setup entry."""
    await init_integration(hass)

    state = hass.states.get("sensor.nettigo_air_monitor_sds011_pm2_5")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "11.03"


async def test_config_not_ready(hass: HomeAssistant) -> None:
    """Test for setup failure if the connection to the device fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="10.10.2.3",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"host": "10.10.2.3"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nam.NettigoAirMonitor.initialize",
        side_effect=ApiError("API Error"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_not_ready_while_checking_credentials(hass: HomeAssistant) -> None:
    """Test for setup failure if the connection fails while checking credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="10.10.2.3",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"host": "10.10.2.3"},
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.nam.NettigoAirMonitor.initialize"),
        patch(
            "homeassistant.components.nam.NettigoAirMonitor.async_check_credentials",
            side_effect=ApiError("API Error"),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_auth_failed(hass: HomeAssistant) -> None:
    """Test for setup failure if the auth fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="10.10.2.3",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={"host": "10.10.2.3"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nam.NettigoAirMonitor.async_check_credentials",
        side_effect=AuthFailedError("Authorization has failed"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_remove_air_quality_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test remove air_quality entities from registry."""
    entity_registry.async_get_or_create(
        AIR_QUALITY_PLATFORM,
        DOMAIN,
        "aa:bb:cc:dd:ee:ff-sds011",
        suggested_object_id="nettigo_air_monitor_sds011",
        disabled_by=None,
    )

    entity_registry.async_get_or_create(
        AIR_QUALITY_PLATFORM,
        DOMAIN,
        "aa:bb:cc:dd:ee:ff-sps30",
        suggested_object_id="nettigo_air_monitor_sps30",
        disabled_by=None,
    )

    await init_integration(hass)

    entry = entity_registry.async_get("air_quality.nettigo_air_monitor_sds011")
    assert entry is None

    entry = entity_registry.async_get("air_quality.nettigo_air_monitor_sps30")
    assert entry is None
