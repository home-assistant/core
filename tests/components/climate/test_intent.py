"""Test climate intents."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.climate import (
    DOMAIN,
    ClimateEntity,
    HVACMode,
    intent as climate_intent,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, entity_registry as er, intent
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
        await hass.config_entries.async_forward_entry_setup(config_entry, DOMAIN)
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> bool:
        await hass.config_entries.async_unload_platforms(config_entry, [Platform.TODO])
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


async def create_mock_platform(
    hass: HomeAssistant,
    entities: list[ClimateEntity],
) -> MockConfigEntry:
    """Create a todo platform with the specified entities."""

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

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


class MockClimateEntity(ClimateEntity):
    """Mock Climate device to use in tests."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_mode = HVACMode.OFF
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]


async def test_get_temperature(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test HassClimateGetTemperature intent."""
    await climate_intent.async_setup_intents(hass)

    climate_1 = MockClimateEntity()
    climate_1._attr_name = "Climate 1"
    climate_1._attr_unique_id = "1234"
    climate_1._attr_current_temperature = 10.0
    entity_registry.async_get_or_create(
        DOMAIN, "test", "1234", suggested_object_id="climate_1"
    )

    climate_2 = MockClimateEntity()
    climate_2._attr_name = "Climate 2"
    climate_2._attr_unique_id = "5678"
    climate_2._attr_current_temperature = 22.0
    entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", suggested_object_id="climate_2"
    )

    await create_mock_platform(hass, [climate_1, climate_2])

    # Add climate entities to different areas:
    # climate_1 => living room
    # climate_2 => bedroom
    # nothing in office
    living_room_area = area_registry.async_create(name="Living Room")
    bedroom_area = area_registry.async_create(name="Bedroom")
    office_area = area_registry.async_create(name="Office")

    entity_registry.async_update_entity(
        climate_1.entity_id, area_id=living_room_area.id
    )
    entity_registry.async_update_entity(climate_2.entity_id, area_id=bedroom_area.id)

    # First climate entity will be selected (no area)
    response = await intent.async_handle(
        hass, "test", climate_intent.INTENT_GET_TEMPERATURE, {}
    )
    assert response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert len(response.matched_states) == 1
    assert response.matched_states[0].entity_id == climate_1.entity_id
    state = response.matched_states[0]
    assert state.attributes["current_temperature"] == 10.0

    # Select by area (climate_2)
    response = await intent.async_handle(
        hass,
        "test",
        climate_intent.INTENT_GET_TEMPERATURE,
        {"area": {"value": bedroom_area.name}},
    )
    assert response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert len(response.matched_states) == 1
    assert response.matched_states[0].entity_id == climate_2.entity_id
    state = response.matched_states[0]
    assert state.attributes["current_temperature"] == 22.0

    # Select by name (climate_2)
    response = await intent.async_handle(
        hass,
        "test",
        climate_intent.INTENT_GET_TEMPERATURE,
        {"name": {"value": "Climate 2"}},
    )
    assert response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert len(response.matched_states) == 1
    assert response.matched_states[0].entity_id == climate_2.entity_id
    state = response.matched_states[0]
    assert state.attributes["current_temperature"] == 22.0

    # Check area with no climate entities
    with pytest.raises(intent.NoStatesMatchedError) as error:
        response = await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_GET_TEMPERATURE,
            {"area": {"value": office_area.name}},
        )

    # Exception should contain details of what we tried to match
    assert isinstance(error.value, intent.NoStatesMatchedError)
    assert error.value.name is None
    assert error.value.area == office_area.name
    assert error.value.domains == {DOMAIN}
    assert error.value.device_classes is None

    # Check wrong name
    with pytest.raises(intent.NoStatesMatchedError) as error:
        response = await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_GET_TEMPERATURE,
            {"name": {"value": "Does not exist"}},
        )

    assert isinstance(error.value, intent.NoStatesMatchedError)
    assert error.value.name == "Does not exist"
    assert error.value.area is None
    assert error.value.domains == {DOMAIN}
    assert error.value.device_classes is None

    # Check wrong name with area
    with pytest.raises(intent.NoStatesMatchedError) as error:
        response = await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_GET_TEMPERATURE,
            {"name": {"value": "Climate 1"}, "area": {"value": bedroom_area.name}},
        )

    assert isinstance(error.value, intent.NoStatesMatchedError)
    assert error.value.name == "Climate 1"
    assert error.value.area == bedroom_area.name
    assert error.value.domains == {DOMAIN}
    assert error.value.device_classes is None


async def test_get_temperature_no_entities(
    hass: HomeAssistant,
) -> None:
    """Test HassClimateGetTemperature intent with no climate entities."""
    await climate_intent.async_setup_intents(hass)

    await create_mock_platform(hass, [])

    with pytest.raises(intent.IntentHandleError):
        await intent.async_handle(
            hass, "test", climate_intent.INTENT_GET_TEMPERATURE, {}
        )


async def test_get_temperature_no_state(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test HassClimateGetTemperature intent when states are missing."""
    await climate_intent.async_setup_intents(hass)

    climate_1 = MockClimateEntity()
    climate_1._attr_name = "Climate 1"
    climate_1._attr_unique_id = "1234"
    entity_registry.async_get_or_create(
        DOMAIN, "test", "1234", suggested_object_id="climate_1"
    )

    await create_mock_platform(hass, [climate_1])

    living_room_area = area_registry.async_create(name="Living Room")
    entity_registry.async_update_entity(
        climate_1.entity_id, area_id=living_room_area.id
    )

    with (
        patch("homeassistant.core.StateMachine.get", return_value=None),
        pytest.raises(intent.IntentHandleError),
    ):
        await intent.async_handle(
            hass, "test", climate_intent.INTENT_GET_TEMPERATURE, {}
        )

    with (
        patch("homeassistant.core.StateMachine.async_all", return_value=[]),
        pytest.raises(intent.NoStatesMatchedError) as error,
    ):
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_GET_TEMPERATURE,
            {"area": {"value": "Living Room"}},
        )

    # Exception should contain details of what we tried to match
    assert isinstance(error.value, intent.NoStatesMatchedError)
    assert error.value.name is None
    assert error.value.area == "Living Room"
    assert error.value.domains == {DOMAIN}
    assert error.value.device_classes is None
