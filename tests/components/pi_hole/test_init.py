"""Test pi_hole component."""

from homeassistant.components import pi_hole
from homeassistant.components.pi_hole.const import MIN_TIME_BETWEEN_UPDATES
from homeassistant.util import dt as dt_util

from . import _create_mocked_hole, _patch_config_flow_hole

from tests.async_mock import patch
from tests.common import async_fire_time_changed, async_setup_component


def _patch_init_hole(mocked_hole):
    return patch("homeassistant.components.pi_hole.Hole", return_value=mocked_hole)


async def test_setup_minimal_config(hass):
    """Tests component setup with minimal config."""
    mocked_hole = _create_mocked_hole()
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        assert await async_setup_component(
            hass, pi_hole.DOMAIN, {pi_hole.DOMAIN: [{"host": "pi.hole"}]}
        )

    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.pi_hole_ads_blocked_today").name
        == "Pi-Hole Ads Blocked Today"
    )
    assert (
        hass.states.get("sensor.pi_hole_ads_percentage_blocked_today").name
        == "Pi-Hole Ads Percentage Blocked Today"
    )
    assert (
        hass.states.get("sensor.pi_hole_dns_queries_cached").name
        == "Pi-Hole DNS Queries Cached"
    )
    assert (
        hass.states.get("sensor.pi_hole_dns_queries_forwarded").name
        == "Pi-Hole DNS Queries Forwarded"
    )
    assert (
        hass.states.get("sensor.pi_hole_dns_queries_today").name
        == "Pi-Hole DNS Queries Today"
    )
    assert (
        hass.states.get("sensor.pi_hole_dns_unique_clients").name
        == "Pi-Hole DNS Unique Clients"
    )
    assert (
        hass.states.get("sensor.pi_hole_dns_unique_domains").name
        == "Pi-Hole DNS Unique Domains"
    )
    assert (
        hass.states.get("sensor.pi_hole_domains_blocked").name
        == "Pi-Hole Domains Blocked"
    )
    assert hass.states.get("sensor.pi_hole_seen_clients").name == "Pi-Hole Seen Clients"

    assert hass.states.get("sensor.pi_hole_ads_blocked_today").state == "0"
    assert hass.states.get("sensor.pi_hole_ads_percentage_blocked_today").state == "0"
    assert hass.states.get("sensor.pi_hole_dns_queries_cached").state == "0"
    assert hass.states.get("sensor.pi_hole_dns_queries_forwarded").state == "0"
    assert hass.states.get("sensor.pi_hole_dns_queries_today").state == "0"
    assert hass.states.get("sensor.pi_hole_dns_unique_clients").state == "0"
    assert hass.states.get("sensor.pi_hole_dns_unique_domains").state == "0"
    assert hass.states.get("sensor.pi_hole_domains_blocked").state == "0"
    assert hass.states.get("sensor.pi_hole_seen_clients").state == "0"


async def test_setup_name_config(hass):
    """Tests component setup with a custom name."""
    mocked_hole = _create_mocked_hole()
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        assert await async_setup_component(
            hass,
            pi_hole.DOMAIN,
            {pi_hole.DOMAIN: [{"host": "pi.hole", "name": "Custom"}]},
        )

    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.custom_ads_blocked_today").name
        == "Custom Ads Blocked Today"
    )


async def test_disable_service_call(hass):
    """Test disable service call with no Pi-hole named."""
    mocked_hole = _create_mocked_hole()
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        assert await async_setup_component(
            hass,
            pi_hole.DOMAIN,
            {
                pi_hole.DOMAIN: [
                    {"host": "pi.hole1", "api_key": "1"},
                    {"host": "pi.hole2", "name": "Custom", "api_key": "2"},
                ]
            },
        )

        await hass.async_block_till_done()

        await hass.services.async_call(
            pi_hole.DOMAIN,
            pi_hole.SERVICE_DISABLE,
            {pi_hole.SERVICE_DISABLE_ATTR_DURATION: "00:00:01"},
            blocking=True,
        )

        await hass.async_block_till_done()

        assert mocked_hole.disable.call_count == 2


async def test_enable_service_call(hass):
    """Test enable service call with no Pi-hole named."""
    mocked_hole = _create_mocked_hole()
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        assert await async_setup_component(
            hass,
            pi_hole.DOMAIN,
            {
                pi_hole.DOMAIN: [
                    {"host": "pi.hole1", "api_key": "1"},
                    {"host": "pi.hole2", "name": "Custom", "api_key": "2"},
                ]
            },
        )

        await hass.async_block_till_done()

        await hass.services.async_call(
            pi_hole.DOMAIN, pi_hole.SERVICE_ENABLE, {}, blocking=True
        )

        await hass.async_block_till_done()

        assert mocked_hole.enable.call_count == 2


async def test_update_coordinator(hass):
    """Test update coordinator."""
    mocked_hole = _create_mocked_hole()
    sensor_entity_id = "sensor.pi_hole_ads_blocked_today"
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        assert await async_setup_component(
            hass, pi_hole.DOMAIN, {pi_hole.DOMAIN: [{"host": "pi.hole"}]}
        )
        await hass.async_block_till_done()
        assert mocked_hole.get_data.call_count == 3
        assert hass.states.get(sensor_entity_id).state == "0"

        mocked_hole.data["ads_blocked_today"] = 1
        utcnow = dt_util.utcnow()
        async_fire_time_changed(hass, utcnow + MIN_TIME_BETWEEN_UPDATES)
        await hass.async_block_till_done()
        assert mocked_hole.get_data.call_count == 4
        assert hass.states.get(sensor_entity_id).state == "1"
