"""Test Device Tracker config entry things."""
from collections.abc import Generator
from typing import Any

import pytest

from homeassistant.components.device_tracker import (
    ATTR_HOST_NAME,
    ATTR_IP,
    ATTR_MAC,
    ATTR_SOURCE_TYPE,
    DOMAIN,
    SourceType,
)
from homeassistant.components.device_tracker.config_entry import (
    CONNECTED_DEVICE_REGISTERED,
    BaseTrackerEntity,
    ScannerEntity,
    TrackerEntity,
)
from homeassistant.components.zone import ATTR_RADIUS
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlow
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test"
TEST_MAC_ADDRESS = "12:34:56:AB:CD:EF"


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None, None, None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


@pytest.fixture(autouse=True)
def mock_setup_integration(hass: HomeAssistant) -> None:
    """Fixture to set up a mock integration."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.DEVICE_TRACKER]
        )
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> bool:
        await hass.config_entries.async_unload_platforms(
            config_entry, [Platform.DEVICE_TRACKER]
        )
        return True

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
            async_unload_entry=async_unload_entry_init,
        ),
    )


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
    """Return the config entry used for the tests."""
    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    return config_entry


async def create_mock_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entities: list[Entity],
) -> MockConfigEntry:
    """Create a device tracker platform with the specified entities."""

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test event platform via config entry."""
        async_add_entities(entities)

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


@pytest.fixture(name="entity_id")
def entity_id_fixture() -> str:
    """Return the entity_id of the entity for the test."""
    return "device_tracker.entity1"


