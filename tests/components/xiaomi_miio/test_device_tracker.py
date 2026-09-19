"""The tests for the xiaomi_miio device_tracker (Xiaomi Mi WiFi Repeater 2)."""

from collections.abc import Generator
from unittest.mock import MagicMock, Mock, patch

from construct.core import ChecksumError
from freezegun.api import FrozenDateTimeFactory
from miio import DeviceException
from miio.wifirepeater import WifiRepeaterStatus
import pytest

from homeassistant import config_entries
from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.xiaomi_miio import const
from homeassistant.components.xiaomi_miio.coordinator import UPDATE_INTERVAL
from homeassistant.components.xiaomi_miio.device_tracker import (
    XiaomiMiioRepeaterDevice,
    add_entities,
)
from homeassistant.components.xiaomi_miio.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import TEST_MAC

from tests.common import MockConfigEntry, async_fire_time_changed

TEST_HOST = "192.168.1.100"
TEST_TOKEN = "12345678901234567890123456789012"
TEST_MODEL = const.MODEL_WIFI_REPEATER_V2

STATION_1_MAC = "aa:bb:cc:dd:ee:01"
STATION_1_IP = "192.168.1.133"
STATION_2_MAC = "aa:bb:cc:dd:ee:02"
STATION_2_IP = "192.168.1.156"
STATION_3_MAC = "ff:ee:dd:cc:bb:aa"
STATION_3_IP = "192.168.1.199"


def get_mock_status(stations: list[dict[str, str]]) -> WifiRepeaterStatus:
    """Return a mock WifiRepeaterStatus."""
    return WifiRepeaterStatus(
        {
            "sta": {"count": len(stations), "access_policy": 0},
            "mat": stations,
            "access_list": {"mac": ""},
        }
    )


def get_mock_info(model: str = TEST_MODEL, mac_address: str = TEST_MAC) -> Mock:
    """Return a mock device info instance."""
    device_info = Mock()
    device_info.model = model
    device_info.mac_address = mac_address
    device_info.hardware_version = "AB123"
    device_info.firmware_version = "1.2.3_456"
    return device_info


@pytest.fixture
def mock_device_registry_devices(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> dr.DeviceRegistry:
    """Create device registry devices so the device tracker entities are enabled."""
    config_entry = MockConfigEntry(domain="something_else")
    config_entry.add_to_hass(hass)

    for idx, device in enumerate((STATION_1_MAC, STATION_2_MAC, STATION_3_MAC)):
        device_registry.async_get_or_create(
            name=f"Device {idx}",
            config_entry_id=config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, device)},
        )
    return device_registry


@pytest.fixture
def mock_repeater() -> Generator[MagicMock]:
    """Mock the WifiRepeater device."""
    mock_repeater = MagicMock()
    mock_repeater.info = Mock(return_value=get_mock_info())
    mock_repeater.status = Mock(
        return_value=get_mock_status(
            [
                {"mac": STATION_1_MAC, "ip": STATION_1_IP, "last_time": 12345},
                {"mac": STATION_2_MAC, "ip": STATION_2_IP, "last_time": 67890},
            ]
        )
    )
    with patch("homeassistant.components.xiaomi_miio.WifiRepeater") as mock_class:
        mock_class.return_value = mock_repeater
        yield mock_repeater


def create_repeater_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a config entry for the wifi repeater."""
    return MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="123456",
        title=f"{TEST_MODEL} {TEST_HOST}",
        data={
            const.CONF_FLOW_TYPE: const.CONF_WIFI_REPEATER,
            CONF_HOST: TEST_HOST,
            CONF_TOKEN: TEST_TOKEN,
            CONF_MODEL: TEST_MODEL,
            CONF_MAC: TEST_MAC,
        },
    )


async def setup_repeater(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the repeater and wait for completion."""
    entry = create_repeater_entry(hass)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def get_entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    mac: str,
) -> str:
    """Return the entity id for a station mac address."""
    unique_id = f"{entry.entry_id}_{mac}"
    entity_id = entity_registry.async_get_entity_id(
        "device_tracker", const.DOMAIN, unique_id
    )
    assert entity_id
    return entity_id


