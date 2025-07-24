"""Tests for the Sonos config flow."""

import asyncio
import logging
from unittest.mock import Mock, PropertyMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant import config_entries
from homeassistant.components import sonos
from homeassistant.components.sonos.const import (
    DISCOVERY_INTERVAL,
    SONOS_SPEAKER_ACTIVITY,
)
from homeassistant.components.sonos.exception import SonosUpdateError
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import MockSoCo, SoCoMockFactory

from tests.common import async_fire_time_changed


async def test_creating_entry_sets_up_media_player(
    hass: HomeAssistant, zeroconf_payload: ZeroconfServiceInfo
) -> None:
    """Test setting up Sonos loads the media player."""

    # Initiate a discovery to allow a user config flow
    await hass.config_entries.flow.async_init(
        sonos.DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf_payload,
    )

    with patch(
        "homeassistant.components.sonos.media_player.async_setup_entry",
    ) as mock_setup:
        result = await hass.config_entries.flow.async_init(
            sonos.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done(wait_background_tasks=True)

    assert len(mock_setup.mock_calls) == 1


async def test_configuring_sonos_creates_entry(hass: HomeAssistant) -> None:
    """Test that specifying config will create an entry."""
    with patch(
        "homeassistant.components.sonos.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        await async_setup_component(
            hass,
            sonos.DOMAIN,
            {"sonos": {"media_player": {"interface_addr": "127.0.0.1"}}},
        )
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_not_configuring_sonos_not_creates_entry(hass: HomeAssistant) -> None:
    """Test that no config will not create an entry."""
    with patch(
        "homeassistant.components.sonos.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        await async_setup_component(hass, sonos.DOMAIN, {})
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 0


async def test_async_poll_manual_hosts_warnings(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    soco_factory: SoCoMockFactory,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that host warnings are not logged repeatedly."""

    soco = soco_factory.cache_mock(MockSoCo(), "10.10.10.1", "Bedroom")
    with (
        caplog.at_level(logging.DEBUG),
        patch.object(
            type(soco), "visible_zones", new_callable=PropertyMock
        ) as mock_visible_zones,
    ):
        # First call fails, it should be logged as a WARNING message
        mock_visible_zones.side_effect = OSError()
        caplog.clear()
        await _setup_hass(hass)
        assert [
            rec.levelname
            for rec in caplog.records
            if "Could not get visible Sonos devices from" in rec.message
        ] == ["WARNING"]

        # Second call fails again, it should be logged as a DEBUG message
        mock_visible_zones.side_effect = OSError()
        caplog.clear()
        freezer.tick(DISCOVERY_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert [
            rec.levelname
            for rec in caplog.records
            if "Could not get visible Sonos devices from" in rec.message
        ] == ["DEBUG"]

        # Third call succeeds, logs message indicating reconnect
        mock_visible_zones.return_value = {soco}
        mock_visible_zones.side_effect = None
        caplog.clear()
        freezer.tick(DISCOVERY_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert [
            rec.levelname
            for rec in caplog.records
            if "Connection reestablished to Sonos device" in rec.message
        ] == ["WARNING"]

        # Fourth call succeeds, it should log nothing
        caplog.clear()
        freezer.tick(DISCOVERY_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert "Connection reestablished to Sonos device" not in caplog.text

        # Fifth call fails again again, should be logged as a WARNING message
        mock_visible_zones.side_effect = OSError()
        caplog.clear()
        freezer.tick(DISCOVERY_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert [
            rec.levelname
            for rec in caplog.records
            if "Could not get visible Sonos devices from" in rec.message
        ] == ["WARNING"]


class _MockSoCoOsError(MockSoCo):
    @property
    def visible_zones(self):
        raise OSError


class _MockSoCoVisibleZones(MockSoCo):
    def set_visible_zones(self, visible_zones) -> None:
        """Set visible zones."""
        self.vz_return = visible_zones  # pylint: disable=attribute-defined-outside-init

    @property
    def visible_zones(self):
        return self.vz_return


async def _setup_hass(hass: HomeAssistant):
    await async_setup_component(
        hass,
        sonos.DOMAIN,
        {
            "sonos": {
                "media_player": {
                    "interface_addr": "127.0.0.1",
                    "hosts": ["10.10.10.1", "10.10.10.2"],
                }
            }
        },
    )
    await hass.async_block_till_done()


async def test_async_poll_manual_hosts_1(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tests first device fails, second device successful, speakers do not exist."""
    soco_1 = soco_factory.cache_mock(_MockSoCoOsError(), "10.10.10.1", "Living Room")
    soco_2 = soco_factory.cache_mock(MockSoCo(), "10.10.10.2", "Bedroom")

    with caplog.at_level(logging.WARNING):
        await _setup_hass(hass)
        assert "media_player.bedroom" in entity_registry.entities
        assert "media_player.living_room" not in entity_registry.entities
        assert (
            f"Could not get visible Sonos devices from {soco_1.ip_address}"
            in caplog.text
        )
        assert (
            f"Could not get visible Sonos devices from {soco_2.ip_address}"
            not in caplog.text
        )

    await hass.async_block_till_done(wait_background_tasks=True)


async def test_async_poll_manual_hosts_2(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test first device success, second device fails, speakers do not exist."""
    soco_1 = soco_factory.cache_mock(MockSoCo(), "10.10.10.1", "Living Room")
    soco_2 = soco_factory.cache_mock(_MockSoCoOsError(), "10.10.10.2", "Bedroom")

    with caplog.at_level(logging.WARNING):
        await _setup_hass(hass)
        assert "media_player.bedroom" not in entity_registry.entities
        assert "media_player.living_room" in entity_registry.entities
        assert (
            f"Could not get visible Sonos devices from {soco_1.ip_address}"
            not in caplog.text
        )
        assert (
            f"Could not get visible Sonos devices from {soco_2.ip_address}"
            in caplog.text
        )

    await hass.async_block_till_done(wait_background_tasks=True)


async def test_async_poll_manual_hosts_3(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test both devices fail, speakers do not exist."""
    soco_1 = soco_factory.cache_mock(_MockSoCoOsError(), "10.10.10.1", "Living Room")
    soco_2 = soco_factory.cache_mock(_MockSoCoOsError(), "10.10.10.2", "Bedroom")

    with caplog.at_level(logging.WARNING):
        await _setup_hass(hass)
        assert "media_player.bedroom" not in entity_registry.entities
        assert "media_player.living_room" not in entity_registry.entities
        assert (
            f"Could not get visible Sonos devices from {soco_1.ip_address}"
            in caplog.text
        )
        assert (
            f"Could not get visible Sonos devices from {soco_2.ip_address}"
            in caplog.text
        )

    await hass.async_block_till_done(wait_background_tasks=True)


async def test_async_poll_manual_hosts_4(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test both devices are successful, speakers do not exist."""
    soco_1 = soco_factory.cache_mock(MockSoCo(), "10.10.10.1", "Living Room")
    soco_2 = soco_factory.cache_mock(MockSoCo(), "10.10.10.2", "Bedroom")

    with caplog.at_level(logging.WARNING):
        await _setup_hass(hass)
        assert "media_player.bedroom" in entity_registry.entities
        assert "media_player.living_room" in entity_registry.entities
        assert (
            f"Could not get visible Sonos devices from {soco_1.ip_address}"
            not in caplog.text
        )
        assert (
            f"Could not get visible Sonos devices from {soco_2.ip_address}"
            not in caplog.text
        )

    await hass.async_block_till_done(wait_background_tasks=True)


class SpeakerActivity:
    """Unit test class to track speaker activity messages."""

    def __init__(self, hass: HomeAssistant, soco: MockSoCo) -> None:
        """Create the object from soco."""
        self.soco = soco
        self.hass = hass
        self.call_count: int = 0
        self.event = asyncio.Event()
        async_dispatcher_connect(
            self.hass,
            f"{SONOS_SPEAKER_ACTIVITY}-{self.soco.uid}",
            self.speaker_activity,
        )

    @callback
    def speaker_activity(self, source: str) -> None:
        """Track the last activity on this speaker, set availability and resubscribe."""
        if source == "manual zone scan":
            self.event.set()
            self.call_count += 1


async def test_async_poll_manual_hosts_5(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test both succeed, speakers exist and unavailable, ping succeeds."""
    soco_1 = soco_factory.cache_mock(MockSoCo(), "10.10.10.1", "Living Room")
    soco_1.renderingControl = Mock()
    soco_1.renderingControl.GetVolume = Mock()
    speaker_1_activity = SpeakerActivity(hass, soco_1)
    soco_2 = soco_factory.cache_mock(MockSoCo(), "10.10.10.2", "Bedroom")
    soco_2.renderingControl = Mock()
    soco_2.renderingControl.GetVolume = Mock()
    speaker_2_activity = SpeakerActivity(hass, soco_2)

    with caplog.at_level(logging.DEBUG):
        caplog.clear()

        await _setup_hass(hass)

        assert "media_player.bedroom" in entity_registry.entities
        assert "media_player.living_room" in entity_registry.entities

        async_fire_time_changed(hass, dt_util.utcnow() + DISCOVERY_INTERVAL)
        await hass.async_block_till_done()
        await asyncio.gather(
            *[speaker_1_activity.event.wait(), speaker_2_activity.event.wait()]
        )
        assert speaker_1_activity.call_count == 1
        assert speaker_2_activity.call_count == 1
        assert "Activity on Living Room" in caplog.text
        assert "Activity on Bedroom" in caplog.text

    await hass.async_block_till_done(wait_background_tasks=True)


async def test_async_poll_manual_hosts_6(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test both succeed, speakers exist and unavailable, pings fail."""
    soco_1 = soco_factory.cache_mock(MockSoCo(), "10.10.10.1", "Living Room")
    # Rendering Control Get Volume is what speaker ping calls.
    soco_1.renderingControl = Mock()
    soco_1.renderingControl.GetVolume = Mock()
    soco_1.renderingControl.GetVolume.side_effect = SonosUpdateError()
    speaker_1_activity = SpeakerActivity(hass, soco_1)
    soco_2 = soco_factory.cache_mock(MockSoCo(), "10.10.10.2", "Bedroom")
    soco_2.renderingControl = Mock()
    soco_2.renderingControl.GetVolume = Mock()
    soco_2.renderingControl.GetVolume.side_effect = SonosUpdateError()
    speaker_2_activity = SpeakerActivity(hass, soco_2)

    with patch(
        "homeassistant.components.sonos.DISCOVERY_INTERVAL"
    ) as mock_discovery_interval:
        # Speed up manual discovery interval so second iteration runs sooner
        mock_discovery_interval.total_seconds = Mock(side_effect=[0.0, 60])
        await _setup_hass(hass)

        assert "media_player.bedroom" in entity_registry.entities
        assert "media_player.living_room" in entity_registry.entities

        with caplog.at_level(logging.DEBUG):
            caplog.clear()
            await hass.async_block_till_done()
            assert "Activity on Living Room" not in caplog.text
            assert "Activity on Bedroom" not in caplog.text
            assert speaker_1_activity.call_count == 0
            assert speaker_2_activity.call_count == 0

    await hass.async_block_till_done(wait_background_tasks=True)


async def test_async_poll_manual_hosts_7(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test both succeed, speaker do not exist, new hosts found in visible zones."""
    soco_1 = soco_factory.cache_mock(
        _MockSoCoVisibleZones(), "10.10.10.1", "Living Room"
    )
    soco_2 = soco_factory.cache_mock(_MockSoCoVisibleZones(), "10.10.10.2", "Bedroom")
    soco_3 = soco_factory.cache_mock(MockSoCo(), "10.10.10.3", "Basement")
    soco_4 = soco_factory.cache_mock(MockSoCo(), "10.10.10.4", "Garage")
    soco_5 = soco_factory.cache_mock(MockSoCo(), "10.10.10.5", "Studio")

    soco_1.set_visible_zones({soco_1, soco_2, soco_3, soco_4, soco_5})
    soco_2.set_visible_zones({soco_1, soco_2, soco_3, soco_4, soco_5})

    await _setup_hass(hass)
    await hass.async_block_till_done()

    assert "media_player.bedroom" in entity_registry.entities
    assert "media_player.living_room" in entity_registry.entities
    assert "media_player.basement" in entity_registry.entities
    assert "media_player.garage" in entity_registry.entities
    assert "media_player.studio" in entity_registry.entities

    await hass.async_block_till_done(wait_background_tasks=True)


async def test_async_poll_manual_hosts_8(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test both succeed, speaker do not exist, invisible zone."""
    soco_1 = soco_factory.cache_mock(
        _MockSoCoVisibleZones(), "10.10.10.1", "Living Room"
    )
    soco_2 = soco_factory.cache_mock(_MockSoCoVisibleZones(), "10.10.10.2", "Bedroom")
    soco_3 = soco_factory.cache_mock(MockSoCo(), "10.10.10.3", "Basement")
    soco_4 = soco_factory.cache_mock(MockSoCo(), "10.10.10.4", "Garage")
    soco_5 = soco_factory.cache_mock(MockSoCo(), "10.10.10.5", "Studio")

    soco_1.set_visible_zones({soco_2, soco_3, soco_4, soco_5})
    soco_2.set_visible_zones({soco_2, soco_3, soco_4, soco_5})

    await _setup_hass(hass)
    await hass.async_block_till_done()

    assert "media_player.bedroom" in entity_registry.entities
    assert "media_player.living_room" not in entity_registry.entities
    assert "media_player.basement" in entity_registry.entities
    assert "media_player.garage" in entity_registry.entities
    assert "media_player.studio" in entity_registry.entities
    await hass.async_block_till_done(wait_background_tasks=True)


async def _setup_hass_ipv6_address_not_supported(hass: HomeAssistant):
    await async_setup_component(
        hass,
        sonos.DOMAIN,
        {
            "sonos": {
                "media_player": {
                    "interface_addr": "127.0.0.1",
                    "hosts": ["2001:db8:3333:4444:5555:6666:7777:8888"],
                }
            }
        },
    )
    await hass.async_block_till_done()


async def test_ipv6_not_supported(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tests that invalid ipv4 addresses do not generate stack dump."""
    with caplog.at_level(logging.DEBUG):
        caplog.clear()
        await _setup_hass_ipv6_address_not_supported(hass)
        await hass.async_block_till_done()
    assert "invalid ip_address received" in caplog.text
    assert "2001:db8:3333:4444:5555:6666:7777:8888" in caplog.text