class MockTrackerEntity(TrackerEntity):
    """Test tracker entity."""

    def __init__(
        self,
        battery_level: int | None = None,
        location_name: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> None:
        """Initialize entity."""
        self._battery_level = battery_level
        self._location_name = location_name
        self._latitude = latitude
        self._longitude = longitude

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the device.

        Percentage from 0-100.
        """
        return self._battery_level

    @property
    def source_type(self) -> SourceType | str:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    @property
    def location_name(self) -> str | None:
        """Return a location name for the current location of the device."""
        return self._location_name

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self._latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self._longitude


@pytest.fixture(name="battery_level")
def battery_level_fixture() -> int | None:
    """Return the battery level of the entity for the test."""
    return None


@pytest.fixture(name="location_name")
def location_name_fixture() -> str | None:
    """Return the location_name of the entity for the test."""
    return None


@pytest.fixture(name="latitude")
def latitude_fixture() -> float | None:
    """Return the latitude of the entity for the test."""
    return None


@pytest.fixture(name="longitude")
def longitude_fixture() -> float | None:
    """Return the longitude of the entity for the test."""
    return None


@pytest.fixture(name="tracker_entity")
def tracker_entity_fixture(
    entity_id: str,
    battery_level: int | None,
    location_name: str | None,
    latitude: float | None,
    longitude: float | None,
) -> MockTrackerEntity:
    """Create a test tracker entity."""
    entity = MockTrackerEntity(
        battery_level=battery_level,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
    )
    entity.entity_id = entity_id
    return entity


class MockScannerEntity(ScannerEntity):
    """Test scanner entity."""

    def __init__(
        self,
        ip_address: str | None = None,
        mac_address: str | None = None,
        hostname: str | None = None,
        connected: bool = False,
        unique_id: str | None = None,
    ) -> None:
        """Initialize entity."""
        self._ip_address = ip_address
        self._mac_address = mac_address
        self._hostname = hostname
        self._connected = connected
        self._unique_id = unique_id

    @property
    def should_poll(self) -> bool:
        """Return False for the test entity."""
        return False

    @property
    def source_type(self) -> SourceType | str:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.ROUTER

    @property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return self._ip_address

    @property
    def mac_address(self) -> str | None:
        """Return the mac address of the device."""
        return self._mac_address

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        return self._hostname

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._connected

    @property
    def unique_id(self) -> str | None:
        """Return hostname of the device."""
        return self._unique_id or self._mac_address

    @callback
    def set_connected(self, connected: bool) -> None:
        """Set connected state."""
        self._connected = connected
        self.async_write_ha_state()


@pytest.fixture(name="ip_address")
def ip_address_fixture() -> str | None:
    """Return the ip_address of the entity for the test."""
    return None


@pytest.fixture(name="mac_address")
def mac_address_fixture() -> str | None:
    """Return the mac_address of the entity for the test."""
    return None


@pytest.fixture(name="hostname")
def hostname_fixture() -> str | None:
    """Return the hostname of the entity for the test."""
    return None


@pytest.fixture(name="unique_id")
def unique_id_fixture() -> str | None:
    """Return the unique_id of the entity for the test."""
    return None


@pytest.fixture(name="scanner_entity")
def scanner_entity_fixture(
    entity_id: str,
    ip_address: str | None,
    mac_address: str | None,
    hostname: str | None,
    unique_id: str | None,
) -> MockScannerEntity:
    """Create a test scanner entity."""
    entity = MockScannerEntity(
        ip_address=ip_address,
        mac_address=mac_address,
        hostname=hostname,
        unique_id=unique_id,
    )
    entity.entity_id = entity_id
    return entity


async def test_load_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_id: str,
    tracker_entity: MockTrackerEntity,
) -> None:
    """Test loading and unloading a config entry with a device tracker entity."""
    config_entry = await create_mock_platform(hass, config_entry, [tracker_entity])
    assert config_entry.state == ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.NOT_LOADED

    state = hass.states.get(entity_id)
    assert not state


@pytest.mark.parametrize(
    (
        "battery_level",
        "location_name",
        "latitude",
        "longitude",
        "expected_state",
        "expected_attributes",
    ),
    [
        (
            None,
            None,
            1.0,
            2.0,
            STATE_NOT_HOME,
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_GPS_ACCURACY: 0,
                ATTR_LATITUDE: 1.0,
                ATTR_LONGITUDE: 2.0,
            },
        ),
        (
            None,
            None,
            50.0,
            60.0,
            STATE_HOME,
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_GPS_ACCURACY: 0,
                ATTR_LATITUDE: 50.0,
                ATTR_LONGITUDE: 60.0,
            },
        ),
        (
            None,
            None,
            -50.0,
            -60.0,
            "other zone",
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_GPS_ACCURACY: 0,
                ATTR_LATITUDE: -50.0,
                ATTR_LONGITUDE: -60.0,
            },
        ),
        (
            None,
            "zen_zone",
            None,
            None,
            "zen_zone",
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
            },
        ),
        (
            None,
            None,
            None,
            None,
            STATE_UNKNOWN,
            {ATTR_SOURCE_TYPE: SourceType.GPS},
        ),
        (
            100,
            None,
            None,
            None,
            STATE_UNKNOWN,
            {ATTR_BATTERY_LEVEL: 100, ATTR_SOURCE_TYPE: SourceType.GPS},
        ),
    ],
)
async def test_tracker_entity_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_id: str,
    tracker_entity: MockTrackerEntity,
    expected_state: str,
    expected_attributes: dict[str, Any],
) -> None:
    """Test tracker entity state and state attributes."""
    config_entry = await create_mock_platform(hass, config_entry, [tracker_entity])
    assert config_entry.state == ConfigEntryState.LOADED
    hass.states.async_set(
        "zone.home",
        "0",
        {ATTR_LATITUDE: 50.0, ATTR_LONGITUDE: 60.0, ATTR_RADIUS: 200},
    )
    hass.states.async_set(
        "zone.other_zone",
        "0",
        {ATTR_LATITUDE: -50.0, ATTR_LONGITUDE: -60.0, ATTR_RADIUS: 300},
    )
    await hass.async_block_till_done()
    # Write state again to ensure the zone state is taken into account.
    tracker_entity.async_write_ha_state()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == expected_state
    assert state.attributes == expected_attributes


@pytest.mark.parametrize(
    ("ip_address", "mac_address", "hostname"),
    [("0.0.0.0", "ad:de:ef:be:ed:fe", "test.hostname.org")],
)
async def test_scanner_entity_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_id: str,
    ip_address: str,
    mac_address: str,
    hostname: str,
    scanner_entity: MockScannerEntity,
) -> None:
    """Test ScannerEntity based device tracker."""
    # Make device tied to other integration so device tracker entities get enabled
    other_config_entry = MockConfigEntry(domain="not_fake_integration")
    other_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        name="Device from other integration",
        config_entry_id=other_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac_address)},
    )

    config_entry = await create_mock_platform(hass, config_entry, [scanner_entity])
    assert config_entry.state == ConfigEntryState.LOADED

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.attributes == {
        ATTR_SOURCE_TYPE: SourceType.ROUTER,
        ATTR_IP: ip_address,
        ATTR_MAC: mac_address,
        ATTR_HOST_NAME: hostname,
    }
    assert entity_state.state == STATE_NOT_HOME

    scanner_entity.set_connected(True)
    await hass.async_block_till_done()

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.state == STATE_HOME


def test_tracker_entity() -> None:
    """Test coverage for base TrackerEntity class."""
    entity = TrackerEntity()
    with pytest.raises(NotImplementedError):
        assert entity.source_type is None
    assert entity.latitude is None
    assert entity.longitude is None
    assert entity.location_name is None
    assert entity.state is None
    assert entity.battery_level is None
    assert entity.should_poll is False
    assert entity.force_update is True

    class MockEntity(TrackerEntity):
        """Mock tracker class."""

        def __init__(self) -> None:
            """Initialize."""
            self.is_polling = False

        @property
        def should_poll(self) -> bool:
            """Return False for the test entity."""
            return self.is_polling

    test_entity = MockEntity()

    assert test_entity.force_update

    test_entity.is_polling = True

    assert not test_entity.force_update


def test_scanner_entity() -> None:
    """Test coverage for base ScannerEntity entity class."""
    entity = ScannerEntity()
    with pytest.raises(NotImplementedError):
        assert entity.source_type is None
    with pytest.raises(NotImplementedError):
        assert entity.is_connected is None
    with pytest.raises(NotImplementedError):
        assert entity.state == STATE_NOT_HOME
    assert entity.battery_level is None
    assert entity.ip_address is None
    assert entity.mac_address is None
    assert entity.hostname is None

    class MockEntity(ScannerEntity):
        """Mock scanner class."""

        def __init__(self) -> None:
            """Initialize."""
            self.mock_mac_address: str | None = None

        @property
        def mac_address(self) -> str | None:
            """Return the mac address of the device."""
            return self.mock_mac_address

    test_entity = MockEntity()

    assert test_entity.unique_id is None

    test_entity.mock_mac_address = TEST_MAC_ADDRESS

    assert test_entity.unique_id == TEST_MAC_ADDRESS


def test_base_tracker_entity() -> None:
    """Test coverage for base BaseTrackerEntity entity class."""
    entity = BaseTrackerEntity()
    with pytest.raises(NotImplementedError):
        assert entity.source_type is None
    assert entity.battery_level is None
    with pytest.raises(NotImplementedError):
        assert entity.state_attributes is None


async def test_cleanup_legacy(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test we clean up devices created by old device tracker."""
    device_entry_1 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "device1")}
    )
    device_entry_2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "device2")}
    )
    device_entry_3 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "device3")}
    )

    # Device with light + device tracker entity
    entity_entry_1a = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        "entity1a-unique",
        config_entry=config_entry,
        device_id=device_entry_1.id,
    )
    entity_entry_1b = entity_registry.async_get_or_create(
        "light",
        "test",
        "entity1b-unique",
        config_entry=config_entry,
        device_id=device_entry_1.id,
    )
    # Just device tracker entity
    entity_entry_2a = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        "entity2a-unique",
        config_entry=config_entry,
        device_id=device_entry_2.id,
    )
    # Device with no device tracker entities
    entity_entry_3a = entity_registry.async_get_or_create(
        "light",
        "test",
        "entity3a-unique",
        config_entry=config_entry,
        device_id=device_entry_3.id,
    )
    # Device tracker but no device
    entity_entry_4a = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        "entity4a-unique",
        config_entry=config_entry,
    )
    # Completely different entity
    entity_entry_5a = entity_registry.async_get_or_create(
        "light",
        "test",
        "entity4a-unique",
        config_entry=config_entry,
    )

    await create_mock_platform(hass, config_entry, [])

    for entity_entry in (
        entity_entry_1a,
        entity_entry_1b,
        entity_entry_3a,
        entity_entry_4a,
        entity_entry_5a,
    ):
        assert entity_registry.async_get(entity_entry.entity_id) is not None

    entity_entry = entity_registry.async_get(entity_entry_2a.entity_id)
    assert entity_entry is not None
    # We've removed device so device ID cleared
    assert entity_entry.device_id is None
    # Removed because only had device tracker entity
    assert device_registry.async_get(device_entry_2.id) is None