async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_device_registry_devices: dr.DeviceRegistry,
    mock_repeater: MagicMock,
) -> None:
    """Test the setup of the repeater device tracker."""
    entry = await setup_repeater(hass)

    for mac, ip in (
        (STATION_1_MAC, STATION_1_IP),
        (STATION_2_MAC, STATION_2_IP),
    ):
        entity_id = get_entity_id(hass, entity_registry, entry, mac)
        assert (state := hass.states.get(entity_id))
        assert state.state == "home"
        assert state.attributes["mac"] == mac
        assert state.attributes["ip"] == ip
        assert state.attributes["source_type"] == "router"
        assert entity_registry.async_get(entity_id).disabled_by is None, (
            "Entity should be enabled"
        )

    # The repeater itself is registered as a device.
    device_entry = device_registry.async_get_device_by_identifier(
        (const.DOMAIN, "123456"), entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.model == TEST_MODEL

    # The entry is set up with a coordinator that polled the device.
    assert entry.runtime_data.device_coordinator.data is not None
    assert mock_repeater.status.call_count == 1


async def test_repeater_flow_type_dispatch(hass: HomeAssistant) -> None:
    """Test that the repeater flow type dispatches to the repeater setup."""
    entry = create_repeater_entry(hass)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.xiaomi_miio.async_setup_repeater_entry"
    ) as mock_setup_repeater:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    mock_setup_repeater.assert_awaited_once()


async def test_refresh_adds_new_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device_registry_devices: dr.DeviceRegistry,
    mock_repeater: MagicMock,
) -> None:
    """Test that a device connecting after setup gets a new entity."""
    entry = await setup_repeater(hass)

    assert (
        entity_registry.async_get_entity_id(
            "device_tracker", const.DOMAIN, f"{entry.entry_id}_{STATION_3_MAC}"
        )
        is None
    )

    mock_repeater.status = Mock(
        return_value=get_mock_status(
            [
                {"mac": STATION_2_MAC, "ip": STATION_2_IP, "last_time": 111},
                {"mac": STATION_3_MAC, "ip": STATION_3_IP, "last_time": 222},
            ]
        )
    )
    coordinator = entry.runtime_data.device_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    entity_id = get_entity_id(hass, entity_registry, entry, STATION_3_MAC)
    assert (state := hass.states.get(entity_id))
    assert state.state == "home"
    assert state.attributes["ip"] == STATION_3_IP


async def test_device_disconnects(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device_registry_devices: dr.DeviceRegistry,
    mock_repeater: MagicMock,
) -> None:
    """Test that a device dropping off the repeater reports not_home."""
    entry = await setup_repeater(hass)
    entity_id = get_entity_id(hass, entity_registry, entry, STATION_1_MAC)
    assert (state := hass.states.get(entity_id))
    assert state.state == "home"

    mock_repeater.status = Mock(
        return_value=get_mock_status(
            [{"mac": STATION_2_MAC, "ip": STATION_2_IP, "last_time": 111}]
        )
    )
    coordinator = entry.runtime_data.device_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == "not_home"
    assert "ip" not in state.attributes


