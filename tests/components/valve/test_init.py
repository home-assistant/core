"""The tests for Valve."""
from collections.abc import Generator

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.valve import (
    DOMAIN,
    ValveDeviceClass,
    ValveEntity,
    ValveEntityDescription,
    ValveEntityFeature,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlow
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_SET_VALVE_POSITION,
    SERVICE_TOGGLE,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
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


class MockFlow(ConfigFlow):
    """Test flow."""


class MockValveEntity(ValveEntity):
    """Mock valve device to use in tests."""

    _attr_should_poll = False
    _target_valve_position: int

    def __init__(
        self,
        unique_id: str = "mock_valve",
        name: str = "Valve",
        features: ValveEntityFeature = ValveEntityFeature(0),
        current_position: int = None,
        device_class: ValveDeviceClass = None,
        reports_position: bool = True,
    ) -> None:
        """Initialize the valve."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_supported_features = features
        self._attr_current_valve_position = current_position
        if reports_position is not None:
            self._attr_reports_position = reports_position
        if device_class is not None:
            self._attr_device_class = device_class

    def set_valve_position(self, position: int) -> None:
        """Set the valve to opening or closing towards a target percentage."""
        if position > self._attr_current_valve_position:
            self._attr_is_closing = False
            self._attr_is_opening = True
        else:
            self._attr_is_closing = True
            self._attr_is_opening = False
        self._target_valve_position = position
        self.schedule_update_ha_state()

    def stop_valve(self) -> None:
        """Stop the valve."""
        self._attr_is_closing = False
        self._attr_is_opening = False
        self._target_valve_position = None
        self._attr_is_closed = self._attr_current_valve_position == 0
        self.schedule_update_ha_state()

    @callback
    def finish_movement(self):
        """Set the value to the saved target and removes intermediate states."""
        self._attr_current_valve_position = self._target_valve_position
        self._attr_is_closing = False
        self._attr_is_opening = False
        self.async_write_ha_state()


class MockBinaryValveEntity(ValveEntity):
    """Mock valve device to use in tests."""

    def __init__(
        self,
        unique_id: str = "mock_valve_2",
        name: str = "Valve",
        features: ValveEntityFeature = ValveEntityFeature(0),
        is_closed: bool = None,
    ) -> None:
        """Initialize the valve."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_supported_features = features
        self._attr_is_closed = is_closed
        self._attr_reports_position = False

    def open_valve(self) -> None:
        """Open the valve."""
        self._attr_is_closed = False

    def close_valve(self) -> None:
        """Mock implementantion for sync close function."""
        self._attr_is_closed = True


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None, None, None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


@pytest.fixture
def mock_config_entry(hass) -> tuple[MockConfigEntry, list[ValveEntity]]:
    """Mock a config entry which sets up a couple of valve entities."""
    entities = [
        MockBinaryValveEntity(
            is_closed=False,
            features=ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE,
        ),
        MockValveEntity(
            current_position=50,
            features=ValveEntityFeature.OPEN
            | ValveEntityFeature.CLOSE
            | ValveEntityFeature.STOP
            | ValveEntityFeature.SET_POSITION,
        ),
    ]

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setup(
            config_entry, Platform.VALVE
        )
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload up test config entry."""
        await hass.config_entries.async_unload_platforms(config_entry, [Platform.VALVE])
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

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test platform via config entry."""
        async_add_entities(entities)

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)

    return (config_entry, entities)


