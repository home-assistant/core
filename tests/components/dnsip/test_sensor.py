"""The test for the DNS IP sensor platform."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from aiodns.error import DNSError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.dnsip.const import (
    CONF_HOSTNAME,
    CONF_IPV4,
    CONF_IPV6,
    CONF_RESOLVER,
    CONF_RESOLVER_IPV6,
    DOMAIN,
)
from homeassistant.components.dnsip.sensor import SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import RetrieveDNS

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensor(hass: HomeAssistant) -> None:
    """Test the DNS IP sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_HOSTNAME: "home-assistant.io",
            CONF_NAME: "home-assistant.io",
            CONF_IPV4: True,
            CONF_IPV6: True,
        },
        options={
            CONF_RESOLVER: "208.67.222.222",
            CONF_RESOLVER_IPV6: "2620:119:53::53",
        },
        entry_id="1",
        unique_id="home-assistant.io",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dnsip.sensor.aiodns.DNSResolver",
        return_value=RetrieveDNS(),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state1 = hass.states.get("sensor.home_assistant_io")
    state2 = hass.states.get("sensor.home_assistant_io_ipv6")

    assert state1.state == "1.2.3.4"
    assert state2.state == "1.2.3.4"


async def test_sensor_no_response(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the DNS IP sensor with DNS error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_HOSTNAME: "home-assistant.io",
            CONF_NAME: "home-assistant.io",
            CONF_IPV4: True,
            CONF_IPV6: False,
        },
        options={
            CONF_RESOLVER: "208.67.222.222",
            CONF_RESOLVER_IPV6: "2620:119:53::53",
        },
        entry_id="1",
        unique_id="home-assistant.io",
    )
    entry.add_to_hass(hass)

    dns_mock = RetrieveDNS()
    with patch(
        "homeassistant.components.dnsip.sensor.aiodns.DNSResolver",
        return_value=dns_mock,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.home_assistant_io")

    assert state.state == "1.2.3.4"

    dns_mock.error = DNSError()
    with patch(
        "homeassistant.components.dnsip.sensor.aiodns.DNSResolver",
        return_value=dns_mock,
    ):
        freezer.tick(timedelta(seconds=SCAN_INTERVAL.seconds))
        async_fire_time_changed(hass)
        freezer.tick(timedelta(seconds=SCAN_INTERVAL.seconds))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # Allows 2 retries before going unavailable
        state = hass.states.get("sensor.home_assistant_io")
        assert state.state == "1.2.3.4"

        freezer.tick(timedelta(seconds=SCAN_INTERVAL.seconds))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.home_assistant_io")
    assert state.state == STATE_UNAVAILABLE
