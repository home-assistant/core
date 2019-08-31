"""Test pi_hole component."""

from asynctest import CoroutineMock
from hole import Hole

from homeassistant.components import pi_hole
from tests.common import async_setup_component
from unittest.mock import patch


def mock_pihole_data_call(Hole):
    """Need to override so as to allow mocked data."""
    Hole.__init__ = (
        lambda self, host, loop, session, location, tls, verify_tls=True, api_token=None: None
    )
    Hole.data = {
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
    pass


async def test_setup_no_config(hass):
    """Tests component setup with no config."""
    with patch.object(
        Hole, "get_data", new=CoroutineMock(side_effect=mock_pihole_data_call(Hole))
    ):
        assert await async_setup_component(hass, pi_hole.DOMAIN, {pi_hole.DOMAIN: {}})

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


async def test_setup_custom_config(hass):
    """Tests component setup with custom config."""
    with patch.object(
        Hole, "get_data", new=CoroutineMock(side_effect=mock_pihole_data_call(Hole))
    ):
        assert await async_setup_component(
            hass, pi_hole.DOMAIN, {pi_hole.DOMAIN: {"name": "Custom"}}
        )

    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.custom_ads_blocked_today").name
        == "Custom Ads Blocked Today"
    )