@pytest.mark.parametrize(
    ("mac_address", "unique_id"), [(TEST_MAC_ADDRESS, f"{TEST_MAC_ADDRESS}_yo1")]
)
async def test_register_mac(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    scanner_entity: MockScannerEntity,
    entity_id: str,
    mac_address: str,
    unique_id: str,
) -> None:
    """Test registering a mac."""
    await create_mock_platform(hass, config_entry, [scanner_entity])

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac_address)},
    )
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.disabled_by is None


@pytest.mark.parametrize(
    ("connections", "mac_address", "unique_id"),
    [
        (
            set(),
            TEST_MAC_ADDRESS,
            f"{TEST_MAC_ADDRESS}_yo1",
        ),
        (
            {(dr.CONNECTION_NETWORK_MAC, TEST_MAC_ADDRESS)},
            "aa:bb:cc:dd:ee:ff",
            "aa_bb_cc_dd_ee_ff",
        ),
    ],
)
async def test_register_mac_not_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    scanner_entity: MockScannerEntity,
    entity_id: str,
    connections: set[tuple[str, str]],
    mac_address: str,
    unique_id: str,
) -> None:
    """Test registering a mac when the mac or entity isn't found."""
    registering_scanner_entity = MockScannerEntity(mac_address="aa:bb:cc:dd:ee:ff")
    registering_scanner_entity.entity_id = f"{DOMAIN}.registering_scanner_entity"

    await create_mock_platform(
        hass, config_entry, [registering_scanner_entity, scanner_entity]
    )

    test_entity_entry = entity_registry.async_get(entity_id)
    assert test_entity_entry is not None
    assert test_entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections=connections,
        identifiers={(TEST_DOMAIN, "device1")},
    )
    await hass.async_block_till_done()

    # The entity entry under test should still be disabled.
    test_entity_entry = entity_registry.async_get(entity_id)
    assert test_entity_entry is not None
    assert test_entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize(
    ("mac_address", "unique_id"), [(TEST_MAC_ADDRESS, f"{TEST_MAC_ADDRESS}_yo1")]
)
async def test_register_mac_ignored(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    scanner_entity: MockScannerEntity,
    entity_id: str,
    mac_address: str,
    unique_id: str,
) -> None:
    """Test ignoring registering a mac."""
    config_entry = MockConfigEntry(domain=TEST_DOMAIN, pref_disable_new_entities=True)
    config_entry.add_to_hass(hass)

    await create_mock_platform(hass, config_entry, [scanner_entity])

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac_address)},
    )
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION


