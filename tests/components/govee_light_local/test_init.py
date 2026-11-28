"""Tests init for the Govee Local API integration."""

import asyncio
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from govee_local_api import GoveeDevice
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant import config_entries
from homeassistant.components.govee_light_local.const import (
    CLEANUP_TIMEOUT,
    CLEANUP_WAIT_TIMEOUT,
    DOMAIN,
    SCAN_INTERVAL,
)
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    DISABLED_NETWORK_ADAPTERS,
    answer_scans,
    create_device,
    create_entry,
    create_legacy_entry,
    scan_reply,
    setup_light,
)


def _register_legacy_light(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    device: GoveeDevice,
) -> er.RegistryEntry:
    """Register a lamp the way the entry for every lamp had set it up."""
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device.fingerprint)},
        name=device.sku,
        model_id=device.sku,
    )
    return entity_registry.async_get_or_create(
        LIGHT_DOMAIN,
        DOMAIN,
        device.fingerprint,
        config_entry=entry,
        device_id=device_entry.id,
        suggested_object_id=f"my_{device.sku}",
    )


NEW_LAMP_FLOWS = [(config_entries.SOURCE_INTEGRATION_DISCOVERY, "new_lamp")]


def _flows_in_progress(hass: HomeAssistant) -> list[tuple[str, str]]:
    """Return the source and unique ID of the flows in progress."""
    return [
        (flow["context"]["source"], flow["context"]["unique_id"])
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    ]


