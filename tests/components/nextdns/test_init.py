"""Test init of NextDNS integration."""
from unittest.mock import patch

from nextdns import ApiError

from homeassistant.components.nextdns.const import CONF_PROFILE_ID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import MockConfigEntry


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test a successful setup entry."""
    await init_integration(hass)

    state = hass.states.get("sensor.fake_profile_dns_queries_blocked_ratio")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "20.0"


async def test_config_not_ready(hass: HomeAssistant) -> None:
    """Test for setup failure if the connection to the service fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Fake Profile",
        unique_id="xyz12",
        data={CONF_API_KEY: "fake_api_key", CONF_PROFILE_ID: "xyz12"},
    )

    with patch(
        "homeassistant.components.nextdns.NextDns.get_profiles",
        side_effect=ApiError("API Error"),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
