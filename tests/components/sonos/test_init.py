"""Tests for the Sonos config flow."""

import asyncio
from collections.abc import Callable, Coroutine
from functools import partial
from http import HTTPStatus
from itertools import chain, repeat
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from requests import Response
from requests.exceptions import HTTPError

from homeassistant import config_entries
from homeassistant.components import sonos
from homeassistant.components.sonos.const import (
    DISCOVERY_INTERVAL,
    SONOS_SPEAKER_ACTIVITY,
    UPNP_ISSUE_ID,
    UPNP_ST,
)
from homeassistant.components.sonos.exception import SonosUpdateError
from homeassistant.components.sonos.speaker import RESUB_COOLDOWN_SECONDS
from homeassistant.components.ssdp import SsdpChange
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.service_info.ssdp import ATTR_UPNP_UDN, SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import MockSoCo, SoCoMockFactory, SonosMockEvent


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
        return_value=None,
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
        return_value=None,
    ) as mock_setup:
        await async_setup_component(hass, sonos.DOMAIN, {})
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 0


async def test_upnp_disabled_discovery(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    config_entry: MockConfigEntry,
    soco: MockSoCo,
) -> None:
    """Test issue creation when discovery processing fails with 403."""

    resp = Response()
    resp.status_code = HTTPStatus.FORBIDDEN
    http_error = HTTPError(response=resp)

    with patch(
        "tests.components.sonos.conftest.MockSoCo.household_id",
        new_callable=PropertyMock,
        create=True,
        side_effect=http_error,
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    issue_id = f"{UPNP_ISSUE_ID}_{soco.ip_address}"
    issue = issue_registry.async_get_issue(sonos.DOMAIN, issue_id)
    assert issue is not None
    assert issue.config_entry_id == config_entry.entry_id

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(sonos.DOMAIN, issue_id) is None


def _speaker_services(soco: MockSoCo) -> tuple[MagicMock, ...]:
    """Return the services a speaker subscribes to."""
    return (
        soco.alarmClock,
        soco.avTransport,
        soco.contentDirectory,
        soco.deviceProperties,
        soco.renderingControl,
        soco.zoneGroupTopology,
    )


def _wrap_unsubscribes(soco: MockSoCo) -> list[AsyncMock]:
    """Wrap the unsubscribe methods of all speaker subscriptions in mocks."""
    unsubscribes = []
    for service in _speaker_services(soco):
        subscription = service.subscribe.return_value
        subscription.unsubscribe = AsyncMock(wraps=subscription.unsubscribe)
        unsubscribes.append(subscription.unsubscribe)
    return unsubscribes


async def test_disable_device_unsubscribes_speaker(
    hass: HomeAssistant,
    async_autosetup_sonos: None,
    soco: MockSoCo,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    fire_zgs_event: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """Test disable tears down subscriptions and re-enable restores them."""
    unsubscribes = _wrap_unsubscribes(soco)
    device = device_registry.async_get_device_by_identifier(
        (sonos.DOMAIN, soco.uid), config_entry.entry_id
    )
    assert device is not None

    device_registry.async_update_device(
        device.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    for unsubscribe in unsubscribes:
        unsubscribe.assert_awaited_once()

    for service in _speaker_services(soco):
        service.subscribe.reset_mock()
    # Let fire_zgs_event wait for the callback set by the reloaded entry.
    soco.zoneGroupTopology.subscribe.return_value.callback_future = None

    # Re-enabling the device re-enables its entities, which reloads the entry.
    device_registry.async_update_device(device.id, disabled_by=None)
    freezer.tick(config_entries.RELOAD_AFTER_UPDATE_DELAY + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await fire_zgs_event()

    for service in _speaker_services(soco):
        service.subscribe.assert_awaited()


async def test_disabled_device_ignores_household_poll_activity(
    hass: HomeAssistant,
    async_autosetup_sonos: None,
    soco: MockSoCo,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a household poll doesn't resubscribe a disabled device."""
    device = device_registry.async_get_device_by_identifier(
        (sonos.DOMAIN, soco.uid), config_entry.entry_id
    )
    assert device is not None
    device_registry.async_update_device(
        device.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    for service in _speaker_services(soco):
        service.subscribe.reset_mock()

    # The household poll emits this signal after a successful update.
    freezer.tick(RESUB_COOLDOWN_SECONDS + 1)
    async_dispatcher_send(
        hass, f"{SONOS_SPEAKER_ACTIVITY}-{soco.uid}", "household poll"
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    for service in _speaker_services(soco):
        service.subscribe.assert_not_awaited()


async def test_device_disabled_during_setup_does_not_subscribe(
    hass: HomeAssistant,
    async_setup_sonos: Callable[[], Coroutine[Any, Any, None]],
    soco: MockSoCo,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a device disabled before speaker setup completes is not subscribed."""
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(sonos.DOMAIN, soco.uid)},
    )
    speaker_info = soco.get_speaker_info.return_value

    def _disable_during_setup(*args: Any, **kwargs: Any) -> dict[str, Any]:
        # Runs in the executor while the speaker is being created
        hass.loop.call_soon_threadsafe(
            partial(
                device_registry.async_update_device,
                device.id,
                disabled_by=dr.DeviceEntryDisabler.USER,
            )
        )
        return speaker_info

    soco.get_speaker_info.side_effect = _disable_during_setup
    await async_setup_sonos()

    assert not config_entry.runtime_data.discovered[soco.uid].available
    # ZoneGroupTopology is subscribed by discovery before the speaker is created
    for service in (
        soco.alarmClock,
        soco.avTransport,
        soco.contentDirectory,
        soco.deviceProperties,
        soco.renderingControl,
    ):
        service.subscribe.assert_not_awaited()


@pytest.mark.parametrize(
    ("identifiers", "update"),
    [
        pytest.param(
            {(sonos.DOMAIN, "RINCON_test")},
            {"name_by_user": "Renamed"},
            id="other_change",
        ),
        pytest.param(
            {(sonos.DOMAIN, "RINCON_undiscovered")},
            {"disabled_by": dr.DeviceEntryDisabler.USER},
            id="undiscovered_speaker",
        ),
        pytest.param(
            {("other_domain", "RINCON_test")},
            {"disabled_by": dr.DeviceEntryDisabler.USER},
            id="other_domain",
        ),
    ],
)
async def test_device_registry_update_ignored(
    hass: HomeAssistant,
    async_autosetup_sonos: None,
    soco: MockSoCo,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    identifiers: set[tuple[str, str]],
    update: dict[str, Any],
) -> None:
    """Test device registry updates that must not take the speaker offline."""
    unsubscribes = _wrap_unsubscribes(soco)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers=identifiers
    )

    device_registry.async_update_device(device.id, **update)
    await hass.async_block_till_done(wait_background_tasks=True)

    for unsubscribe in unsubscribes:
        unsubscribe.assert_not_awaited()


async def test_device_disabled_in_other_config_entry_ignored(
    hass: HomeAssistant,
    async_autosetup_sonos: None,
    soco: MockSoCo,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test disabling a device of another config entry with the same uid."""
    unsubscribes = _wrap_unsubscribes(soco)
    other_entry = MockConfigEntry(domain="other_domain")
    other_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={(sonos.DOMAIN, soco.uid)},
    )

    device_registry.async_update_device(
        device.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    for unsubscribe in unsubscribes:
        unsubscribe.assert_not_awaited()


async def test_upnp_disabled_manual_hosts(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    soco_factory: SoCoMockFactory,
) -> None:
    """Test issue creation when manual host processing fails with 403."""

    resp = Response()
    resp.status_code = HTTPStatus.FORBIDDEN
    http_error = HTTPError(response=resp)
    soco = soco_factory.cache_mock(MockSoCo(), "10.10.10.1", "Bedroom")

    with patch.object(
        type(soco),
        "household_id",
        new_callable=PropertyMock,
        create=True,
        side_effect=http_error,
    ):
        await _setup_hass(hass)

    issue = issue_registry.async_get_issue(
        sonos.DOMAIN, f"{UPNP_ISSUE_ID}_{soco.ip_address}"
    )
    assert issue is not None
    assert issue.translation_placeholders.get("device_ip") == "10.10.10.1"


async def test_discovery_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test exception handling during discovery processing."""

    with patch(
        "tests.components.sonos.conftest.MockSoCo.household_id",
        new_callable=PropertyMock,
        create=True,
        side_effect=OSError("This is a test"),
    ):
        caplog.set_level(logging.ERROR)
        caplog.clear()
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert "This is a test" in caplog.text


async def test_discovery_skips_disabled_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    soco: MockSoCo,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test discovery message handling skips disabled Sonos devices."""
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(sonos.DOMAIN, soco.uid)},
        disabled_by=dr.DeviceEntryDisabler.USER,
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    soco.zoneGroupTopology.subscribe.assert_not_awaited()
    assert not er.async_entries_for_device(entity_registry, device.id)


async def test_discovery_reenable_device_on_new_discovery(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    soco: MockSoCo,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    discover: MagicMock,
    fire_zgs_event: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """Test re-enabling a disabled device allows subscriptions and entities."""
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(sonos.DOMAIN, soco.uid)},
        disabled_by=dr.DeviceEntryDisabler.USER,
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    soco.zoneGroupTopology.subscribe.assert_not_awaited()
    assert not er.async_entries_for_device(entity_registry, device.id)

    device_registry.async_update_device(device.id, disabled_by=None)

    # Re-run discovery using the fixture's own mocked callback path.
    discover.side_effect(*discover.call_args.args, **discover.call_args.kwargs)
    await hass.async_block_till_done(wait_background_tasks=True)

    await fire_zgs_event()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert soco.zoneGroupTopology.subscribe.await_count > 0
    assert er.async_entries_for_device(entity_registry, device.id)


async def test_discovery_from_ssdp_advertisement(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    soco: MockSoCo,
    discover: MagicMock,
    fire_zgs_event: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """Test speakers are set up when SSDP only receives advertisements."""
    # NOTIFY advertisements carry "nt" but no "st" header.
    advertisement_headers = {
        "nt": UPNP_ST,
        "nts": "ssdp:alive",
        "location": f"http://{soco.ip_address}/",
    }

    def replay_advertisement(
        hass: HomeAssistant,
        callback: Callable[[SsdpServiceInfo, SsdpChange], None],
        match_dict: dict[str, str],
    ) -> MagicMock:
        if match_dict.items() <= advertisement_headers.items():
            callback(
                SsdpServiceInfo(
                    ssdp_location=f"http://{soco.ip_address}/",
                    ssdp_st=UPNP_ST,
                    ssdp_nt=UPNP_ST,
                    ssdp_usn=f"uuid:{soco.uid}::{UPNP_ST}",
                    upnp={ATTR_UPNP_UDN: f"uuid:{soco.uid}"},
                ),
                SsdpChange.ALIVE,
            )
        return MagicMock()

    discover.side_effect = replay_advertisement
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    soco.zoneGroupTopology.subscribe.assert_awaited()
    await fire_zgs_event()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("media_player.zone_a")


@pytest.mark.parametrize(
    ("speaker_changes", "expected_subscribes"),
    [
        pytest.param([], 0, id="speaker_available"),
        pytest.param([SsdpChange.BYEBYE], 1, id="speaker_unavailable"),
    ],
)
async def test_discovery_unknown_uid_on_known_speaker_ip(
    hass: HomeAssistant,
    async_autosetup_sonos: None,
    soco: MockSoCo,
    discover: MagicMock,
    speaker_changes: list[SsdpChange],
    expected_subscribes: int,
) -> None:
    """Test an unknown uid on a known speaker's IP, e.g. an Arc headphone zone."""
    ssdp_callback = discover.call_args.args[1]
    for change in speaker_changes:
        ssdp_callback(
            SsdpServiceInfo(
                ssdp_location=f"http://{soco.ip_address}:1400/",
                ssdp_st=UPNP_ST,
                ssdp_usn=f"uuid:{soco.uid}::{UPNP_ST}",
                upnp={ATTR_UPNP_UDN: f"uuid:{soco.uid}"},
            ),
            change,
        )
    await hass.async_block_till_done(wait_background_tasks=True)
    soco.zoneGroupTopology.subscribe.reset_mock()

    headphone_uid = "RINCON_test01500"
    ssdp_callback(
        SsdpServiceInfo(
            ssdp_location=f"http://{soco.ip_address}:1500/xml/device_description.xml",
            ssdp_st=UPNP_ST,
            ssdp_usn=f"uuid:{headphone_uid}::{UPNP_ST}",
            upnp={ATTR_UPNP_UDN: f"uuid:{headphone_uid}"},
        ),
        SsdpChange.ALIVE,
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert soco.zoneGroupTopology.subscribe.await_count == expected_subscribes


async def test_async_poll_manual_hosts_warnings(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    soco_factory: SoCoMockFactory,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that host warnings are not logged repeatedly."""

    soco = soco_factory.cache_mock(MockSoCo(), "10.10.10.1", "Bedroom")
    with (
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


class _MockSoCoUidError(MockSoCo):
    """Mock SoCo used for uid property error tests."""

    @property
    def visible_zones(self):
        """Return no additional zones without touching uid lookup."""
        return set()


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


async def test_async_poll_manual_hosts_uid_oserror(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test uid lookup OSError skips host and logs warning."""
    soco_1 = soco_factory.cache_mock(_MockSoCoUidError(), "10.10.10.1", "Living Room")
    soco_factory.cache_mock(MockSoCo(), "10.10.10.2", "Bedroom")
    uid = soco_1.uid

    with (
        caplog.at_level(logging.WARNING),
        patch.object(
            type(soco_1),
            "uid",
            new_callable=PropertyMock,
            create=True,
            side_effect=chain([uid], repeat(OSError("uid unavailable"))),
        ),
    ):
        await _setup_hass(hass)

    assert "media_player.bedroom" in entity_registry.entities
    assert "media_player.living_room" not in entity_registry.entities
    assert f"Could not get Sonos uid from {soco_1.ip_address}" in caplog.text

    await hass.async_block_till_done(wait_background_tasks=True)


async def test_async_poll_manual_hosts_uid_http_error(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test uid lookup HTTPError skips host."""
    resp = Response()
    resp.status_code = HTTPStatus.FORBIDDEN
    http_error = HTTPError(response=resp)

    soco_1 = soco_factory.cache_mock(_MockSoCoUidError(), "10.10.10.1", "Living Room")
    soco_factory.cache_mock(MockSoCo(), "10.10.10.2", "Bedroom")
    uid = soco_1.uid

    with patch.object(
        type(soco_1),
        "uid",
        new_callable=PropertyMock,
        create=True,
        side_effect=chain([uid], repeat(http_error)),
    ):
        await _setup_hass(hass)

    assert "media_player.bedroom" in entity_registry.entities
    assert "media_player.living_room" not in entity_registry.entities

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
    soco_2 = soco_factory.cache_mock(MockSoCo(), "10.10.10.2", "Bedroom")
    soco_2.renderingControl = Mock()
    soco_2.renderingControl.GetVolume = Mock()
    soco_2.renderingControl.GetVolume.side_effect = SonosUpdateError()

    await _setup_hass(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "media_player.bedroom" in entity_registry.entities
    assert "media_player.living_room" in entity_registry.entities
    bedroom_state = hass.states.get("media_player.bedroom")
    assert bedroom_state is not None
    assert bedroom_state.state == "unavailable"
    living_room_state = hass.states.get("media_player.living_room")
    assert living_room_state is not None
    assert living_room_state.state == "unavailable"

    speaker_1_activity = SpeakerActivity(hass, soco_1)
    speaker_2_activity = SpeakerActivity(hass, soco_2)
    soco_1.renderingControl.GetVolume.reset_mock()
    soco_2.renderingControl.GetVolume.reset_mock()

    with (
        freeze_time(dt_util.utcnow()) as freezer,
    ):
        caplog.clear()
        freezer.tick(DISCOVERY_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        soco_1.renderingControl.GetVolume.assert_called_once_with(
            [("InstanceID", 0), ("Channel", "Master")], timeout=1
        )
        soco_2.renderingControl.GetVolume.assert_called_once_with(
            [("InstanceID", 0), ("Channel", "Master")], timeout=1
        )
        assert "Activity on Living Room" not in caplog.text
        assert "Activity on Bedroom" not in caplog.text
        assert speaker_1_activity.call_count == 0
        assert speaker_2_activity.call_count == 0


async def test_async_poll_manual_hosts_skips_ping_for_disabled_device(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test disabled manual-host speakers are not pinged on heartbeat."""
    soco = soco_factory.cache_mock(MockSoCo(), "10.10.10.1", "Living Room")
    soco.renderingControl = Mock()
    soco.renderingControl.GetVolume = Mock()

    await _setup_hass(hass)

    assert "media_player.living_room" in entity_registry.entities

    # Mark the speaker unavailable via ZGS event with VanishedDevices.
    async def fire_vanish_event():
        subscription = soco.zoneGroupTopology.subscribe.return_value
        sub_callback = await subscription.wait_for_callback_to_be_set()
        zgs_with_vanished = f"""<ZoneGroupState>
            <ZoneGroups>
                <ZoneGroup Coordinator="{soco.uid}" ID="{soco.uid}:1384750254">
                    <ZoneGroupMember UUID="{soco.uid}" Location="http://192.168.4.2:1400/xml/device_description.xml" ZoneName="Living Room"/>
                </ZoneGroup>
            </ZoneGroups>
            <VanishedDevices>
                <ZoneGroupMember UUID="{soco.uid}" Reason="powered off" ZoneName="Living Room"/>
            </VanishedDevices>
        </ZoneGroupState>"""
        event = SonosMockEvent(
            soco, soco.zoneGroupTopology, {"ZoneGroupState": zgs_with_vanished}
        )
        sub_callback(event)
        await hass.async_block_till_done(wait_background_tasks=True)

    await fire_vanish_event()

    # Verify the speaker is marked unavailable.
    state = hass.states.get("media_player.living_room")
    assert state is not None
    assert state.state == "unavailable"

    # Now disable the device.
    entry = hass.config_entries.async_entries(sonos.DOMAIN)[0]
    device = device_registry.async_get_device_by_identifier(
        (sonos.DOMAIN, soco.uid), entry.entry_id
    )
    assert device is not None
    device_registry.async_update_device(
        device.id,
        disabled_by=dr.DeviceEntryDisabler.USER,
    )

    # SonosSpeaker.ping uses RenderingControl.GetVolume under the hood.
    soco.renderingControl.GetVolume.reset_mock()
    with freeze_time(dt_util.utcnow()) as freezer:
        freezer.tick(DISCOVERY_INTERVAL)
        async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # The disabled speaker should not have been pinged.
    soco.renderingControl.GetVolume.assert_not_called()


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


async def test_async_poll_manual_hosts_skips_disabled_visible_zone(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test disabled visible zone is skipped in visible-zones expansion."""
    soco_1 = soco_factory.cache_mock(
        _MockSoCoVisibleZones(), "10.10.10.1", "Living Room"
    )
    # Host 2 is marked disabled in the device registry.
    # Host 1's visible-zones expansion encounters host 2 and exercises the
    # _async_add_visible_zones disabled filter branch.
    soco_2 = soco_factory.cache_mock(MockSoCo(), "10.10.10.2", "Bedroom")

    soco_1.set_visible_zones({soco_1, soco_2})

    config_entry = MockConfigEntry(domain=sonos.DOMAIN)
    config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(sonos.DOMAIN, soco_2.uid)},
        disabled_by=dr.DeviceEntryDisabler.USER,
    )

    await _setup_hass(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "media_player.living_room" in entity_registry.entities
    assert "media_player.bedroom" not in entity_registry.entities
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
    caplog.clear()
    await _setup_hass_ipv6_address_not_supported(hass)
    await hass.async_block_till_done()
    assert "invalid ip_address received" in caplog.text
    assert "2001:db8:3333:4444:5555:6666:7777:8888" in caplog.text


async def test_no_exception_when_entry_unloaded_during_speaker_discovery(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    soco: MockSoCo,
    soco_factory: SoCoMockFactory,
    async_autosetup_sonos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test no exception when a discovery event arrives after entry unload.

    Exercises the scenario where async_add_speakers is called after the entry
    has been unloaded. The _stop_event guard in _add_speaker must detect that
    the entry is inactive and skip speaker creation without raising an exception.
    """
    new_soco = soco_factory.cache_mock(MockSoCo(), "10.10.10.99", "New Room")

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    # Fire a ZGS discovery event for the new speaker after the entry is
    # unloaded. This simulates a late-arriving network event.
    subscription = soco.zoneGroupTopology.subscribe.return_value
    sub_callback = await subscription.wait_for_callback_to_be_set()
    with (
        patch.object(
            MockSoCo,
            "visible_zones",
            new_callable=PropertyMock,
            return_value={soco, new_soco},
        ),
    ):
        caplog.clear()
        sub_callback(SonosMockEvent(soco, soco.zoneGroupTopology, {}))
        await hass.async_block_till_done(wait_background_tasks=True)

    assert any(
        "Config entry unloaded while adding speaker" in message
        for message in caplog.messages
    )
