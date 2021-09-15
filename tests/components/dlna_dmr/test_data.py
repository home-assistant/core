"""Tests for the DLNA DMR data module."""
from __future__ import annotations

from homeassistant.components.dlna_dmr.const import DOMAIN
from homeassistant.components.dlna_dmr.data import EventListenAddr, get_domain_data
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant


async def test_get_domain_data(hass: HomeAssistant) -> None:
    """Test the get_domain_data function returns the same data every time."""
    assert DOMAIN not in hass.data
    domain_data = get_domain_data(hass)
    assert domain_data is not None
    assert get_domain_data(hass) is domain_data


async def test_event_notifier(hass: HomeAssistant) -> None:
    """Test getting and releasing event notifiers."""
    domain_data = get_domain_data(hass)

    listen_addr = EventListenAddr(None, 0, None)
    event_notifier = await domain_data.async_get_event_notifier(listen_addr, hass)
    assert event_notifier is not None

    # Same address should give same notifier
    listen_addr_2 = EventListenAddr(None, 0, None)
    event_notifier_2 = await domain_data.async_get_event_notifier(listen_addr_2, hass)
    assert event_notifier_2 is event_notifier

    # Different address should give different notifier
    listen_addr_3 = EventListenAddr("localhost", 9999, "http://192.88.99.4:9999/notify")
    event_notifier_3 = await domain_data.async_get_event_notifier(listen_addr_3, hass)
    assert event_notifier_3 is not None
    assert event_notifier_3 is not event_notifier

    # There should be 2 notifiers total, one with 2 references, and a stop callback
    assert set(domain_data.event_notifiers.keys()) == {listen_addr, listen_addr_3}
    assert domain_data.event_notifier_refs == {listen_addr: 2, listen_addr_3: 1}
    assert domain_data.stop_listener_remove is not None

    # Releasing notifiers should delete them when they have not more references
    await domain_data.async_release_event_notifier(listen_addr)
    assert set(domain_data.event_notifiers.keys()) == {listen_addr, listen_addr_3}
    assert domain_data.event_notifier_refs == {listen_addr: 1, listen_addr_3: 1}
    assert domain_data.stop_listener_remove is not None

    await domain_data.async_release_event_notifier(listen_addr)
    assert set(domain_data.event_notifiers.keys()) == {listen_addr_3}
    assert domain_data.event_notifier_refs == {listen_addr: 0, listen_addr_3: 1}
    assert domain_data.stop_listener_remove is not None

    await domain_data.async_release_event_notifier(listen_addr_3)
    assert set(domain_data.event_notifiers.keys()) == set()
    assert domain_data.event_notifier_refs == {listen_addr: 0, listen_addr_3: 0}
    assert domain_data.stop_listener_remove is None


async def test_cleanup_event_notifiers(hass: HomeAssistant) -> None:
    """Test cleanup function clears all event notifiers."""
    domain_data = get_domain_data(hass)
    await domain_data.async_get_event_notifier(EventListenAddr(None, 0, None), hass)
    await domain_data.async_get_event_notifier(
        EventListenAddr(None, 0, "different"), hass
    )

    await domain_data.async_cleanup_event_notifiers(Event(EVENT_HOMEASSISTANT_STOP))

    assert not domain_data.event_notifiers
    assert not domain_data.event_notifier_refs