async def test_valve_setup(
    hass: HomeAssistant,
    mock_config_entry: tuple[MockConfigEntry, list[ValveEntity]],
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup and tear down of valve platform and entity."""
    config_entry = mock_config_entry[0]

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    for entity in mock_config_entry[1]:
        entity_id = entity.entity_id
        state = hass.states.get(entity_id)
        assert state
        assert state == snapshot

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED

    for entity in mock_config_entry[1]:
        entity_id = entity.entity_id
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_UNAVAILABLE
        assert state == snapshot


async def test_services(
    hass: HomeAssistant, mock_config_entry: tuple[MockConfigEntry, list[ValveEntity]]
) -> None:
    """Test the provided services."""
    config_entry = mock_config_entry[0]
    ent1, ent2 = mock_config_entry[1]

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Test init all valves should be open
    assert is_open(hass, ent1)
    assert is_open(hass, ent2)

    # call basic toggle services
    await call_service(hass, SERVICE_TOGGLE, ent1)
    await call_service(hass, SERVICE_TOGGLE, ent2)

    # entities without stop should be closed and with stop should be closing
    assert is_closed(hass, ent1)
    assert is_closing(hass, ent2)
    ent2.finish_movement()
    assert is_closed(hass, ent2)

    # call basic toggle services and set different valve position states
    await call_service(hass, SERVICE_TOGGLE, ent1)
    await call_service(hass, SERVICE_TOGGLE, ent2)
    await hass.async_block_till_done()

    # entities should be in correct state depending on the SUPPORT_STOP feature and valve position
    assert is_open(hass, ent1)
    assert is_opening(hass, ent2)

    # call basic toggle services
    await call_service(hass, SERVICE_TOGGLE, ent1)
    await call_service(hass, SERVICE_TOGGLE, ent2)

    # entities should be in correct state depending on the SUPPORT_STOP feature and valve position
    assert is_closed(hass, ent1)
    assert not is_opening(hass, ent2)
    assert not is_closing(hass, ent2)
    assert is_closed(hass, ent2)

    await call_service(hass, SERVICE_SET_VALVE_POSITION, ent2, 50)
    assert is_opening(hass, ent2)


async def test_valve_device_class(hass: HomeAssistant) -> None:
    """Test valve entity with defaults."""
    default_valve = MockValveEntity()
    default_valve.hass = hass

    assert default_valve.device_class is None

    entity_description = ValveEntityDescription(
        key="test",
        device_class=ValveDeviceClass.GAS,
    )
    default_valve.entity_description = entity_description
    assert default_valve.device_class is ValveDeviceClass.GAS

    water_valve = MockValveEntity(device_class=ValveDeviceClass.WATER)
    water_valve.hass = hass

    assert water_valve.device_class is ValveDeviceClass.WATER


async def test_valve_report_position(hass: HomeAssistant) -> None:
    """Test valve entity with defaults."""
    default_valve = MockValveEntity(reports_position=None)
    default_valve.hass = hass

    with pytest.raises(ValueError):
        default_valve.reports_position

    second_valve = MockValveEntity(reports_position=True)
    second_valve.hass = hass

    assert second_valve.reports_position is True

    entity_description = ValveEntityDescription(key="test", reports_position=True)
    third_valve = MockValveEntity(reports_position=None)
    third_valve.entity_description = entity_description
    assert third_valve.reports_position is True


async def test_none_state(hass: HomeAssistant) -> None:
    """Test different criteria for closeness."""
    binary_valve_with_none_is_closed_attr = MockBinaryValveEntity(is_closed=None)
    binary_valve_with_none_is_closed_attr.hass = hass

    assert binary_valve_with_none_is_closed_attr.state is None

    pos_valve_with_none_is_closed_attr = MockValveEntity()
    pos_valve_with_none_is_closed_attr.hass = hass

    assert pos_valve_with_none_is_closed_attr.state is None


async def test_supported_features(hass: HomeAssistant) -> None:
    """Test valve entity with defaults."""
    valve = MockValveEntity(features=None)
    valve.hass = hass

    assert valve.supported_features is None


def call_service(hass, service, ent, position=None):
    """Call any service on entity."""
    params = {ATTR_ENTITY_ID: ent.entity_id}
    if position is not None:
        params["position"] = position
    return hass.services.async_call(DOMAIN, service, params, blocking=True)


def set_valve_position(ent, position) -> None:
    """Set a position value to a valve."""
    ent._values["current_valve_position"] = position


def is_open(hass, ent):
    """Return if the valve is closed based on the statemachine."""
    return hass.states.is_state(ent.entity_id, STATE_OPEN)


def is_opening(hass, ent):
    """Return if the valve is closed based on the statemachine."""
    return hass.states.is_state(ent.entity_id, STATE_OPENING)


def is_closed(hass, ent):
    """Return if the valve is closed based on the statemachine."""
    return hass.states.is_state(ent.entity_id, STATE_CLOSED)


def is_closing(hass, ent):
    """Return if the valve is closed based on the statemachine."""
    return hass.states.is_state(ent.entity_id, STATE_CLOSING)