async def test_repeater_unreachable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device_registry_devices: dr.DeviceRegistry,
    mock_repeater: MagicMock,
) -> None:
    """Test that a failed poll keeps the last known station data."""
    entry = await setup_repeater(hass)
    entity_id_1 = get_entity_id(hass, entity_registry, entry, STATION_1_MAC)
    entity_id_2 = get_entity_id(hass, entity_registry, entry, STATION_2_MAC)

    mock_repeater.status = Mock(side_effect=DeviceException("unreachable"))
    coordinator = entry.runtime_data.device_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    # Entities keep the last known data instead of flipping to not_home.
    for entity_id, ip in (
        (entity_id_1, STATION_1_IP),
        (entity_id_2, STATION_2_IP),
    ):
        assert (state := hass.states.get(entity_id))
        assert state.state == "home"
        assert state.attributes["ip"] == ip

    # A successful refresh restores normal operation.
    mock_repeater.status = Mock(
        return_value=get_mock_status(
            [
                {"mac": STATION_1_MAC, "ip": STATION_1_IP, "last_time": 123},
                {"mac": STATION_2_MAC, "ip": STATION_2_IP, "last_time": 456},
            ]
        )
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success is True


async def test_coordinator_checksum_error_starts_reauth(
    hass: HomeAssistant,
    mock_device_registry_devices: dr.DeviceRegistry,
    mock_repeater: MagicMock,
) -> None:
    """A checksum error on a refresh starts the reauth flow."""
    entry = await setup_repeater(hass)

    error = DeviceException({})
    error.__cause__ = ChecksumError({})
    mock_repeater.status = Mock(side_effect=error)

    coordinator = entry.runtime_data.device_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    assert entry.state is config_entries.ConfigEntryState.LOADED
    in_progress = hass.config_entries.flow.async_progress_by_handler(
        const.DOMAIN, match_context={"source": config_entries.SOURCE_REAUTH}
    )
    assert len(in_progress) == 1


async def test_coordinator_retry_checksum_error_starts_reauth(
    hass: HomeAssistant,
    mock_device_registry_devices: dr.DeviceRegistry,
    mock_repeater: MagicMock,
) -> None:
    """A checksum error on the retry refresh starts the reauth flow."""
    entry = await setup_repeater(hass)

    retry_error = DeviceException({})
    retry_error.code = -9999
    checksum_error = DeviceException({})
    checksum_error.__cause__ = ChecksumError({})
    mock_repeater.status = Mock(side_effect=[retry_error, checksum_error])

    coordinator = entry.runtime_data.device_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    assert mock_repeater.status.call_count == 2
    assert entry.state is config_entries.ConfigEntryState.LOADED
    in_progress = hass.config_entries.flow.async_progress_by_handler(
        const.DOMAIN, match_context={"source": config_entries.SOURCE_REAUTH}
    )
    assert len(in_progress) == 1


async def test_setup_ignores_malformed_stations(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device_registry_devices: dr.DeviceRegistry,
    mock_repeater: MagicMock,
) -> None:
    """Stations that are not dicts or miss a MAC address are skipped."""
    mock_repeater.status = Mock(
        return_value=WifiRepeaterStatus(
            {
                "sta": {"count": 3, "access_policy": 0},
                "mat": [
                    {"mac": STATION_1_MAC, "ip": STATION_1_IP, "last_time": 12345},
                    {"ip": STATION_2_IP, "last_time": 67890},
                    "not-a-dict",
                ],
                "access_list": {"mac": ""},
            }
        )
    )

    entry = await setup_repeater(hass)

    entity_id = get_entity_id(hass, entity_registry, entry, STATION_1_MAC)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "home"
    assert [
        item.unique_id
        for item in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if item.domain == "device_tracker"
    ] == [f"{entry.entry_id}_{STATION_1_MAC}"]


async def test_add_entities_without_station_info(
    hass: HomeAssistant, mock_repeater: MagicMock
) -> None:
    """Adding tracker entities without a station list is a no-op."""
    entry = await setup_repeater(hass)

    added: list[XiaomiMiioRepeaterDevice] = []
    add_entities(
        entry.runtime_data.device_coordinator,
        None,
        added.extend,
        {},
    )

    assert not added


async def test_update_state_with_missing_or_malformed_stations(
    hass: HomeAssistant,
    mock_device_registry_devices: dr.DeviceRegistry,
    mock_repeater: MagicMock,
) -> None:
    """The station state tolerates missing data and malformed stations."""
    entry = await setup_repeater(hass)
    coordinator = entry.runtime_data.device_coordinator

    coordinator.data = None
    entity = XiaomiMiioRepeaterDevice(coordinator, STATION_1_MAC)
    entity.async_update_state()
    assert not entity.is_connected

    coordinator.data = WifiRepeaterStatus(
        {
            "sta": {"count": 2, "access_policy": 0},
            "mat": ["not-a-dict", {"ip": STATION_1_IP, "last_time": 12345}],
            "access_list": {"mac": ""},
        }
    )
    entity.async_update_state()
    assert not entity.is_connected


async def test_setup_auth_error(hass: HomeAssistant, mock_repeater: MagicMock) -> None:
    """Test setup with a wrong token (checksum error) starts reauth."""
    error = DeviceException({})
    error.__cause__ = ChecksumError({})
    mock_repeater.info = Mock(side_effect=error)

    entry = create_repeater_entry(hass)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    in_progress = hass.config_entries.flow.async_progress_by_handler(
        const.DOMAIN, match_context={"source": config_entries.SOURCE_REAUTH}
    )
    assert len(in_progress) == 1


async def test_setup_unavailable(hass: HomeAssistant, mock_repeater: MagicMock) -> None:
    """Test setup with an unreachable repeater retries."""
    mock_repeater.info = Mock(side_effect=DeviceException("unreachable"))

    entry = create_repeater_entry(hass)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY


async def test_setup_first_refresh_failure(
    hass: HomeAssistant, mock_repeater: MagicMock
) -> None:
    """Test setup where the first coordinator refresh fails retries."""
    mock_repeater.status = Mock(side_effect=DeviceException("unreachable"))

    entry = create_repeater_entry(hass)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY


async def test_restore_missing_station(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device_registry_devices: dr.DeviceRegistry,
    mock_repeater: MagicMock,
) -> None:
    """Test that a previously seen station is restored as not_home."""
    entry = create_repeater_entry(hass)
    entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "device_tracker",
        const.DOMAIN,
        f"{entry.entry_id}_{STATION_3_MAC}",
        config_entry=entry,
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = get_entity_id(hass, entity_registry, entry, STATION_3_MAC)
    assert (state := hass.states.get(entity_id))
    assert state.state == "not_home"


async def test_restore_skips_untracked_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device_registry_devices: dr.DeviceRegistry,
    mock_repeater: MagicMock,
) -> None:
    """Test that registry entries that are not station trackers are skipped."""
    entry = create_repeater_entry(hass)
    entry.add_to_hass(hass)
    # Pre-scoping unique_id format: the raw MAC without the entry prefix.
    entity_registry.async_get_or_create(
        "device_tracker",
        const.DOMAIN,
        STATION_3_MAC,
        config_entry=entry,
    )
    entity_registry.async_get_or_create(
        "sensor",
        const.DOMAIN,
        f"{entry.entry_id}_sensor",
        config_entry=entry,
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # STATION_3 is not connected, so no scoped entity may be restored
    # from the unscoped registry entry.
    assert (
        entity_registry.async_get_entity_id(
            "device_tracker", const.DOMAIN, f"{entry.entry_id}_{STATION_3_MAC}"
        )
        is None
    )


async def test_unload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_device_registry_devices: dr.DeviceRegistry,
    mock_repeater: MagicMock,
) -> None:
    """Test that unloading the entry stops polling."""
    entry = await setup_repeater(hass)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    calls_before = mock_repeater.status.call_count
    freezer.tick(UPDATE_INTERVAL + UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_repeater.status.call_count == calls_before

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert mock_repeater.status.call_count > calls_before


async def test_diagnostics(
    hass: HomeAssistant,
    mock_device_registry_devices: dr.DeviceRegistry,
    mock_repeater: MagicMock,
) -> None:
    """Test diagnostics export the repeater station list with redaction."""
    entry = await setup_repeater(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["coordinator_data"] == {
        "sta": {"count": 2, "access_policy": 0},
        "mat": [
            {"mac": REDACTED, "ip": REDACTED, "last_time": 12345},
            {"mac": REDACTED, "ip": REDACTED, "last_time": 67890},
        ],
        "access_list": {"mac": ""},
    }

    config_entry_data = diagnostics["config_entry"]["data"]
    assert config_entry_data[CONF_TOKEN] == REDACTED
    assert config_entry_data[CONF_MAC] == REDACTED


async def test_two_entries_same_station(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device_registry_devices: dr.DeviceRegistry,
    mock_repeater: MagicMock,
) -> None:
    """The same station seen by two repeaters gets one tracker per entry."""
    entry = await setup_repeater(hass)

    # A second repeater seeing the same station must not take over its tracker.
    second_entry = MockConfigEntry(
        domain=const.DOMAIN,
        entry_id="01JCCCCCCCCCCCCCCCCCCCCCCCCC",
        unique_id="654321",
        title=f"{TEST_MODEL} {TEST_HOST}",
        data={
            const.CONF_FLOW_TYPE: const.CONF_WIFI_REPEATER,
            CONF_HOST: TEST_HOST,
            CONF_TOKEN: TEST_TOKEN,
            CONF_MODEL: TEST_MODEL,
            CONF_MAC: TEST_MAC,
        },
    )
    second_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second_entry.entry_id)
    await hass.async_block_till_done()

    assert second_entry.state is config_entries.ConfigEntryState.LOADED
    for test_entry in (entry, second_entry):
        entity_id = get_entity_id(hass, entity_registry, test_entry, STATION_1_MAC)
        assert (state := hass.states.get(entity_id))
        assert state.state == "home"
        assert entity_registry.async_get(entity_id).config_entry_id == (
            test_entry.entry_id
        )


async def test_entities_disabled_without_registry_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_repeater: MagicMock,
) -> None:
    """Test that station entities are disabled when the mac is unregistered.

    Scanner entities are disabled by default unless the mac address is
    registered in the device registry; being connected at add time does
    not enable them.
    """
    entry = await setup_repeater(hass)

    entity_id = get_entity_id(hass, entity_registry, entry, STATION_1_MAC)
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None

    assert entry.runtime_data.device_coordinator.data is not None
