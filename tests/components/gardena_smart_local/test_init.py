"""Tests for the GARDENA smart local integration setup."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from gardena_smart_local_api.devices import DeviceMap
from gardena_smart_local_api.devices.irrigation import Gen2WaterControl
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.gardena_smart_local import (
    _async_exclude_and_report_failure,
)
from homeassistant.components.gardena_smart_local.const import (
    CONF_FINGERPRINT,
    DEFAULT_PORT,
    DEFAULT_VALVE_DURATION_MINUTES,
    DOMAIN,
)
from homeassistant.components.gardena_smart_local.coordinator import (
    GardenaSmartLocalCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
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


async def test_exclude_success_creates_no_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """A confirmed exclusion does not warn the user."""
    coordinator = MagicMock()
    coordinator.async_exclude_device = AsyncMock(return_value=True)

    await _async_exclude_and_report_failure(hass, coordinator, "dev-1")

    coordinator.async_exclude_device.assert_awaited_once_with("dev-1")
    assert issue_registry.async_get_issue(DOMAIN, "exclude_failed_dev-1") is None


async def test_exclude_retry_success_clears_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Removing a still-paired device again resolves the earlier warning."""
    coordinator = MagicMock()
    coordinator.async_exclude_device = AsyncMock(return_value=False)
    await _async_exclude_and_report_failure(hass, coordinator, "dev-1")
    assert issue_registry.async_get_issue(DOMAIN, "exclude_failed_dev-1")

    coordinator.async_exclude_device = AsyncMock(return_value=True)
    await _async_exclude_and_report_failure(hass, coordinator, "dev-1")

    assert issue_registry.async_get_issue(DOMAIN, "exclude_failed_dev-1") is None


async def test_exclude_failure_creates_repair_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """A gateway that does not confirm exclusion is surfaced to the user."""
    coordinator = MagicMock()
    coordinator.async_exclude_device = AsyncMock(return_value=False)

    await _async_exclude_and_report_failure(hass, coordinator, "dev-1")

    issue = issue_registry.async_get_issue(DOMAIN, "exclude_failed_dev-1")
    assert issue is not None
    assert issue.translation_key == "exclude_failed"
    assert issue.translation_placeholders == {"device_id": "dev-1"}


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
async def setup_entry(
    hass: HomeAssistant, mock_device: MagicMock, mock_exclude: AsyncMock
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
        patch.object(
            GardenaSmartLocalCoordinator, "send_request", AsyncMock(return_value=[])
        ),
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
    entity_registry: er.EntityRegistry,
) -> None:
    """The integration's own open_valve action forwards the validated duration."""
    entity_id = await _valve_entity_id(entity_registry)

    await hass.services.async_call(
        DOMAIN, "open_valve", {"entity_id": entity_id, "duration": 120}, blocking=True
    )

    mock_device.build_open_valve_obj.assert_called_once_with(0, 120)
    setup_entry.runtime_data.send_request.assert_awaited_once()


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