async def test_setup_without_listening_addresses(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test setup is retried when no enabled adapter has an IPv4 address."""
    config_entry = create_entry(hass, create_device(mock_govee_api))

    with patch(
        "homeassistant.components.network.async_get_adapters",
        return_value=DISABLED_NETWORK_ADAPTERS,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert (
        config_entry.reason
        == "No enabled network adapter has an IPv4 address to listen on"
    )
    mock_govee_api.start.assert_not_awaited()


@pytest.mark.usefixtures("mock_network_adapters", "mock_stuck_cleanup")
async def test_unload_waits_for_delayed_cleanup(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unloading keeps waiting for a cleanup that completes late."""

    entry, _ = await setup_light(hass, mock_govee_api)

    unload_task = hass.async_create_task(
        hass.config_entries.async_unload(entry.entry_id)
    )
    await asyncio.sleep(0)
    assert not unload_task.done()

    # Two seconds in: inside the cleanup wait window, so unload is still pending.
    freezer.tick(2)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert not unload_task.done()

    mock_govee_api.cleanup.return_value.set()
    assert await unload_task

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    assert "Timed out waiting for port" not in caplog.text


@pytest.mark.usefixtures("mock_network_adapters", "mock_stuck_cleanup")
async def test_unload_warns_when_port_not_released(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a controller that never closes its sockets does not wedge the unload."""

    entry, _ = await setup_light(hass, mock_govee_api)

    unload_task = hass.async_create_task(
        hass.config_entries.async_unload(entry.entry_id)
    )
    await asyncio.sleep(0)

    freezer.tick(CLEANUP_WAIT_TIMEOUT + 1)
    await asyncio.sleep(0)
    assert await unload_task
    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    assert "Timed out waiting for port 4002 to be released" in caplog.text


async def test_controller_is_shared_between_entries(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test the controller starts for the first lamp and stops after the last."""

    entry, _ = await setup_light(hass, mock_govee_api)
    other_entry, other_device = await setup_light(
        hass, mock_govee_api, ip="192.168.1.101", fingerprint="other", sku="H615B"
    )

    mock_govee_api.start.assert_awaited_once()
    assert entry.runtime_data.coordinator is other_entry.runtime_data.coordinator

    assert await hass.config_entries.async_unload(other_entry.entry_id)
    await hass.async_block_till_done()

    # The unloaded lamp is no longer tracked, the other one still is.
    mock_govee_api.remove_device.assert_called_once_with(other_device)
    mock_govee_api.cleanup.assert_not_called()
    assert hass.states.get("light.h615a").state == STATE_OFF

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    mock_govee_api.cleanup.assert_called_once_with(timeout=CLEANUP_TIMEOUT)


async def test_ip_address_change_is_stored(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test a set up lamp answering from a new address updates its entry."""

    entry, device = await setup_light(hass, mock_govee_api)

    device.update_ip("192.168.1.150")
    scan_reply(mock_govee_api, device)
    await hass.async_block_till_done()

    assert entry.data == {CONF_IP_ADDRESS: "192.168.1.150"}
    # The library already follows the lamp, so nothing is reloaded.
    mock_govee_api.start.assert_awaited_once()
    assert entry.state is config_entries.ConfigEntryState.LOADED


async def test_setup_stores_new_ip_address(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test a lamp found at another address than the stored one is set up."""

    device = create_device(mock_govee_api)
    entry = create_entry(hass, device)
    device.update_ip("192.168.1.150")
    answer_scans(mock_govee_api, device)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.data == {CONF_IP_ADDRESS: "192.168.1.150"}
    # The probe of the address it no longer has is dropped.
    mock_govee_api.remove_device_from_discovery_queue.assert_called_once_with(
        "192.168.1.100"
    )


async def test_retrying_entry_recovers_when_lamp_answers(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test a lamp that was offline is set up as soon as a scan hears it."""

    await setup_light(hass, mock_govee_api)
    offline_device = create_device(
        mock_govee_api, ip="192.168.1.101", fingerprint="offline", sku="H615B"
    )
    offline_entry = create_entry(hass, offline_device)

    await hass.config_entries.async_setup(offline_entry.entry_id)
    assert offline_entry.state is config_entries.ConfigEntryState.SETUP_RETRY

    # It comes back with another address, heard through the other lamp's controller.
    offline_device.update_ip("192.168.1.151")
    answer_scans(mock_govee_api, offline_device)
    scan_reply(mock_govee_api, offline_device)
    await hass.async_block_till_done()

    assert offline_entry.state is config_entries.ConfigEntryState.LOADED
    assert offline_entry.data == {CONF_IP_ADDRESS: "192.168.1.151"}
    assert hass.states.get("light.h615b").state == STATE_OFF
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_unknown_lamp_starts_discovery_flow(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test a lamp without an entry is offered to the user once."""

    await setup_light(hass, mock_govee_api)
    new_device = create_device(
        mock_govee_api, ip="192.168.1.101", fingerprint="new_lamp", sku="H615B"
    )

    scan_reply(mock_govee_api, new_device)
    # A second reply does not start a second flow.
    scan_reply(mock_govee_api, new_device)
    await hass.async_block_till_done()

    assert _flows_in_progress(hass) == NEW_LAMP_FLOWS


@pytest.mark.parametrize(
    ("source", "disabled_by"),
    [
        pytest.param(config_entries.SOURCE_IGNORE, None, id="ignored"),
        pytest.param(
            config_entries.SOURCE_USER,
            config_entries.ConfigEntryDisabler.USER,
            id="disabled",
        ),
    ],
)
async def test_ignored_or_disabled_lamp_is_left_alone(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    source: str,
    disabled_by: config_entries.ConfigEntryDisabler | None,
) -> None:
    """Test a lamp the user ignored or disabled is only offered once that ends."""

    await setup_light(hass, mock_govee_api)
    device = create_device(
        mock_govee_api, ip="192.168.1.101", fingerprint="unwanted", sku="H615B"
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=device.fingerprint,
        source=source,
        disabled_by=disabled_by,
        data={CONF_IP_ADDRESS: device.ip},
    )
    entry.add_to_hass(hass)

    assert not scan_reply(mock_govee_api, device)
    await hass.async_block_till_done()

    assert device not in mock_govee_api.devices
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    assert await hass.config_entries.async_remove(entry.entry_id)
    scan_reply(mock_govee_api, device)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["unique_id"] for flow in flows] == ["unwanted"]


async def test_cancelled_start_releases_port(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test the controller is cleaned up when its start is cancelled."""

    entry = create_entry(hass, create_device(mock_govee_api))
    mock_govee_api.start.side_effect = asyncio.CancelledError

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    mock_govee_api.cleanup.assert_called_once_with(timeout=CLEANUP_TIMEOUT)


@pytest.mark.parametrize(
    ("polling_disabled", "answering", "polled"),
    [
        pytest.param([True], [True], False, id="only_lamp_disabled"),
        pytest.param([True, True], [True, True], False, id="every_lamp_disabled"),
        pytest.param([True, False], [True, True], True, id="one_lamp_still_polling"),
        pytest.param([True, False], [True, False], False, id="polling_lamp_not_set_up"),
    ],
)
async def test_polling_preference(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
    polling_disabled: list[bool],
    answering: list[bool],
    polled: bool,
) -> None:
    """Test the shared controller stops polling once every set up lamp has it disabled."""

    for index, (disabled, answers) in enumerate(
        zip(polling_disabled, answering, strict=True)
    ):
        device = create_device(
            mock_govee_api, ip=f"192.168.1.{100 + index}", fingerprint=f"lamp_{index}"
        )
        answer_scans(mock_govee_api, *[device][: int(answers)])
        entry = create_entry(hass, device)
        hass.config_entries.async_update_entry(entry, pref_disable_polling=disabled)
        assert await hass.config_entries.async_setup(entry.entry_id) is answers
    await hass.async_block_till_done()
    mock_govee_api.send_update_message.reset_mock()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_govee_api.send_update_message.called is polled


async def test_polling_stops_when_last_polling_lamp_is_unloaded(
    hass: HomeAssistant, mock_govee_api: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test unloading the only polling lamp stops the shared controller's polling."""

    disabled_entry, _ = await setup_light(hass, mock_govee_api)
    hass.config_entries.async_update_entry(disabled_entry, pref_disable_polling=True)
    polling_entry, _ = await setup_light(
        hass, mock_govee_api, ip="192.168.1.101", fingerprint="polling", sku="H615B"
    )

    assert await hass.config_entries.async_unload(polling_entry.entry_id)
    # The refresh that was already scheduled still runs; none follows it.
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_govee_api.send_update_message.reset_mock()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_govee_api.send_update_message.assert_not_called()


async def test_legacy_entry_is_split_per_lamp(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the entry for every lamp becomes one entry per lamp.

    Every lamp it had set up gets its own entry and keeps its registry
    entries, also a lamp that is offline. A lamp it never set up is offered
    like any newly discovered one.
    """

    legacy_entry = create_legacy_entry(hass)
    first = create_device(mock_govee_api, fingerprint="first")
    second = create_device(
        mock_govee_api, ip="192.168.1.101", fingerprint="second", sku="H615B"
    )
    offline = create_device(
        mock_govee_api, ip="192.168.1.102", fingerprint="offline", sku="H615C"
    )
    entity_ids = {
        device.fingerprint: _register_legacy_light(
            device_registry, entity_registry, legacy_entry, device
        ).entity_id
        for device in (first, second, offline)
    }
    # An entity another integration attached to the lamp stays with it.
    helper_entry = MockConfigEntry(domain="helper")
    helper_entry.add_to_hass(hass)
    second_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "second"), legacy_entry.entry_id
    )
    assert second_device is not None
    helper_entity = entity_registry.async_get_or_create(
        "sensor",
        "helper",
        "second_helper",
        config_entry=helper_entry,
        device_id=second_device.id,
    )
    hass.config_entries.async_update_entry(legacy_entry, pref_disable_polling=True)
    new_device = create_device(
        mock_govee_api, ip="192.168.1.103", fingerprint="new_lamp", sku="H615D"
    )
    # The new lamp answers first, and is still not the one the entry turns into.
    answer_scans(mock_govee_api, new_device, first, second)

    assert await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()

    # Every lamp keeps the polling preference of the entry it came from.
    assert all(
        entry.pref_disable_polling
        for entry in hass.config_entries.async_entries(DOMAIN)
    )
    assert legacy_entry.version == 2
    assert legacy_entry.unique_id == "first"
    assert legacy_entry.title == "H615A"
    assert legacy_entry.data == {CONF_IP_ADDRESS: "192.168.1.100"}

    second_entry = hass.config_entries.async_entry_for_domain_unique_id(
        DOMAIN, "second"
    )
    assert second_entry is not None
    assert second_entry.state is config_entries.ConfigEntryState.LOADED
    assert second_entry.title == "H615B"
    assert second_entry.data == {CONF_IP_ADDRESS: "192.168.1.101"}

    offline_entry = hass.config_entries.async_entry_for_domain_unique_id(
        DOMAIN, "offline"
    )
    assert offline_entry is not None
    assert offline_entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert offline_entry.title == "H615C"
    assert offline_entry.data == {CONF_IP_ADDRESS: None}

    mock_govee_api.start.assert_awaited_once()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 3
    assert _flows_in_progress(hass) == NEW_LAMP_FLOWS

    for fingerprint, entry in (
        ("first", legacy_entry),
        ("second", second_entry),
        ("offline", offline_entry),
    ):
        entity_entry = entity_registry.async_get(entity_ids[fingerprint])
        assert entity_entry is not None
        assert entity_entry.config_entry_id == entry.entry_id
        assert dr.async_entries_for_config_entry(device_registry, entry.entry_id) == [
            device_registry.async_get_device_by_identifier(
                (DOMAIN, fingerprint), entry.entry_id
            )
        ]
    assert hass.states.get(entity_ids["first"]).state == STATE_OFF
    assert hass.states.get(entity_ids["second"]).state == STATE_OFF
    helper_entity = entity_registry.async_get(helper_entity.entity_id)
    assert helper_entity is not None
    assert helper_entity.config_entry_id == helper_entry.entry_id

    # The offline lamp comes back and is set up without a prompt.
    answer_scans(mock_govee_api, offline)
    scan_reply(mock_govee_api, offline)
    await hass.async_block_till_done()

    assert offline_entry.state is config_entries.ConfigEntryState.LOADED
    assert offline_entry.data == {CONF_IP_ADDRESS: "192.168.1.102"}
    assert hass.states.get(entity_ids["offline"]).state == STATE_OFF
    assert _flows_in_progress(hass) == NEW_LAMP_FLOWS


async def test_legacy_entry_waits_for_a_lamp_it_had_set_up(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the legacy entry does not take a new lamp while its own are offline."""

    legacy_entry = create_legacy_entry(hass)
    entity_entry = _register_legacy_light(
        device_registry, entity_registry, legacy_entry, create_device(mock_govee_api)
    )
    answer_scans(
        mock_govee_api,
        create_device(
            mock_govee_api, ip="192.168.1.101", fingerprint="new_lamp", sku="H615B"
        ),
    )

    await hass.config_entries.async_setup(legacy_entry.entry_id)
    await hass.async_block_till_done()

    assert legacy_entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert legacy_entry.reason == "No devices found on the network"
    assert legacy_entry.unique_id == DOMAIN
    assert entity_registry.async_get(entity_entry.entity_id) is not None
    mock_govee_api.cleanup.assert_called_once_with(timeout=CLEANUP_TIMEOUT)
    # The new lamp is offered like any newly discovered one.
    assert _flows_in_progress(hass) == NEW_LAMP_FLOWS


async def test_pending_legacy_entry_does_not_hold_back_other_lamps(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a new lamp is offered while the legacy entry waits for its own lamps."""

    await setup_light(hass, mock_govee_api)
    legacy_entry = create_legacy_entry(hass)
    _register_legacy_light(
        device_registry,
        entity_registry,
        legacy_entry,
        create_device(mock_govee_api, ip="192.168.1.102", fingerprint="offline"),
    )
    await hass.config_entries.async_setup(legacy_entry.entry_id)
    assert legacy_entry.state is config_entries.ConfigEntryState.SETUP_RETRY

    scan_reply(
        mock_govee_api,
        create_device(
            mock_govee_api, ip="192.168.1.101", fingerprint="new_lamp", sku="H615B"
        ),
    )
    await hass.async_block_till_done()

    assert _flows_in_progress(hass) == NEW_LAMP_FLOWS


async def test_user_scan_leaves_lamps_to_the_pending_legacy_entry(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a scan started by the user does not split the legacy entry's lamps."""

    legacy_entry = create_legacy_entry(hass)
    device = create_device(mock_govee_api)
    entity_entry = _register_legacy_light(
        device_registry, entity_registry, legacy_entry, device
    )
    await hass.config_entries.async_setup(legacy_entry.entry_id)
    assert legacy_entry.state is config_entries.ConfigEntryState.SETUP_RETRY

    answer_scans(mock_govee_api, device)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    # Nothing is on offer, so the flow does not claim a discovery started.
    assert result["reason"] == "no_devices_found"
    assert hass.config_entries.async_entries(DOMAIN) == [legacy_entry]
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    entity_entry = entity_registry.async_get(entity_entry.entity_id)
    assert entity_entry is not None
    assert entity_entry.config_entry_id == legacy_entry.entry_id


async def test_disabled_legacy_entry_keeps_its_lamps(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a disabled legacy entry's lamps stay disabled and block no other lamp."""

    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        disabled_by=config_entries.ConfigEntryDisabler.USER,
    )
    legacy_entry.add_to_hass(hass)
    owned = create_device(
        mock_govee_api, ip="192.168.1.101", fingerprint="owned", sku="H615B"
    )
    _register_legacy_light(device_registry, entity_registry, legacy_entry, owned)
    new_device = create_device(
        mock_govee_api, ip="192.168.1.102", fingerprint="new_lamp", sku="H615C"
    )
    await setup_light(hass, mock_govee_api)

    assert not scan_reply(mock_govee_api, owned)
    scan_reply(mock_govee_api, new_device)
    await hass.async_block_till_done()

    assert owned not in mock_govee_api.devices
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert _flows_in_progress(hass) == NEW_LAMP_FLOWS

    # Once the disabled entry is gone, its lamp is offered like a new one.
    assert await hass.config_entries.async_remove(legacy_entry.entry_id)
    scan_reply(mock_govee_api, owned)
    await hass.async_block_till_done()

    assert (
        config_entries.SOURCE_INTEGRATION_DISCOVERY,
        "owned",
    ) in _flows_in_progress(hass)


async def test_scan_waits_for_late_replies(
    hass: HomeAssistant, mock_govee_api: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a legacy entry without lamps takes one that answers late in the scan."""

    legacy_entry = create_legacy_entry(hass)
    device = create_device(mock_govee_api)
    scan_sent = asyncio.Event()

    def send_discovery_message() -> None:
        hass.loop.call_soon(scan_reply, mock_govee_api, device)
        scan_sent.set()

    mock_govee_api.send_discovery_message.side_effect = send_discovery_message

    with patch(
        "homeassistant.components.govee_light_local.coordinator.DISCOVERY_TIMEOUT", 5
    ):
        setup_task = hass.async_create_task(
            hass.config_entries.async_setup(legacy_entry.entry_id)
        )
        await scan_sent.wait()
        assert not setup_task.done()

        # The reply arrives while the scan is still collecting them.
        freezer.tick(5)
        async_fire_time_changed(hass)
        assert await setup_task
    await hass.async_block_till_done()

    assert legacy_entry.unique_id == "asdawdqwdqwd"
    assert hass.states.get("light.h615a").state == STATE_OFF
    # The lamp the entry took is not offered as well.
    assert not _flows_in_progress(hass)


async def test_remove_leftover_device(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test only a lamp left over from the legacy entry can be removed by hand."""

    assert await async_setup_component(hass, "config", {})
    entry, device = await setup_light(hass, mock_govee_api)
    own_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device.fingerprint), entry.entry_id
    )
    assert own_device is not None
    leftover_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "leftover")}
    )

    client = await hass_ws_client(hass)

    response = await client.remove_device(own_device.id)
    assert not response["success"]
    assert device_registry.async_get(own_device.id) is not None

    response = await client.remove_device(leftover_device.id)
    assert response["success"]
    assert device_registry.async_get(leftover_device.id) is None
