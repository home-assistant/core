"""Tests for the GARDENA smart local integration setup."""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from gardena_smart_local_api.client import DiscoveryError, GatewayClient
from gardena_smart_local_api.devices import DeviceMap
from gardena_smart_local_api.devices.irrigation import Gen2WaterControl
from gardena_smart_local_api.messages import IngressMessageList
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.gardena_smart_local import (
    _async_exclude_and_report_failure,
)
from homeassistant.components.gardena_smart_local.const import (
    CONF_FINGERPRINT,
    CONF_KNOWN_DEVICES,
    CONF_PENDING_EXCLUSIONS,
    DEFAULT_PORT,
    DEFAULT_VALVE_DURATION_MINUTES,
    DOMAIN,
)
from homeassistant.components.gardena_smart_local.coordinator import (
    GardenaSmartLocalCoordinator,
)
from homeassistant.config_entries import (
    ConfigEntryDisabler,
    ConfigEntryState,
    ConfigSubentryData,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

MOCK_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_PASSWORD: "testpassword",
    CONF_FINGERPRINT: "ab" * 32,
}


async def test_setup_rejected_password_is_auth_error(hass: HomeAssistant) -> None:
    """A gateway 401 during setup fails the entry instead of retrying forever."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with patch(
        "aiohttp.ClientSession.ws_connect",
        side_effect=aiohttp.WSServerHandshakeError(
            request_info=MagicMock(), history=(), status=401, message="Unauthorized"
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_changed_certificate_is_error(hass: HomeAssistant) -> None:
    """A gateway presenting another certificate fails the entry until reconfigured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with patch(
        "aiohttp.ClientSession.ws_connect",
        side_effect=aiohttp.ServerFingerprintMismatch(
            bytes.fromhex(MOCK_DATA[CONF_FINGERPRINT]), b"\x00" * 32, "host", 8443
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_unexpected_error_is_not_retried(hass: HomeAssistant) -> None:
    """A defect during setup fails the entry instead of retrying forever."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with patch(
        "aiohttp.ClientSession.ws_connect", side_effect=RuntimeError("parser bug")
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_failed_discovery_is_retried(hass: HomeAssistant) -> None:
    """A gateway that answers discovery with an error keeps the entry retrying."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with patch.object(
        GatewayClient,
        "connect",
        AsyncMock(
            side_effect=DiscoveryError(
                "The discovery failed", IngressMessageList([]), DeviceMap({})
            )
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_gateway_timeout_is_retried(hass: HomeAssistant) -> None:
    """A gateway that does not answer in time keeps the entry in retry state."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with patch("aiohttp.ClientSession.ws_connect", side_effect=TimeoutError):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_gateway_offline_is_retried(hass: HomeAssistant) -> None:
    """A connection failure during setup keeps the entry in retry state."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with patch(
        "aiohttp.ClientSession.ws_connect",
        side_effect=aiohttp.ClientConnectionError("Connection refused"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.fixture
def coordinator(hass: HomeAssistant) -> MagicMock:
    """Return a coordinator stand-in that belongs to a registered entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)
    stand_in = MagicMock()
    stand_in.config_entry = entry
    return stand_in


async def test_exclude_success_creates_no_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, coordinator: MagicMock
) -> None:
    """A confirmed exclusion does not warn the user."""
    coordinator.async_exclude_device = AsyncMock(return_value=True)

    await _async_exclude_and_report_failure(hass, coordinator, "dev-1")

    coordinator.async_exclude_device.assert_awaited_once_with("dev-1")
    assert issue_registry.async_get_issue(DOMAIN, "exclude_failed_dev-1") is None


async def test_exclude_retry_success_clears_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, coordinator: MagicMock
) -> None:
    """Removing a still-paired device again resolves the earlier warning."""
    coordinator.async_exclude_device = AsyncMock(return_value=False)
    await _async_exclude_and_report_failure(hass, coordinator, "dev-1")
    assert issue_registry.async_get_issue(DOMAIN, "exclude_failed_dev-1")

    coordinator.async_exclude_device = AsyncMock(return_value=True)
    await _async_exclude_and_report_failure(hass, coordinator, "dev-1")

    assert issue_registry.async_get_issue(DOMAIN, "exclude_failed_dev-1") is None


async def test_exclude_failure_creates_repair_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, coordinator: MagicMock
) -> None:
    """A gateway that does not confirm exclusion is surfaced to the user."""
    coordinator.async_exclude_device = AsyncMock(return_value=False)

    await _async_exclude_and_report_failure(hass, coordinator, "dev-1")

    issue = issue_registry.async_get_issue(DOMAIN, "exclude_failed_dev-1")
    assert issue is not None
    assert issue.translation_key == "exclude_failed"
    assert issue.translation_placeholders == {"device_id": "dev-1"}
    assert issue.config_entry_id == coordinator.config_entry.entry_id


async def test_removing_the_gateway_clears_its_exclusion_warning(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, coordinator: MagicMock
) -> None:
    """A warning about a device of a deleted gateway is no longer actionable."""
    coordinator.async_exclude_device = AsyncMock(return_value=False)
    await _async_exclude_and_report_failure(hass, coordinator, "dev-1")

    await hass.config_entries.async_remove(coordinator.config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, "exclude_failed_dev-1") is None


@pytest.fixture
def mock_device() -> MagicMock:
    """Return a supported single-valve device."""
    device = MagicMock(spec=Gen2WaterControl)
    device.id = "dev-1"
    device.serial_number = "00000001"
    device.software_version = "1.0.0"
    device.hardware_version = "1.0"
    device.model_definition = MagicMock()
    device.model_definition.name = "Smart Water Control"
    device.model_definition.model_number = "1"
    device.valve_ids = [0]
    device.is_online = True
    device.is_valve_open.return_value = False
    device.build_open_valve_obj.return_value = "OPEN_OBJ"
    return device


@pytest.fixture
def mock_exclude() -> AsyncMock:
    """Return the mock standing in for the gateway's device exclusion."""
    return AsyncMock(return_value=True)


@pytest.fixture
def mock_send_request() -> AsyncMock:
    """Return the mock standing in for the gateway confirming a command."""
    return AsyncMock(return_value=IngressMessageList([]))


@pytest.fixture
async def setup_entry(
    hass: HomeAssistant,
    mock_device: MagicMock,
    mock_exclude: AsyncMock,
    mock_send_request: AsyncMock,
) -> AsyncGenerator[MockConfigEntry]:
    """Set up an entry whose gateway reports one valve device."""

    async def _connect(self: GardenaSmartLocalCoordinator) -> None:
        self.async_set_updated_data(DeviceMap({mock_device.id: mock_device}))

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with (
        patch.object(GardenaSmartLocalCoordinator, "async_connect", _connect),
        patch.object(GardenaSmartLocalCoordinator, "async_disconnect", AsyncMock()),
        patch.object(GardenaSmartLocalCoordinator, "connected", True),
        patch.object(GatewayClient, "send_request", mock_send_request),
        patch.object(
            GardenaSmartLocalCoordinator, "async_exclude_device", mock_exclude
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry


async def test_setup_and_unload(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Setup stores the coordinator, adds the valve, and unload stops the gateway link."""
    assert setup_entry.state is ConfigEntryState.LOADED
    coordinator = setup_entry.runtime_data
    assert isinstance(coordinator, GardenaSmartLocalCoordinator)
    entity_id = entity_registry.async_get_entity_id("valve", DOMAIN, "dev-1_valve_0")
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "closed"

    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()

    assert setup_entry.state is ConfigEntryState.NOT_LOADED
    coordinator.async_disconnect.assert_awaited_once()


async def test_device_subentry_created_for_discovered_device(
    setup_entry: MockConfigEntry,
) -> None:
    """A discovered supported device gets a subentry, once."""
    subentries = list(setup_entry.subentries.values())
    assert len(subentries) == 1
    assert subentries[0].data == {"device_id": "dev-1"}
    assert subentries[0].unique_id == "dev-1"

    setup_entry.runtime_data.async_update_listeners()

    assert len(setup_entry.subentries) == 1


async def test_removing_subentry_excludes_device(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    mock_exclude: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Removing the device subentry excludes the device from the gateway."""
    subentry_id = next(iter(setup_entry.subentries))

    hass.config_entries.async_remove_subentry(setup_entry, subentry_id)
    await hass.async_block_till_done()

    mock_exclude.assert_awaited_once_with("dev-1")
    assert issue_registry.async_get_issue(DOMAIN, "exclude_failed_dev-1") is None
    assert setup_entry.data[CONF_PENDING_EXCLUSIONS] == []
    assert setup_entry.data[CONF_KNOWN_DEVICES] == []


async def test_devices_with_a_subentry_are_stored(setup_entry: MockConfigEntry) -> None:
    """The entry remembers its devices, to notice removals while not set up."""
    assert setup_entry.data[CONF_KNOWN_DEVICES] == ["dev-1"]


async def test_device_removed_while_disabled_is_excluded_once_enabled(
    hass: HomeAssistant, mock_device: MagicMock, mock_exclude: AsyncMock
) -> None:
    """A subentry deleted before the integration is set up is still noticed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_DATA, CONF_KNOWN_DEVICES: ["dev-1"]},
        disabled_by=ConfigEntryDisabler.USER,
        subentries_data=[
            ConfigSubentryData(
                data={"device_id": "dev-1"},
                subentry_type="device",
                title="Smart Water Control 00000001",
                unique_id="dev-1",
            )
        ],
    )
    entry.add_to_hass(hass)
    hass.config_entries.async_remove_subentry(entry, next(iter(entry.subentries)))

    async def _connect(self: GardenaSmartLocalCoordinator) -> None:
        self.async_set_updated_data(DeviceMap({mock_device.id: mock_device}))

    with (
        patch.object(GardenaSmartLocalCoordinator, "async_connect", _connect),
        patch.object(GardenaSmartLocalCoordinator, "async_disconnect", AsyncMock()),
        patch.object(
            GardenaSmartLocalCoordinator, "async_exclude_device", mock_exclude
        ),
    ):
        await hass.config_entries.async_set_disabled_by(entry.entry_id, None)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    mock_exclude.assert_awaited_once_with("dev-1")
    assert not entry.subentries
    assert entry.data[CONF_KNOWN_DEVICES] == []
    assert entry.data[CONF_PENDING_EXCLUSIONS] == []


async def test_exclusion_interrupted_by_unload_runs_on_the_next_setup(
    hass: HomeAssistant, setup_entry: MockConfigEntry, mock_exclude: AsyncMock
) -> None:
    """The removal is stored before the gateway confirms the exclusion."""
    started = asyncio.Event()

    async def _exclude(_device_id: str) -> bool:
        started.set()
        await asyncio.Event().wait()
        return True

    mock_exclude.side_effect = _exclude
    hass.config_entries.async_remove_subentry(
        setup_entry, next(iter(setup_entry.subentries))
    )
    await started.wait()

    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()

    assert setup_entry.data[CONF_PENDING_EXCLUSIONS] == ["dev-1"]


async def test_removing_subentry_reports_failed_exclusion(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    mock_exclude: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A rejected exclusion leaves a repair issue after the subentry is gone."""
    mock_exclude.return_value = False
    subentry_id = next(iter(setup_entry.subentries))

    hass.config_entries.async_remove_subentry(setup_entry, subentry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, "exclude_failed_dev-1") is not None


async def _valve_entity_id(entity_registry: er.EntityRegistry) -> str:
    entity_id = entity_registry.async_get_entity_id("valve", DOMAIN, "dev-1_valve_0")
    assert entity_id is not None
    return entity_id


async def test_open_valve_action_passes_duration(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    mock_device: MagicMock,
    mock_send_request: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """The integration's own open_valve action forwards the validated duration."""
    entity_id = await _valve_entity_id(entity_registry)

    await hass.services.async_call(
        DOMAIN, "open_valve", {"entity_id": entity_id, "duration": 120}, blocking=True
    )

    mock_device.build_open_valve_obj.assert_called_once_with(0, 120)
    mock_send_request.assert_awaited_once()


async def test_open_valve_action_defaults_duration(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    mock_device: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Without a duration the default of 30 minutes is used."""
    entity_id = await _valve_entity_id(entity_registry)

    await hass.services.async_call(
        DOMAIN, "open_valve", {"entity_id": entity_id}, blocking=True
    )

    mock_device.build_open_valve_obj.assert_called_once_with(
        0, DEFAULT_VALVE_DURATION_MINUTES * 60
    )


@pytest.mark.parametrize("duration", [59, 10801])
async def test_open_valve_action_rejects_out_of_range_duration(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    mock_device: MagicMock,
    entity_registry: er.EntityRegistry,
    duration: int,
) -> None:
    """Durations outside the supported range never reach the gateway."""
    entity_id = await _valve_entity_id(entity_registry)

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "open_valve",
            {"entity_id": entity_id, "duration": duration},
            blocking=True,
        )

    mock_device.build_open_valve_obj.assert_not_called()


async def test_open_valve_action_ignores_foreign_entities(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """The action only targets this integration's valves."""
    hass.states.async_set("valve.other", "closed")

    await hass.services.async_call(
        DOMAIN, "open_valve", {"entity_id": "valve.other"}, blocking=True
    )

    mock_device.build_open_valve_obj.assert_not_called()


async def test_standard_valve_services_still_work(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    mock_device: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """The custom action does not shadow the built-in valve services."""
    entity_id = await _valve_entity_id(entity_registry)

    await hass.services.async_call(
        "valve", "open_valve", {"entity_id": entity_id}, blocking=True
    )

    mock_device.build_open_valve_obj.assert_called_once_with(
        0, DEFAULT_VALVE_DURATION_MINUTES * 60
    )


async def test_unsupported_device_gets_no_subentry_or_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_exclude: AsyncMock,
) -> None:
    """Devices without an entity in this integration are left alone."""
    sensor = MagicMock()
    sensor.id = "sensor-1"

    async def _connect(self: GardenaSmartLocalCoordinator) -> None:
        self.async_set_updated_data(DeviceMap.model_construct({sensor.id: sensor}))

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with (
        patch.object(GardenaSmartLocalCoordinator, "async_connect", _connect),
        patch.object(GardenaSmartLocalCoordinator, "async_disconnect", AsyncMock()),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert not entry.subentries
    assert not er.async_entries_for_config_entry(entity_registry, entry.entry_id)


async def test_firmware_update_refreshes_device_registry(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    mock_device: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A new firmware version reported by the gateway reaches the device registry."""
    [device_entry] = dr.async_entries_for_config_entry(
        device_registry, setup_entry.entry_id
    )
    assert device_entry.sw_version == "1.0.0"

    mock_device.software_version = "2.0.0"
    setup_entry.runtime_data.async_set_updated_data(setup_entry.runtime_data.data)
    await hass.async_block_till_done()

    [device_entry] = dr.async_entries_for_config_entry(
        device_registry, setup_entry.entry_id
    )
    assert device_entry.sw_version == "2.0.0"


@pytest.mark.parametrize(
    "connect_error",
    [TimeoutError("no answer"), asyncio.CancelledError()],
    ids=["failed", "cancelled"],
)
async def test_setup_that_does_not_connect_stops_the_connection(
    hass: HomeAssistant, connect_error: BaseException
) -> None:
    """A setup that fails or is cancelled while connecting leaves nothing running."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with (
        patch.object(
            GardenaSmartLocalCoordinator, "async_connect", side_effect=connect_error
        ),
        patch.object(
            GardenaSmartLocalCoordinator, "async_disconnect", AsyncMock()
        ) as disconnect,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is not ConfigEntryState.LOADED
    disconnect.assert_awaited_once()


async def test_setup_that_fails_after_connecting_stops_the_connection(
    hass: HomeAssistant,
) -> None:
    """A platform that cannot be set up does not leave the connection running."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)

    with (
        patch.object(GardenaSmartLocalCoordinator, "async_connect", AsyncMock()),
        patch.object(
            GardenaSmartLocalCoordinator, "async_disconnect", AsyncMock()
        ) as disconnect,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(side_effect=RuntimeError("platform failed")),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    disconnect.assert_awaited_once()


async def test_device_back_on_the_gateway_keeps_its_valve(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    mock_device: MagicMock,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A device that leaves the gateway and comes back reuses its entity."""
    coordinator = setup_entry.runtime_data
    entity_id = entity_registry.async_get_entity_id("valve", DOMAIN, "dev-1_valve_0")

    coordinator.async_set_updated_data(DeviceMap({}))
    coordinator.async_set_updated_data(DeviceMap({mock_device.id: mock_device}))
    await hass.async_block_till_done()

    assert "already exists" not in caplog.text
    assert hass.states.get(entity_id).state == "closed"


async def test_device_included_again_gets_its_valve_back(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    mock_device: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Removing the subentry removes the valve, and including the device adds it."""
    coordinator = setup_entry.runtime_data
    coordinator.async_set_updated_data(DeviceMap({}))
    hass.config_entries.async_remove_subentry(
        setup_entry, next(iter(setup_entry.subentries))
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get_entity_id("valve", DOMAIN, "dev-1_valve_0") is None

    coordinator.async_set_updated_data(DeviceMap({mock_device.id: mock_device}))
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id("valve", DOMAIN, "dev-1_valve_0")
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "closed"


async def test_commands_use_the_device_from_the_latest_discovery(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    mock_device: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A discovery that replaces the device object is used for the next command."""
    rediscovered = MagicMock(spec=Gen2WaterControl)
    rediscovered.configure_mock(
        id=mock_device.id,
        serial_number=mock_device.serial_number,
        software_version=mock_device.software_version,
        valve_ids=[0],
        is_online=True,
    )
    rediscovered.is_valve_open.return_value = False
    setup_entry.runtime_data.async_set_updated_data(
        DeviceMap({rediscovered.id: rediscovered})
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "valve",
        "open_valve",
        {"entity_id": await _valve_entity_id(entity_registry)},
        blocking=True,
    )

    rediscovered.build_open_valve_obj.assert_called_once()
    mock_device.build_open_valve_obj.assert_not_called()


async def test_device_removed_while_offline_is_excluded_on_the_next_setup(
    hass: HomeAssistant, mock_exclude: AsyncMock
) -> None:
    """A subentry removed while the gateway is unreachable is not forgotten."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_DATA,
        subentries_data=[
            ConfigSubentryData(
                data={"device_id": "dev-1"},
                subentry_type="device",
                title="Smart Water Control 00000001",
                unique_id="dev-1",
            )
        ],
    )
    entry.add_to_hass(hass)
    with (
        patch.object(
            GardenaSmartLocalCoordinator,
            "async_connect",
            AsyncMock(side_effect=TimeoutError("offline")),
        ),
        patch.object(GardenaSmartLocalCoordinator, "async_disconnect", AsyncMock()),
        patch.object(
            GardenaSmartLocalCoordinator, "async_exclude_device", mock_exclude
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_RETRY

        hass.config_entries.async_remove_subentry(entry, next(iter(entry.subentries)))
        await hass.async_block_till_done()

    mock_exclude.assert_not_awaited()
    assert entry.data[CONF_PENDING_EXCLUSIONS] == ["dev-1"]


async def _setup_with_pending_exclusion(
    hass: HomeAssistant, mock_device: MagicMock, mock_exclude: AsyncMock
) -> MockConfigEntry:
    async def _connect(self: GardenaSmartLocalCoordinator) -> None:
        self.async_set_updated_data(DeviceMap({mock_device.id: mock_device}))

    entry = MockConfigEntry(
        domain=DOMAIN, data={**MOCK_DATA, CONF_PENDING_EXCLUSIONS: ["dev-1"]}
    )
    entry.add_to_hass(hass)
    with (
        patch.object(GardenaSmartLocalCoordinator, "async_connect", _connect),
        patch.object(GardenaSmartLocalCoordinator, "async_disconnect", AsyncMock()),
        patch.object(
            GardenaSmartLocalCoordinator, "async_exclude_device", mock_exclude
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_exclude.assert_awaited_once_with("dev-1")
    assert entry.data[CONF_PENDING_EXCLUSIONS] == []
    return entry


async def test_pending_exclusion_runs_once_the_gateway_is_back(
    hass: HomeAssistant,
    mock_device: MagicMock,
    mock_exclude: AsyncMock,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The device is excluded after connecting, and gets no subentry or valve."""
    entry = await _setup_with_pending_exclusion(hass, mock_device, mock_exclude)

    assert issue_registry.async_get_issue(DOMAIN, "exclude_failed_dev-1") is None
    assert not entry.subentries
    assert entity_registry.async_get_entity_id("valve", DOMAIN, "dev-1_valve_0") is None


async def test_failed_pending_exclusion_gives_the_device_back(
    hass: HomeAssistant,
    mock_device: MagicMock,
    mock_exclude: AsyncMock,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A device still paired after a failed exclusion gets its subentry and valve."""
    mock_exclude.return_value = False

    entry = await _setup_with_pending_exclusion(hass, mock_device, mock_exclude)

    assert issue_registry.async_get_issue(DOMAIN, "exclude_failed_dev-1") is not None
    subentry_id = next(iter(entry.subentries))
    valve = entity_registry.async_get_entity_id("valve", DOMAIN, "dev-1_valve_0")
    assert entity_registry.async_get(valve).config_subentry_id == subentry_id


async def test_removing_the_entry_excludes_no_device(
    hass: HomeAssistant, setup_entry: MockConfigEntry, mock_exclude: AsyncMock
) -> None:
    """Deleting the whole gateway leaves its devices paired, unlike a subentry."""
    other = MockConfigEntry(domain="other_domain")
    other.add_to_hass(hass)
    hass.config_entries.async_update_entry(other, title="changed")

    await hass.config_entries.async_remove(setup_entry.entry_id)
    await hass.async_block_till_done()

    mock_exclude.assert_not_awaited()