async def test_connected_device_registered(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test dispatch on connected device being registered."""
    dispatches: list[dict[str, Any]] = []

    @callback
    def _save_dispatch(msg: dict[str, Any]) -> None:
        """Save dispatched message."""
        dispatches.append(msg)

    unsub = async_dispatcher_connect(hass, CONNECTED_DEVICE_REGISTERED, _save_dispatch)

    connected_scanner_entity = MockScannerEntity(
        ip_address="5.4.3.2",
        mac_address="aa:bb:cc:dd:ee:ff",
        hostname="connected",
        connected=True,
    )
    disconnected_scanner_entity = MockScannerEntity(
        ip_address="5.4.3.2",
        mac_address="aa:bb:cc:dd:ee:00",
        hostname="disconnected",
        connected=False,
    )
    connected_scanner_entity_bad_ip = MockScannerEntity(
        ip_address="",
        mac_address="aa:bb:cc:dd:ee:01",
        hostname="connected_bad_ip",
        connected=True,
    )

    config_entry = await create_mock_platform(
        hass,
        config_entry,
        [
            connected_scanner_entity,
            disconnected_scanner_entity,
            connected_scanner_entity_bad_ip,
        ],
    )

    full_name = f"{config_entry.domain}.{DOMAIN}"
    assert full_name in hass.config.components
    assert (
        len(hass.states.async_entity_ids(domain_filter=DOMAIN)) == 0
    )  # should be disabled
    assert len(entity_registry.entities) == 3
    assert (
        entity_registry.entities[
            "device_tracker.test_aa_bb_cc_dd_ee_ff"
        ].config_entry_id
        == config_entry.entry_id
    )
    unsub()
    assert dispatches == [
        {"ip": "5.4.3.2", "mac": "aa:bb:cc:dd:ee:ff", "host_name": "connected"}
    ]


async def test_entity_has_device_info(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a scanner entity with device info."""

    class DeviceInfoScannerEntity(MockScannerEntity):
        """Test scanner entity with device info."""

        @property
        def device_info(self) -> dr.DeviceInfo:
            """Return device info."""
            return dr.DeviceInfo(
                connections={(dr.CONNECTION_NETWORK_MAC, TEST_MAC_ADDRESS)},
                identifiers={(TEST_DOMAIN, "device1")},
                manufacturer="manufacturer",
                model="model",
            )

    scanner_entity = DeviceInfoScannerEntity(
        ip_address="5.4.3.2",
        mac_address=TEST_MAC_ADDRESS,
    )

    config_entry = await create_mock_platform(hass, config_entry, [scanner_entity])

    assert (
        len(hass.states.async_entity_ids(domain_filter=DOMAIN)) == 1
    )  # should be enabled
    assert len(entity_registry.entities) == 1
    assert (
        entity_registry.entities[
            f"{DOMAIN}.{TEST_DOMAIN}_{TEST_MAC_ADDRESS.replace(':', '_').lower()}"
        ].config_entry_id
        == config_entry.entry_id
    )
