"""The tests for Valve."""
from collections.abc import Generator

import pytest

from homeassistant.components.valve import (
    DOMAIN,
    ValveEntity,
    ValveEntityFeature,
    is_closed as valve_is_closed,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlow
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
    SERVICE_TOGGLE,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.setup import async_setup_component

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

    def __init__(
        self,
        unique_id: str = "mock_valve",
        name: str = "Valve",
        features: ValveEntityFeature = ValveEntityFeature(0),
    ) -> None:
        """Initialize the valve."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_supported_features = features
        self._attr_is_closed = None


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None, None, None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


async def test_valve_setup(hass: HomeAssistant) -> None:
    """Test setup and tear down of valve platform and entity."""

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

    entity1 = MockValveEntity()
    entity1.entity_id = "valve.mock_valve"

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test platform via config entry."""
        async_add_entities([entity1])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert hass.states.get(entity1.entity_id)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    entity_state = hass.states.get(entity1.entity_id)

    assert entity_state
    assert entity_state.state == STATE_UNAVAILABLE


async def test_services(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    """Test the provided services."""
    platform = getattr(hass.components, "test.valve")

    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    # ent1 = valve without position
    # ent2 = valve with position
    ent1, ent2 = platform.ENTITIES

    # Test init all valves should be open
    assert is_open(hass, ent1)
    assert is_open(hass, ent2)

    # call basic toggle services
    await call_service(hass, SERVICE_TOGGLE, ent1)
    await call_service(hass, SERVICE_TOGGLE, ent2)

    # entities without stop should be closed and with stop should be closing
    assert is_closed(hass, ent1)
    assert is_closing(hass, ent2)

    # call basic toggle services and set different valve position states
    await call_service(hass, SERVICE_TOGGLE, ent1)
    set_valve_position(ent2, 0)
    await call_service(hass, SERVICE_TOGGLE, ent2)

    # entities should be in correct state depending on the SUPPORT_STOP feature and valve position
    assert is_open(hass, ent1)
    assert is_closed(hass, ent2)

    # call basic toggle services
    await call_service(hass, SERVICE_TOGGLE, ent1)
    await call_service(hass, SERVICE_TOGGLE, ent2)

    # entities should be in correct state depending on the SUPPORT_STOP feature and valve position
    assert is_closed(hass, ent1)
    assert is_opening(hass, ent2)


def call_service(hass, service, ent):
    """Call any service on entity."""
    return hass.services.async_call(
        DOMAIN, service, {ATTR_ENTITY_ID: ent.entity_id}, blocking=True
    )


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
    return valve_is_closed(hass, ent.entity_id)


def is_closing(hass, ent):
    """Return if the valve is closed based on the statemachine."""
    return hass.states.is_state(ent.entity_id, STATE_CLOSING)
