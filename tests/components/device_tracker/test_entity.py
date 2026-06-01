"""Test Device Tracker config entry things."""

from collections.abc import Generator
from typing import Any

import pytest

from homeassistant.components.device_tracker import (
    ATTR_HOST_NAME,
    ATTR_IN_ZONES,
    ATTR_IP,
    ATTR_MAC,
    ATTR_SOURCE_TYPE,
    CONF_ASSOCIATED_ZONE,
    CONNECTED_DEVICE_REGISTERED,
    DOMAIN,
    BaseScannerEntity,
    BaseTrackerEntity,
    ScannerEntity,
    SourceType,
    TrackerEntity,
)
from homeassistant.components.zone import ATTR_PASSIVE, ATTR_RADIUS
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlow
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_FRIENDLY_NAME,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
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
        async_add_entities: AddConfigEntryEntitiesCallback,
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
        in_zones: list[str] | None = None,
        location_name: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        location_accuracy: float = 0,
    ) -> None:
        """Initialize entity."""
        self._battery_level = battery_level
        self._in_zones = in_zones
        self._location_name = location_name
        self._latitude = latitude
        self._longitude = longitude
        self._location_accuracy = location_accuracy

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the device.

        Percentage from 0-100.
        """
        return self._battery_level

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    @property
    def in_zones(self) -> list[str] | None:
        """Return the entity_id of zones the device is currently in."""
        return self._in_zones

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

    @property
    def location_accuracy(self) -> float:
        """Return the accuracy of the location in meters."""
        return self._location_accuracy


@pytest.fixture(name="battery_level")
def battery_level_fixture() -> int | None:
    """Return the battery level of the entity for the test."""
    return None


@pytest.fixture(name="in_zones")
def in_zones_fixture() -> list[str] | None:
    """Return the in_zones value of the entity for the test."""
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


@pytest.fixture(name="location_accuracy")
def accuracy_fixture() -> float:
    """Return the location accuracy of the entity for the test."""
    return 0


@pytest.fixture(name="tracker_entity")
def tracker_entity_fixture(
    entity_id: str,
    battery_level: int | None,
    in_zones: list[str] | None,
    location_name: str | None,
    latitude: float | None,
    longitude: float | None,
    location_accuracy: float = 0,
) -> MockTrackerEntity:
    """Create a test tracker entity."""
    entity = MockTrackerEntity(
        battery_level=battery_level,
        in_zones=in_zones,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
        location_accuracy=location_accuracy,
    )
    entity.entity_id = entity_id
    return entity


class MockBaseScannerEntity(BaseScannerEntity):
    """Test base scanner entity."""

    def __init__(
        self,
        connected: bool | None = False,
        unique_id: str | None = None,
    ) -> None:
        """Initialize entity."""
        self._connected = connected
        self._unique_id = unique_id

    @property
    def should_poll(self) -> bool:
        """Return False for the test entity."""
        return False

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.BLUETOOTH_LE

    @property
    def is_connected(self) -> bool | None:
        """Return true if the device is connected to the network."""
        return self._connected

    @property
    def unique_id(self) -> str | None:
        """Return hostname of the device."""
        return self._unique_id

    @callback
    def set_connected(self, connected: bool | None) -> None:
        """Set connected state."""
        self._connected = connected
        self.async_write_ha_state()


@pytest.fixture(name="unique_id")
def unique_id_fixture() -> str | None:
    """Return the unique_id of the entity for the test."""
    return None


@pytest.fixture(name="base_scanner_entity")
def base_scanner_entity_fixture(
    entity_id: str,
    unique_id: str | None,
) -> MockBaseScannerEntity:
    """Create a test base scanner entity."""
    entity = MockBaseScannerEntity(
        unique_id=unique_id,
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
        connected: bool | None = False,
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
    def source_type(self) -> SourceType:
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
    def is_connected(self) -> bool | None:
        """Return true if the device is connected to the network."""
        return self._connected

    @property
    def unique_id(self) -> str | None:
        """Return hostname of the device."""
        return self._unique_id or self._mac_address

    @callback
    def set_connected(self, connected: bool | None) -> None:
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


async def test_load_unload_entry_base_scanner(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_id: str,
    base_scanner_entity: MockBaseScannerEntity,
) -> None:
    """Test loading and unloading a config entry with a device tracker entity."""
    config_entry = await create_mock_platform(hass, config_entry, [base_scanner_entity])
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    state = hass.states.get(entity_id)
    assert not state


async def test_load_unload_entry_scanner(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_id: str,
    scanner_entity: MockScannerEntity,
) -> None:
    """Test loading and unloading a config entry with a device tracker entity."""
    config_entry = await create_mock_platform(hass, config_entry, [scanner_entity])
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    state = hass.states.get(entity_id)
    assert not state


async def test_load_unload_entry_tracker(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_id: str,
    tracker_entity: MockTrackerEntity,
) -> None:
    """Test loading and unloading a config entry with a device tracker entity."""
    config_entry = await create_mock_platform(hass, config_entry, [tracker_entity])
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id)
    assert state

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    state = hass.states.get(entity_id)
    assert not state


@pytest.mark.parametrize(
    (
        "battery_level",
        "in_zones",
        "location_name",
        "latitude",
        "longitude",
        "expected_state",
        "expected_attributes",
    ),
    [
        pytest.param(
            None,
            None,
            None,
            1.0,
            2.0,
            STATE_NOT_HOME,
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_GPS_ACCURACY: 0,
                ATTR_IN_ZONES: [],
                ATTR_LATITUDE: 1.0,
                ATTR_LONGITUDE: 2.0,
            },
            id="lat_long_no_zone",
        ),
        pytest.param(
            None,
            None,
            None,
            50.0,
            60.0,
            STATE_HOME,
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_GPS_ACCURACY: 0,
                ATTR_IN_ZONES: ["zone.home"],
                ATTR_LATITUDE: 50.0,
                ATTR_LONGITUDE: 60.0,
            },
            id="lat_long_home",
        ),
        pytest.param(
            None,
            None,
            None,
            -50.0,
            -60.0,
            "other zone",
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_GPS_ACCURACY: 0,
                ATTR_IN_ZONES: ["zone.other_zone", "zone.other_zone_larger"],
                ATTR_LATITUDE: -50.0,
                ATTR_LONGITUDE: -60.0,
            },
            id="lat_long_other_zone",
        ),
        pytest.param(
            None,
            None,
            "zen_zone",
            None,
            None,
            "zen_zone",
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_IN_ZONES: [],
            },
            id="location_name",
        ),
        pytest.param(
            None,
            None,
            None,
            None,
            None,
            STATE_UNKNOWN,
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_IN_ZONES: [],
            },
            id="no_location",
        ),
        pytest.param(
            100,
            None,
            None,
            None,
            None,
            STATE_UNKNOWN,
            {
                ATTR_BATTERY_LEVEL: 100,
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_IN_ZONES: [],
            },
            id="battery_only",
        ),
        pytest.param(
            None,
            ["zone.home"],
            None,
            None,
            None,
            STATE_HOME,
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_IN_ZONES: ["zone.home"],
            },
            id="in_zones_home",
        ),
        pytest.param(
            None,
            ["zone.other_zone"],
            None,
            None,
            None,
            "other zone",
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_IN_ZONES: ["zone.other_zone"],
            },
            id="in_zones_other_zone",
        ),
        pytest.param(
            None,
            ["zone.other_zone_larger", "zone.other_zone"],
            None,
            None,
            None,
            "other zone",
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_IN_ZONES: ["zone.other_zone", "zone.other_zone_larger"],
            },
            id="in_zones_multiple_sorted_by_radius",
        ),
        pytest.param(
            None,
            ["zone.does_not_exist", "zone.other_zone"],
            None,
            None,
            None,
            "other zone",
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_IN_ZONES: ["zone.other_zone"],
            },
            id="in_zones_filters_missing_zones",
        ),
        pytest.param(
            None,
            ["zone.does_not_exist"],
            None,
            None,
            None,
            STATE_NOT_HOME,
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_IN_ZONES: [],
            },
            id="in_zones_all_missing",
        ),
        pytest.param(
            None,
            ["zone.passive_small", "zone.other_zone"],
            None,
            None,
            None,
            "other zone",
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_IN_ZONES: ["zone.passive_small", "zone.other_zone"],
            },
            id="in_zones_skips_passive_for_state",
        ),
        pytest.param(
            None,
            ["zone.passive_small"],
            None,
            None,
            None,
            STATE_NOT_HOME,
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_IN_ZONES: ["zone.passive_small"],
            },
            id="in_zones_only_passive",
        ),
        pytest.param(
            None,
            [],
            None,
            None,
            None,
            STATE_NOT_HOME,
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_IN_ZONES: [],
            },
            id="in_zones_empty",
        ),
        pytest.param(
            None,
            ["zone.home"],
            None,
            1.0,
            2.0,
            STATE_HOME,
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_GPS_ACCURACY: 0,
                ATTR_IN_ZONES: ["zone.home"],
                ATTR_LATITUDE: 1.0,
                ATTR_LONGITUDE: 2.0,
            },
            id="in_zones_wins_over_lat_long",
        ),
        pytest.param(
            None,
            [],
            None,
            50.0,
            60.0,
            STATE_NOT_HOME,
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_GPS_ACCURACY: 0,
                ATTR_IN_ZONES: [],
                ATTR_LATITUDE: 50.0,
                ATTR_LONGITUDE: 60.0,
            },
            id="empty_in_zones_wins_over_lat_long",
        ),
        pytest.param(
            None,
            ["zone.home"],
            "zen_zone",
            None,
            None,
            "zen_zone",
            {
                ATTR_SOURCE_TYPE: SourceType.GPS,
                ATTR_IN_ZONES: ["zone.home"],
            },
            id="location_name_wins_over_in_zones",
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
    assert config_entry.state is ConfigEntryState.LOADED
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
    hass.states.async_set(
        "zone.other_zone_larger",
        "0",
        {ATTR_LATITUDE: -50.0, ATTR_LONGITUDE: -60.0, ATTR_RADIUS: 500},
    )
    hass.states.async_set(
        "zone.passive_small",
        "0",
        {
            ATTR_LATITUDE: 10.0,
            ATTR_LONGITUDE: 10.0,
            ATTR_RADIUS: 50,
            ATTR_PASSIVE: True,
        },
    )
    await hass.async_block_till_done()
    # Write state again to ensure the zone state is taken into account.
    tracker_entity.async_write_ha_state()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == expected_state
    assert state.attributes == expected_attributes


async def test_base_scanner_entity_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_id: str,
    base_scanner_entity: MockBaseScannerEntity,
) -> None:
    """Test BaseScannerEntity based device tracker."""
    config_entry = await create_mock_platform(hass, config_entry, [base_scanner_entity])
    assert config_entry.state is ConfigEntryState.LOADED

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.attributes == {
        ATTR_SOURCE_TYPE: SourceType.BLUETOOTH_LE,
        ATTR_IN_ZONES: [],
    }
    assert entity_state.state == STATE_NOT_HOME

    base_scanner_entity.set_connected(True)
    await hass.async_block_till_done()

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.state == STATE_HOME
    # No zone.home in the test state machine, so only the canonical home
    # entity_id is reported.
    assert entity_state.attributes == {
        ATTR_SOURCE_TYPE: SourceType.BLUETOOTH_LE,
        ATTR_IN_ZONES: ["zone.home"],
    }

    base_scanner_entity.set_connected(None)
    await hass.async_block_till_done()

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.state == STATE_UNKNOWN
    # is_connected is None -> empty in_zones (always reported).
    assert entity_state.attributes == {
        ATTR_SOURCE_TYPE: SourceType.BLUETOOTH_LE,
        ATTR_IN_ZONES: [],
    }


@pytest.mark.parametrize(
    ("zones", "expected_in_zones"),
    [
        pytest.param(
            [("zone.home", 50.0, 60.0, 100)],
            ["zone.home"],
            id="home_only",
        ),
        pytest.param(
            [
                ("zone.home", 50.0, 60.0, 100),
                ("zone.neighborhood", 50.0, 60.0, 500),
            ],
            ["zone.home", "zone.neighborhood"],
            id="strictly_containing_zone",
        ),
        pytest.param(
            [
                ("zone.home", 50.0, 60.0, 100),
                ("zone.huge", 50.0, 60.0, 10000),
                ("zone.medium", 50.0, 60.0, 500),
            ],
            ["zone.home", "zone.medium", "zone.huge"],
            id="multiple_containing_zones_sorted_by_radius",
        ),
        pytest.param(
            [
                ("zone.home", 50.0, 60.0, 100),
                ("zone.tiny", 50.0, 60.0, 50),
            ],
            ["zone.home"],
            id="zone_smaller_than_home_excluded",
        ),
        pytest.param(
            [
                ("zone.home", 50.0, 60.0, 100),
                ("zone.equal", 50.0, 60.0, 100),
            ],
            # Same center and radius as home: included under the <= predicate.
            # zone.home stays first because the strict-result zone.home entry
            # is filtered out, and zone.equal is the next entry.
            ["zone.home", "zone.equal"],
            id="zone_equal_to_home_included",
        ),
        pytest.param(
            [
                ("zone.home", 50.0, 60.0, 100),
                # Small offset, the home zone is fully inside
                # the other zone (~330m + 100 < 500).
                ("zone.nearby", 50.0030, 60.0, 500),
                # Offset by enough that the home zone is not fully inside
                # the other zone (~440m + 100 > 500).
                ("zone.further_away", 50.0040, 60.0, 500),
                # Offset by a very large amount, no overlap
                # the other zone (~130km + 100 > 500).
                ("zone.faraway", 51.0, 61.0, 500),
            ],
            ["zone.home", "zone.nearby"],
            id="offset_zone_excluded",
        ),
    ],
)
async def test_base_scanner_entity_in_zones_when_connected(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_id: str,
    base_scanner_entity: MockBaseScannerEntity,
    zones: list[tuple[str, float, float, int]],
    expected_in_zones: list[str],
) -> None:
    """Test in_zones content for a connected BaseScannerEntity across zone setups."""
    base_scanner_entity._connected = True

    for entity, latitude, longitude, radius in zones:
        hass.states.async_set(
            entity,
            "0",
            {ATTR_LATITUDE: latitude, ATTR_LONGITUDE: longitude, ATTR_RADIUS: radius},
        )
    await hass.async_block_till_done()

    config_entry = await create_mock_platform(hass, config_entry, [base_scanner_entity])
    assert config_entry.state is ConfigEntryState.LOADED

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.state == STATE_HOME
    assert entity_state.attributes == {
        ATTR_SOURCE_TYPE: SourceType.BLUETOOTH_LE,
        ATTR_IN_ZONES: expected_in_zones,
    }


@pytest.mark.parametrize("unique_id", ["unique_scanner"])
async def test_base_scanner_entity_associated_zone_option(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    base_scanner_entity: MockBaseScannerEntity,
) -> None:
    """Test the associated_zone entity option overrides which zone in_zones reports.

    The scanner reports being connected to a non-default zone; state and in_zones
    must follow the configured zone, and a zone enclosing the configured one is
    included in in_zones too.
    """
    hass.states.async_set(
        "zone.home",
        "0",
        {ATTR_LATITUDE: 50.0, ATTR_LONGITUDE: 60.0, ATTR_RADIUS: 1000},
    )
    hass.states.async_set(
        "zone.kitchen",
        "0",
        {ATTR_LATITUDE: 50.0, ATTR_LONGITUDE: 60.0, ATTR_RADIUS: 50},
    )
    await hass.async_block_till_done()

    base_scanner_entity._connected = True

    config_entry = await create_mock_platform(hass, config_entry, [base_scanner_entity])
    assert config_entry.state is ConfigEntryState.LOADED

    # Default: no option set -> associated with zone.home.
    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.state == STATE_HOME
    assert entity_state.attributes[ATTR_IN_ZONES] == ["zone.home"]

    # Set the option -> associated_zone replaces zone.home; zone.home now shows
    # up via the enclosing-zones lookup.
    entity_registry.async_update_entity_options(
        entity_id,
        DOMAIN,
        {CONF_ASSOCIATED_ZONE: "zone.kitchen"},
    )
    await hass.async_block_till_done()

    assert base_scanner_entity._scanner_option_associated_zone == "zone.kitchen"

    entity_state = hass.states.get(entity_id)
    assert entity_state
    # zone.kitchen is the configured zone -> state is the zone's name.
    assert entity_state.state == "kitchen"
    assert entity_state.attributes[ATTR_IN_ZONES] == ["zone.kitchen", "zone.home"]

    # Clearing the option falls back to zone.home.
    entity_registry.async_update_entity_options(entity_id, DOMAIN, None)
    await hass.async_block_till_done()

    assert base_scanner_entity._scanner_option_associated_zone == "zone.home"

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.state == STATE_HOME
    assert entity_state.attributes[ATTR_IN_ZONES] == ["zone.home"]


@pytest.mark.parametrize("unique_id", ["unique_scanner"])
async def test_base_scanner_entity_associated_zone_removed_after_set(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    entity_id: str,
    base_scanner_entity: MockBaseScannerEntity,
) -> None:
    """Test scanner state and repair issue when associated zone is removed.

    When the user picks a zone via the associated_zone option and then deletes
    that zone, the scanner falls back to ``state == "unknown"`` and a repair
    issue is opened prompting the user to reconfigure.
    """
    hass.states.async_set(
        "zone.home",
        "0",
        {ATTR_LATITUDE: 50.0, ATTR_LONGITUDE: 60.0, ATTR_RADIUS: 1000},
    )
    hass.states.async_set(
        "zone.kitchen",
        "0",
        {ATTR_LATITUDE: 50.0, ATTR_LONGITUDE: 60.0, ATTR_RADIUS: 50},
    )
    await hass.async_block_till_done()

    base_scanner_entity._connected = True

    config_entry = await create_mock_platform(hass, config_entry, [base_scanner_entity])
    assert config_entry.state is ConfigEntryState.LOADED

    entity_registry.async_update_entity_options(
        entity_id,
        DOMAIN,
        {CONF_ASSOCIATED_ZONE: "zone.kitchen"},
    )
    await hass.async_block_till_done()

    # Sanity check before removal.
    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.state == "kitchen"
    assert entity_state.attributes[ATTR_IN_ZONES] == ["zone.kitchen", "zone.home"]
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    issue_id = f"associated_zone_missing_{entity_entry.id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None

    # Remove the associated zone.
    hass.states.async_remove("zone.kitchen")
    await hass.async_block_till_done()

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.state == STATE_UNKNOWN
    assert entity_state.attributes[ATTR_IN_ZONES] == []
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == "associated_zone_missing"
    assert issue.translation_placeholders == {
        "entity_id": entity_id,
        "zone": "zone.kitchen",
    }

    # Restore the zone -> issue is cleared, state recovers.
    hass.states.async_set(
        "zone.kitchen",
        "0",
        {ATTR_LATITUDE: 50.0, ATTR_LONGITUDE: 60.0, ATTR_RADIUS: 50},
    )
    await hass.async_block_till_done()

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.state == "kitchen"
    assert entity_state.attributes[ATTR_IN_ZONES] == ["zone.kitchen", "zone.home"]
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.parametrize("unique_id", ["unique_scanner"])
async def test_base_scanner_entity_associated_zone_missing_at_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    entity_id: str,
    base_scanner_entity: MockBaseScannerEntity,
) -> None:
    """Test repair issue is created when the configured zone is missing at setup."""
    hass.states.async_set(
        "zone.home",
        "0",
        {ATTR_LATITUDE: 50.0, ATTR_LONGITUDE: 60.0, ATTR_RADIUS: 1000},
    )
    await hass.async_block_till_done()

    # Pre-register the entity option pointing at a zone that does not exist.
    entity_entry = entity_registry.async_get_or_create(
        DOMAIN,
        TEST_DOMAIN,
        base_scanner_entity.unique_id,
        suggested_object_id="entity1",
    )
    entity_registry.async_update_entity_options(
        entity_id,
        DOMAIN,
        {CONF_ASSOCIATED_ZONE: "zone.never_existed"},
    )

    base_scanner_entity._connected = True
    config_entry = await create_mock_platform(hass, config_entry, [base_scanner_entity])
    assert config_entry.state is ConfigEntryState.LOADED

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.state == STATE_UNKNOWN
    assert entity_state.attributes[ATTR_IN_ZONES] == []
    issue_id = f"associated_zone_missing_{entity_entry.id}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_placeholders == {
        "entity_id": entity_id,
        "zone": "zone.never_existed",
    }


@pytest.mark.parametrize("unique_id", ["unique_scanner"])
async def test_base_scanner_entity_associated_zone_issue_cleared_on_option_change(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    entity_id: str,
    base_scanner_entity: MockBaseScannerEntity,
) -> None:
    """Test the repair issue is cleared when the user clears the option."""
    hass.states.async_set(
        "zone.home",
        "0",
        {ATTR_LATITUDE: 50.0, ATTR_LONGITUDE: 60.0, ATTR_RADIUS: 1000},
    )
    await hass.async_block_till_done()

    base_scanner_entity._connected = True
    config_entry = await create_mock_platform(hass, config_entry, [base_scanner_entity])
    assert config_entry.state is ConfigEntryState.LOADED

    entity_registry.async_update_entity_options(
        entity_id,
        DOMAIN,
        {CONF_ASSOCIATED_ZONE: "zone.never_existed"},
    )
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    issue_id = f"associated_zone_missing_{entity_entry.id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    # Clearing the option restores the default and clears the repair issue.
    entity_registry.async_update_entity_options(entity_id, DOMAIN, None)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.state == STATE_HOME


@pytest.mark.parametrize("unique_id", ["unique_scanner"])
async def test_base_scanner_entity_associated_zone_issue_cleared_on_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    entity_id: str,
    base_scanner_entity: MockBaseScannerEntity,
) -> None:
    """Test the repair issue is cleared when the entity is removed from hass."""
    hass.states.async_set(
        "zone.home",
        "0",
        {ATTR_LATITUDE: 50.0, ATTR_LONGITUDE: 60.0, ATTR_RADIUS: 1000},
    )
    await hass.async_block_till_done()

    base_scanner_entity._connected = True
    config_entry = await create_mock_platform(hass, config_entry, [base_scanner_entity])
    assert config_entry.state is ConfigEntryState.LOADED

    entity_registry.async_update_entity_options(
        entity_id,
        DOMAIN,
        {CONF_ASSOCIATED_ZONE: "zone.never_existed"},
    )
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    issue_id = f"associated_zone_missing_{entity_entry.id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.parametrize("unique_id", ["unique_scanner"])
async def test_base_scanner_entity_associated_zone_option_set_before_add(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    base_scanner_entity: MockBaseScannerEntity,
) -> None:
    """Test associated_zone option set before the entity is added is honored."""
    hass.states.async_set(
        "zone.home",
        "0",
        {ATTR_LATITUDE: 50.0, ATTR_LONGITUDE: 60.0, ATTR_RADIUS: 1000},
    )
    hass.states.async_set(
        "zone.kitchen",
        "0",
        {ATTR_LATITUDE: 50.0, ATTR_LONGITUDE: 60.0, ATTR_RADIUS: 50},
    )
    await hass.async_block_till_done()

    # Pre-register the entity with the option set before the platform is set up.
    entity_registry.async_get_or_create(
        DOMAIN,
        TEST_DOMAIN,
        base_scanner_entity.unique_id,
        suggested_object_id="entity1",
    )
    entity_registry.async_update_entity_options(
        entity_id,
        DOMAIN,
        {CONF_ASSOCIATED_ZONE: "zone.kitchen"},
    )

    base_scanner_entity._connected = True
    config_entry = await create_mock_platform(hass, config_entry, [base_scanner_entity])
    assert config_entry.state is ConfigEntryState.LOADED

    assert base_scanner_entity._scanner_option_associated_zone == "zone.kitchen"

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.state == "kitchen"
    assert entity_state.attributes[ATTR_IN_ZONES] == ["zone.kitchen", "zone.home"]


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
    assert config_entry.state is ConfigEntryState.LOADED

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.attributes == {
        ATTR_SOURCE_TYPE: SourceType.ROUTER,
        ATTR_IN_ZONES: [],
        ATTR_IP: ip_address,
        ATTR_MAC: mac_address,
        ATTR_HOST_NAME: hostname,
        ATTR_FRIENDLY_NAME: "Device from other integration",
    }
    assert entity_state.state == STATE_NOT_HOME

    scanner_entity.set_connected(True)
    await hass.async_block_till_done()

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.state == STATE_HOME

    scanner_entity.set_connected(None)
    await hass.async_block_till_done()

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.state == STATE_UNKNOWN


def test_tracker_entity() -> None:
    """Test coverage for base TrackerEntity class."""
    entity = TrackerEntity()
    assert entity.source_type is SourceType.GPS
    assert entity.in_zones is None
    assert entity.latitude is None
    assert entity.longitude is None
    assert entity.location_name is None
    assert entity.state is None
    assert entity.battery_level is None
    assert entity.should_poll is False
    assert entity.force_update is True
    assert entity.location_accuracy == 0

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


def test_base_scanner_entity() -> None:
    """Test coverage for base BaseScannerEntity entity class."""
    entity = BaseScannerEntity()
    with pytest.raises(NotImplementedError):
        entity.source_type  # noqa: B018
    with pytest.raises(NotImplementedError):
        entity.is_connected  # noqa: B018
    with pytest.raises(NotImplementedError):
        entity.state  # noqa: B018
    assert entity.battery_level is None


def test_scanner_entity() -> None:
    """Test coverage for base ScannerEntity entity class."""
    entity = ScannerEntity()
    assert entity.source_type is SourceType.ROUTER
    with pytest.raises(NotImplementedError):
        entity.is_connected  # noqa: B018
    with pytest.raises(NotImplementedError):
        entity.state  # noqa: B018
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
        entity.source_type  # noqa: B018
    assert entity.battery_level is None
    with pytest.raises(NotImplementedError):
        entity.state_attributes  # noqa: B018


def test_battery_level_override_deprecation_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that overriding battery_level in a subclass logs a warning."""
    error_message = "is overriding the deprecated battery_level property"

    caplog.clear()

    class _SubclassWithOverride(TrackerEntity):
        @property
        def battery_level(self) -> int | None:
            return 50

    assert error_message in caplog.text
    assert _SubclassWithOverride.__name__ in caplog.text

    # No warning for a subclass that does not override battery_level
    caplog.clear()

    class _SubclassWithoutOverride(TrackerEntity):
        pass

    assert error_message not in caplog.text


