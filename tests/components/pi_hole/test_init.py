"""Test pi_hole component."""

from homeassistant.components import pi_hole

from tests.async_mock import AsyncMock, patch
from tests.common import async_setup_component

ZERO_DATA = {
    "ads_blocked_today": 0,
    "ads_percentage_today": 0,
    "clients_ever_seen": 0,
    "dns_queries_today": 0,
    "domains_being_blocked": 0,
    "queries_cached": 0,
    "queries_forwarded": 0,
    "status": 0,
    "unique_clients": 0,
    "unique_domains": 0,
}


async def test_setup_minimal_config(hass):
    """Tests component setup with minimal config."""
    with patch("homeassistant.components.pi_hole.Hole") as _hole:
        _hole.return_value.get_data = AsyncMock(return_value=None)
        _hole.return_value.data = ZERO_DATA

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
    with patch("homeassistant.components.pi_hole.Hole") as _hole:
        _hole.return_value.get_data = AsyncMock(return_value=None)
        _hole.return_value.data = ZERO_DATA

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
    with patch("homeassistant.components.pi_hole.Hole") as _hole:
        mock_disable = AsyncMock(return_value=None)
        _hole.return_value.disable = mock_disable
        _hole.return_value.get_data = AsyncMock(return_value=None)
        _hole.return_value.data = ZERO_DATA

        assert await async_setup_component(
            hass,
            pi_hole.DOMAIN,
            {
                pi_hole.DOMAIN: [
                    {"host": "pi.hole", "api_key": "1"},
                    {"host": "pi.hole", "name": "Custom", "api_key": "2"},
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

        assert mock_disable.call_count == 2


async def test_enable_service_call(hass):
    """Test enable service call with no Pi-hole named."""
    with patch("homeassistant.components.pi_hole.Hole") as _hole:
        mock_enable = AsyncMock(return_value=None)
        _hole.return_value.enable = mock_enable
        _hole.return_value.get_data = AsyncMock(return_value=None)
        _hole.return_value.data = ZERO_DATA

        assert await async_setup_component(
            hass,
            pi_hole.DOMAIN,
            {
                pi_hole.DOMAIN: [
                    {"host": "pi.hole", "api_key": "1"},
                    {"host": "pi.hole", "name": "Custom", "api_key": "2"},
                ]
            },
        )

        await hass.async_block_till_done()

        await hass.services.async_call(
            pi_hole.DOMAIN, pi_hole.SERVICE_ENABLE, {}, blocking=True
        )

        await hass.async_block_till_done()

        assert mock_enable.call_count == 2
