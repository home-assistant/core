"""Test climate intents."""

from collections.abc import Generator

import pytest

from homeassistant.components import conversation
from homeassistant.components.climate import (
    DOMAIN,
    ClimateEntity,
    HVACMode,
    intent as climate_intent,
)
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, entity_registry as er, intent
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
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
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
    assert await async_setup_component(hass, "homeassistant", {})
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
        hass,
        "test",
        climate_intent.INTENT_GET_TEMPERATURE,
        {},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert response.matched_states
    assert response.matched_states[0].entity_id == climate_1.entity_id
    state = response.matched_states[0]
    assert state.attributes["current_temperature"] == 10.0

    # Select by area (climate_2)
    response = await intent.async_handle(
        hass,
        "test",
        climate_intent.INTENT_GET_TEMPERATURE,
        {"area": {"value": bedroom_area.name}},
        assistant=conversation.DOMAIN,
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
        assistant=conversation.DOMAIN,
    )
    assert response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert len(response.matched_states) == 1
    assert response.matched_states[0].entity_id == climate_2.entity_id
    state = response.matched_states[0]
    assert state.attributes["current_temperature"] == 22.0

    # Check area with no climate entities
    with pytest.raises(intent.MatchFailedError) as error:
        response = await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_GET_TEMPERATURE,
            {"area": {"value": office_area.name}},
            assistant=conversation.DOMAIN,
        )

    # Exception should contain details of what we tried to match
    assert isinstance(error.value, intent.MatchFailedError)
    assert error.value.result.no_match_reason == intent.MatchFailedReason.AREA
    constraints = error.value.constraints
    assert constraints.name is None
    assert constraints.area_name == office_area.name
    assert constraints.domains and (set(constraints.domains) == {DOMAIN})
    assert constraints.device_classes is None

    # Check wrong name
    with pytest.raises(intent.MatchFailedError) as error:
        response = await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_GET_TEMPERATURE,
            {"name": {"value": "Does not exist"}},
        )

    assert isinstance(error.value, intent.MatchFailedError)
    assert error.value.result.no_match_reason == intent.MatchFailedReason.NAME
    constraints = error.value.constraints
    assert constraints.name == "Does not exist"
    assert constraints.area_name is None
    assert constraints.domains and (set(constraints.domains) == {DOMAIN})
    assert constraints.device_classes is None

    # Check wrong name with area
    with pytest.raises(intent.MatchFailedError) as error:
        response = await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_GET_TEMPERATURE,
            {"name": {"value": "Climate 1"}, "area": {"value": bedroom_area.name}},
        )

    assert isinstance(error.value, intent.MatchFailedError)
    assert error.value.result.no_match_reason == intent.MatchFailedReason.AREA
    constraints = error.value.constraints
    assert constraints.name == "Climate 1"
    assert constraints.area_name == bedroom_area.name
    assert constraints.domains and (set(constraints.domains) == {DOMAIN})
    assert constraints.device_classes is None


async def test_get_temperature_no_entities(
    hass: HomeAssistant,
) -> None:
    """Test HassClimateGetTemperature intent with no climate entities."""
    assert await async_setup_component(hass, "homeassistant", {})
    await climate_intent.async_setup_intents(hass)

    await create_mock_platform(hass, [])

    with pytest.raises(intent.MatchFailedError) as err:
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_GET_TEMPERATURE,
            {},
            assistant=conversation.DOMAIN,
        )
    assert err.value.result.no_match_reason == intent.MatchFailedReason.DOMAIN


