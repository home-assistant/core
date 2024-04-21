"""Test sensor of NextDNS integration."""

from datetime import timedelta
from unittest.mock import patch

from nextdns import ApiError
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import init_integration, mock_nextdns

from tests.common import async_fire_time_changed, snapshot_platform


async def test_sensor(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states of sensors."""
    with patch("homeassistant.components.nextdns.PLATFORMS", [Platform.SENSOR]):
        entry = await init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_availability(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    entity_registry: er.EntityRegistry,
) -> None:
    """Ensure that we mark the entities unavailable correctly when service causes an error."""
    await init_integration(hass)

    state = hass.states.get("sensor.fake_profile_dns_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "100"

    state = hass.states.get("sensor.fake_profile_dns_over_https_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "20"

    state = hass.states.get("sensor.fake_profile_dnssec_validated_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "75"

    state = hass.states.get("sensor.fake_profile_encrypted_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "60"

    state = hass.states.get("sensor.fake_profile_ipv4_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "90"

    future = utcnow() + timedelta(minutes=10)
    with (
        patch(
            "homeassistant.components.nextdns.NextDns.get_analytics_status",
            side_effect=ApiError("API Error"),
        ),
        patch(
            "homeassistant.components.nextdns.NextDns.get_analytics_dnssec",
            side_effect=ApiError("API Error"),
        ),
        patch(
            "homeassistant.components.nextdns.NextDns.get_analytics_encryption",
            side_effect=ApiError("API Error"),
        ),
        patch(
            "homeassistant.components.nextdns.NextDns.get_analytics_ip_versions",
            side_effect=ApiError("API Error"),
        ),
        patch(
            "homeassistant.components.nextdns.NextDns.get_analytics_protocols",
            side_effect=ApiError("API Error"),
        ),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.fake_profile_dns_queries")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.fake_profile_dns_over_https_queries")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.fake_profile_dnssec_validated_queries")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.fake_profile_encrypted_queries")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.fake_profile_ipv4_queries")
    assert state
    assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=20)
    with mock_nextdns():
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.fake_profile_dns_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "100"

    state = hass.states.get("sensor.fake_profile_dns_over_https_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "20"

    state = hass.states.get("sensor.fake_profile_dnssec_validated_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "75"

    state = hass.states.get("sensor.fake_profile_encrypted_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "60"

    state = hass.states.get("sensor.fake_profile_ipv4_queries")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "90"
