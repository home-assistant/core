"""Test switch of NextDNS integration."""
from datetime import timedelta
from unittest.mock import patch

from nextdns import ApiError

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import SETTINGS, init_integration

from tests.common import async_fire_time_changed


async def test_switch(hass: HomeAssistant) -> None:
    """Test states of the switches."""
    registry = er.async_get(hass)

    await init_integration(hass)

    state = hass.states.get("switch.fake_profile_ai_driven_threat_detection")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_ai_driven_threat_detection")
    assert entry
    assert entry.unique_id == "xyz12_ai_threat_detection"

    state = hass.states.get("switch.fake_profile_allow_affiliate_tracking_links")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_allow_affiliate_tracking_links")
    assert entry
    assert entry.unique_id == "xyz12_allow_affiliate"

    state = hass.states.get("switch.fake_profile_anonymized_edns_client_subnet")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_anonymized_edns_client_subnet")
    assert entry
    assert entry.unique_id == "xyz12_anonymized_ecs"

    state = hass.states.get("switch.fake_profile_block_bypass_methods")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_bypass_methods")
    assert entry
    assert entry.unique_id == "xyz12_block_bypass_methods"

    state = hass.states.get("switch.fake_profile_block_child_sexual_abuse_material")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_child_sexual_abuse_material")
    assert entry
    assert entry.unique_id == "xyz12_block_csam"

    state = hass.states.get("switch.fake_profile_block_disguised_third_party_trackers")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get(
        "switch.fake_profile_block_disguised_third_party_trackers"
    )
    assert entry
    assert entry.unique_id == "xyz12_block_disguised_trackers"

    state = hass.states.get("switch.fake_profile_block_dynamic_dns_hostnames")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_dynamic_dns_hostnames")
    assert entry
    assert entry.unique_id == "xyz12_block_ddns"

    state = hass.states.get("switch.fake_profile_block_newly_registered_domains")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_newly_registered_domains")
    assert entry
    assert entry.unique_id == "xyz12_block_nrd"

    state = hass.states.get("switch.fake_profile_block_page")
    assert state
    assert state.state == STATE_OFF

    entry = registry.async_get("switch.fake_profile_block_page")
    assert entry
    assert entry.unique_id == "xyz12_block_page"

    state = hass.states.get("switch.fake_profile_block_parked_domains")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_block_parked_domains")
    assert entry
    assert entry.unique_id == "xyz12_block_parked_domains"

    state = hass.states.get("switch.fake_profile_cname_flattening")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_cname_flattening")
    assert entry
    assert entry.unique_id == "xyz12_cname_flattening"

    state = hass.states.get("switch.fake_profile_cache_boost")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_cache_boost")
    assert entry
    assert entry.unique_id == "xyz12_cache_boost"

    state = hass.states.get("switch.fake_profile_cryptojacking_protection")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_cryptojacking_protection")
    assert entry
    assert entry.unique_id == "xyz12_cryptojacking_protection"

    state = hass.states.get("switch.fake_profile_dns_rebinding_protection")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_dns_rebinding_protection")
    assert entry
    assert entry.unique_id == "xyz12_dns_rebinding_protection"

    state = hass.states.get(
        "switch.fake_profile_domain_generation_algorithms_protection"
    )
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get(
        "switch.fake_profile_domain_generation_algorithms_protection"
    )
    assert entry
    assert entry.unique_id == "xyz12_dga_protection"

    state = hass.states.get("switch.fake_profile_force_safesearch")
    assert state
    assert state.state == STATE_OFF

    entry = registry.async_get("switch.fake_profile_force_safesearch")
    assert entry
    assert entry.unique_id == "xyz12_safesearch"

    state = hass.states.get("switch.fake_profile_force_youtube_restricted_mode")
    assert state
    assert state.state == STATE_OFF

    entry = registry.async_get("switch.fake_profile_force_youtube_restricted_mode")
    assert entry
    assert entry.unique_id == "xyz12_youtube_restricted_mode"

    state = hass.states.get("switch.fake_profile_google_safe_browsing")
    assert state
    assert state.state == STATE_OFF

    entry = registry.async_get("switch.fake_profile_google_safe_browsing")
    assert entry
    assert entry.unique_id == "xyz12_google_safe_browsing"

    state = hass.states.get("switch.fake_profile_idn_homograph_attacks_protection")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_idn_homograph_attacks_protection")
    assert entry
    assert entry.unique_id == "xyz12_idn_homograph_attacks_protection"

    state = hass.states.get("switch.fake_profile_logs")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_logs")
    assert entry
    assert entry.unique_id == "xyz12_logs"

    state = hass.states.get("switch.fake_profile_threat_intelligence_feeds")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_threat_intelligence_feeds")
    assert entry
    assert entry.unique_id == "xyz12_threat_intelligence_feeds"

    state = hass.states.get("switch.fake_profile_typosquatting_protection")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_typosquatting_protection")
    assert entry
    assert entry.unique_id == "xyz12_typosquatting_protection"

    state = hass.states.get("switch.fake_profile_web3")
    assert state
    assert state.state == STATE_ON

    entry = registry.async_get("switch.fake_profile_web3")
    assert entry
    assert entry.unique_id == "xyz12_web3"


async def test_switch_on(hass: HomeAssistant) -> None:
    """Test the switch can be turned on."""
    await init_integration(hass)

    state = hass.states.get("switch.fake_profile_block_page")
    assert state
    assert state.state == STATE_OFF

    with patch(
        "homeassistant.components.nextdns.NextDns.set_setting", return_value=True
    ) as mock_switch_on:
        assert await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.fake_profile_block_page"},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get("switch.fake_profile_block_page")
        assert state
        assert state.state == STATE_ON

        mock_switch_on.assert_called_once()


async def test_switch_off(hass: HomeAssistant) -> None:
    """Test the switch can be turned on."""
    await init_integration(hass)

    state = hass.states.get("switch.fake_profile_web3")
    assert state
    assert state.state == STATE_ON

    with patch(
        "homeassistant.components.nextdns.NextDns.set_setting", return_value=True
    ) as mock_switch_on:
        assert await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.fake_profile_web3"},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get("switch.fake_profile_web3")
        assert state
        assert state.state == STATE_OFF

        mock_switch_on.assert_called_once()


async def test_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the entities unavailable correctly when service causes an error."""
    await init_integration(hass)

    state = hass.states.get("switch.fake_profile_web3")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == STATE_ON

    future = utcnow() + timedelta(minutes=10)
    with patch(
        "homeassistant.components.nextdns.NextDns.get_settings",
        side_effect=ApiError("API Error"),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("switch.fake_profile_web3")
    assert state
    assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=20)
    with patch(
        "homeassistant.components.nextdns.NextDns.get_settings",
        return_value=SETTINGS,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("switch.fake_profile_web3")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == STATE_ON