async def test_not_exposed(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test HassClimateGetTemperature intent when entities aren't exposed."""
    assert await async_setup_component(hass, "homeassistant", {})
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

    # Add climate entities to same area
    living_room_area = area_registry.async_create(name="Living Room")
    bedroom_area = area_registry.async_create(name="Bedroom")
    entity_registry.async_update_entity(
        climate_1.entity_id, area_id=living_room_area.id
    )
    entity_registry.async_update_entity(
        climate_2.entity_id, area_id=living_room_area.id
    )

    # Should fail with empty name
    with pytest.raises(intent.InvalidSlotInfo):
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_GET_TEMPERATURE,
            {"name": {"value": ""}},
            assistant=conversation.DOMAIN,
        )

    # Should fail with empty area
    with pytest.raises(intent.InvalidSlotInfo):
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_GET_TEMPERATURE,
            {"area": {"value": ""}},
            assistant=conversation.DOMAIN,
        )

    # Expose second, hide first
    async_expose_entity(hass, conversation.DOMAIN, climate_1.entity_id, False)
    async_expose_entity(hass, conversation.DOMAIN, climate_2.entity_id, True)

    # Second climate entity is exposed
    response = await intent.async_handle(
        hass,
        "test",
        climate_intent.INTENT_GET_TEMPERATURE,
        {},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert len(response.matched_states) == 1
    assert response.matched_states[0].entity_id == climate_2.entity_id

    # Using the area should work
    response = await intent.async_handle(
        hass,
        "test",
        climate_intent.INTENT_GET_TEMPERATURE,
        {"area": {"value": living_room_area.name}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert len(response.matched_states) == 1
    assert response.matched_states[0].entity_id == climate_2.entity_id

    # Using the name of the exposed entity should work
    response = await intent.async_handle(
        hass,
        "test",
        climate_intent.INTENT_GET_TEMPERATURE,
        {"name": {"value": climate_2.name}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert len(response.matched_states) == 1
    assert response.matched_states[0].entity_id == climate_2.entity_id

    # Using the name of the *unexposed* entity should fail
    with pytest.raises(intent.MatchFailedError) as err:
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_GET_TEMPERATURE,
            {"name": {"value": climate_1.name}},
            assistant=conversation.DOMAIN,
        )
    assert err.value.result.no_match_reason == intent.MatchFailedReason.ASSISTANT

    # Expose first, hide second
    async_expose_entity(hass, conversation.DOMAIN, climate_1.entity_id, True)
    async_expose_entity(hass, conversation.DOMAIN, climate_2.entity_id, False)

    # Second climate entity is exposed
    response = await intent.async_handle(
        hass,
        "test",
        climate_intent.INTENT_GET_TEMPERATURE,
        {},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert len(response.matched_states) == 1
    assert response.matched_states[0].entity_id == climate_1.entity_id

    # Wrong area name
    with pytest.raises(intent.MatchFailedError) as err:
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_GET_TEMPERATURE,
            {"area": {"value": bedroom_area.name}},
            assistant=conversation.DOMAIN,
        )
    assert err.value.result.no_match_reason == intent.MatchFailedReason.AREA

    # Neither are exposed
    async_expose_entity(hass, conversation.DOMAIN, climate_1.entity_id, False)
    async_expose_entity(hass, conversation.DOMAIN, climate_2.entity_id, False)

    with pytest.raises(intent.MatchFailedError) as err:
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_GET_TEMPERATURE,
            {},
            assistant=conversation.DOMAIN,
        )
    assert err.value.result.no_match_reason == intent.MatchFailedReason.ASSISTANT

    # Should fail with area
    with pytest.raises(intent.MatchFailedError) as err:
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_GET_TEMPERATURE,
            {"area": {"value": living_room_area.name}},
            assistant=conversation.DOMAIN,
        )
    assert err.value.result.no_match_reason == intent.MatchFailedReason.ASSISTANT

    # Should fail with both names
    for name in (climate_1.name, climate_2.name):
        with pytest.raises(intent.MatchFailedError) as err:
            await intent.async_handle(
                hass,
                "test",
                climate_intent.INTENT_GET_TEMPERATURE,
                {"name": {"value": name}},
                assistant=conversation.DOMAIN,
            )
        assert err.value.result.no_match_reason == intent.MatchFailedReason.ASSISTANT