async def test_attr_location_name_deprecation_warning(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that setting _attr_location_name logs a deprecation warning."""
    error_message = "is setting the deprecated _attr_location_name attribute"

    class _Subclass(TrackerEntity):
        pass

    # No warning when _attr_location_name is unset (default None)
    entity_no_attr = _Subclass()
    entity_no_attr.hass = hass
    assert entity_no_attr.location_name is None
    assert error_message not in caplog.text

    # Warning fires when _attr_location_name has a non-None value
    entity = _Subclass()
    entity.hass = hass
    entity._attr_location_name = "the_zone"
    caplog.clear()
    assert entity.location_name == "the_zone"
    assert error_message in caplog.text

    # Warning does not fire again on subsequent access for the same instance
    caplog.clear()
    assert entity.location_name == "the_zone"
    assert error_message not in caplog.text

    # Warning is suppressed for this instance even after the cached value is
    # invalidated by a subsequent _attr_location_name assignment.
    entity._attr_location_name = "another_zone"
    caplog.clear()
    assert entity.location_name == "another_zone"
    assert error_message not in caplog.text

    # A fresh instance warns once again
    entity_new = _Subclass()
    entity_new.hass = hass
    entity_new._attr_location_name = "the_zone"
    caplog.clear()
    assert entity_new.location_name == "the_zone"
    assert error_message in caplog.text


def test_location_name_override_deprecation_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that overriding location_name in a subclass logs a warning."""
    error_message = "is overriding the deprecated location_name property"

    caplog.clear()

    class _SubclassWithOverride(TrackerEntity):
        @property
        def location_name(self) -> str | None:
            return "custom"

    assert error_message in caplog.text
    assert _SubclassWithOverride.__name__ in caplog.text

    # No warning for a subclass that does not override location_name
    caplog.clear()

    class _SubclassWithoutOverride(TrackerEntity):
        pass

    assert error_message not in caplog.text


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
                name="Test Device",
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
        entity_registry.entities[f"{DOMAIN}.test_device"].config_entry_id
        == config_entry.entry_id
    )


async def test_tracker_entity_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_id: str,
) -> None:
    """Test unavailable tracker entity does not fail on bad latitude/longitude."""

    class _MockTrackerEntity(MockTrackerEntity):
        """Test tracker entity that starts with unavailable state."""

        _attr_available = False

        @property
        def latitude(self) -> float | None:
            """Return latitude value of the device."""
            raise ValueError("Upstream error")

        @property
        def longitude(self) -> float | None:
            """Return longitude value of the device."""
            raise ValueError("Upstream error")

    tracker_entity = _MockTrackerEntity()
    tracker_entity.entity_id = entity_id

    config_entry = await create_mock_platform(hass, config_entry, [tracker_entity])
    assert config_entry.state is ConfigEntryState.LOADED

    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unavailable"
    assert state.attributes == {}
