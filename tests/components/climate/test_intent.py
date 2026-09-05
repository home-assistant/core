"""Test climate intents."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import conversation
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_TEMPERATURE,
    DOMAIN,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    intent as climate_intent,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    entity_registry as er,
    floor_registry as fr,
    intent,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
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
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.CLIMATE]
        )
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
        async_add_entities: AddConfigEntryEntitiesCallback,
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
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the thermostat temperature."""
        value = kwargs[ATTR_TEMPERATURE]
        self._attr_target_temperature = value


class MockClimateEntityNoSetTemperature(ClimateEntity):
    """Mock Climate device to use in tests."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_mode = HVACMode.OFF
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]


class MockClimateEntityWithFanMode(ClimateEntity):
    """Mock Climate device with fan mode support to use in tests."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_mode = HVACMode.OFF
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.FAN_MODE
    # Mixed casing and a vendor-specific mode, as real integrations report.
    _attr_fan_modes = ["auto", "Low", "Turbo"]
    _attr_fan_mode = "auto"

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        self._attr_fan_mode = fan_mode


class MockClimateEntityNoFanModes(MockClimateEntityWithFanMode):
    """Mock Climate device claiming fan mode support without reporting modes."""

    _attr_fan_modes = None
    _attr_fan_mode = None


async def setup_fan_mode_entities(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    floor_registry: fr.FloorRegistry,
) -> tuple[ClimateEntity, ClimateEntity]:
    """Set up two fan mode capable entities in separate areas and floors.

    climate_1 => Living Room => First floor
    climate_2 => Bedroom => Second floor
    """
    climate_1 = MockClimateEntityWithFanMode()
    climate_1._attr_name = "Climate 1"
    climate_1._attr_unique_id = "1234"
    entity_registry.async_get_or_create(
        DOMAIN, "test", "1234", suggested_object_id="climate_1"
    )

    climate_2 = MockClimateEntityWithFanMode()
    climate_2._attr_name = "Climate 2"
    climate_2._attr_unique_id = "5678"
    entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", suggested_object_id="climate_2"
    )

    await create_mock_platform(hass, [climate_1, climate_2])

    living_room_area = area_registry.async_create(name="Living Room")
    bedroom_area = area_registry.async_create(name="Bedroom")
    entity_registry.async_update_entity(
        climate_1.entity_id, area_id=living_room_area.id
    )
    entity_registry.async_update_entity(climate_2.entity_id, area_id=bedroom_area.id)

    first_floor = floor_registry.async_create("First floor")
    second_floor = floor_registry.async_create("Second floor")
    area_registry.async_update(living_room_area.id, floor_id=first_floor.floor_id)
    area_registry.async_update(bedroom_area.id, floor_id=second_floor.floor_id)

    return climate_1, climate_2


async def test_set_temperature(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test HassClimateSetTemperature intent."""
    assert await async_setup_component(hass, "homeassistant", {})
    await climate_intent.async_setup_intents(hass)

    climate_1 = MockClimateEntity()
    climate_1._attr_name = "Climate 1"
    climate_1._attr_unique_id = "1234"
    climate_1._attr_current_temperature = 10.0
    climate_1._attr_target_temperature = 10.0
    entity_registry.async_get_or_create(
        DOMAIN, "test", "1234", suggested_object_id="climate_1"
    )

    climate_2 = MockClimateEntity()
    climate_2._attr_name = "Climate 2"
    climate_2._attr_unique_id = "5678"
    climate_2._attr_current_temperature = 22.0
    climate_2._attr_target_temperature = 22.0
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

    # Put areas on different floors:
    # first floor => living room and office
    # upstairs => bedroom
    first_floor = floor_registry.async_create("First floor")
    living_room_area = area_registry.async_update(
        living_room_area.id, floor_id=first_floor.floor_id
    )
    office_area = area_registry.async_update(
        office_area.id, floor_id=first_floor.floor_id
    )

    second_floor = floor_registry.async_create("Second floor")
    bedroom_area = area_registry.async_update(
        bedroom_area.id, floor_id=second_floor.floor_id
    )

    # Cannot target multiple climate devices
    with pytest.raises(intent.MatchFailedError) as err:
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_SET_TEMPERATURE,
            {"temperature": {"value": 20}},
            assistant=conversation.DOMAIN,
        )
    assert err.value.result.no_match_reason is intent.MatchFailedReason.MULTIPLE_TARGETS

    # Select by area explicitly (climate_2)
    response = await intent.async_handle(
        hass,
        "test",
        climate_intent.INTENT_SET_TEMPERATURE,
        {
            "area": {"value": bedroom_area.name},
            "floor": {"value": ""},
            "name": {"value": ""},
            "temperature": {"value": 20.1},
        },
        assistant=conversation.DOMAIN,
    )
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(response.matched_states) == 1
    assert response.matched_states[0].entity_id == climate_2.entity_id
    state = hass.states.get(climate_2.entity_id)
    assert state.attributes[ATTR_TEMPERATURE] == 20.1

    # Select by area implicitly (climate_2)
    response = await intent.async_handle(
        hass,
        "test",
        climate_intent.INTENT_SET_TEMPERATURE,
        {
            "preferred_area_id": {"value": bedroom_area.id},
            "temperature": {"value": 20.2},
        },
        assistant=conversation.DOMAIN,
    )
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert response.matched_states
    assert response.matched_states[0].entity_id == climate_2.entity_id
    state = hass.states.get(climate_2.entity_id)
    assert state.attributes[ATTR_TEMPERATURE] == 20.2

    # Select by floor explicitly (climate_2)
    response = await intent.async_handle(
        hass,
        "test",
        climate_intent.INTENT_SET_TEMPERATURE,
        {"floor": {"value": second_floor.name}, "temperature": {"value": 20.3}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert response.matched_states
    assert response.matched_states[0].entity_id == climate_2.entity_id
    state = hass.states.get(climate_2.entity_id)
    assert state.attributes[ATTR_TEMPERATURE] == 20.3

    # Select by floor implicitly (climate_2)
    response = await intent.async_handle(
        hass,
        "test",
        climate_intent.INTENT_SET_TEMPERATURE,
        {
            "preferred_floor_id": {"value": second_floor.floor_id},
            "temperature": {"value": 20.4},
        },
        assistant=conversation.DOMAIN,
    )
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert response.matched_states
    assert response.matched_states[0].entity_id == climate_2.entity_id
    state = hass.states.get(climate_2.entity_id)
    assert state.attributes[ATTR_TEMPERATURE] == 20.4

    # Select by name (climate_2)
    response = await intent.async_handle(
        hass,
        "test",
        climate_intent.INTENT_SET_TEMPERATURE,
        {"name": {"value": "Climate 2"}, "temperature": {"value": 20.5}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(response.matched_states) == 1
    assert response.matched_states[0].entity_id == climate_2.entity_id
    state = hass.states.get(climate_2.entity_id)
    assert state.attributes[ATTR_TEMPERATURE] == 20.5

    # Check area with no climate entities (explicit)
    with pytest.raises(intent.MatchFailedError) as error:
        response = await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_SET_TEMPERATURE,
            {"area": {"value": office_area.name}, "temperature": {"value": 20.6}},
            assistant=conversation.DOMAIN,
        )

    # Exception should contain details of what we tried to match
    assert isinstance(error.value, intent.MatchFailedError)
    assert error.value.result.no_match_reason is intent.MatchFailedReason.AREA
    constraints = error.value.constraints
    assert constraints.name is None
    assert constraints.area_name == office_area.name
    assert constraints.domains and (set(constraints.domains) == {DOMAIN})
    assert constraints.device_classes is None

    # Implicit area with no climate entities will fail with multiple targets
    with pytest.raises(intent.MatchFailedError) as err:
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_SET_TEMPERATURE,
            {
                "preferred_area_id": {"value": office_area.id},
                "temperature": {"value": 20.7},
            },
            assistant=conversation.DOMAIN,
        )
    assert err.value.result.no_match_reason is intent.MatchFailedReason.MULTIPLE_TARGETS


async def test_set_temperature_empty_targets(hass: HomeAssistant) -> None:
    """Test empty targets have the same behavior as omitted targets."""
    assert await async_setup_component(hass, "homeassistant", {})
    await climate_intent.async_setup_intents(hass)

    climate_1 = MockClimateEntity()
    climate_1._attr_name = "Climate 1"
    climate_1._attr_unique_id = "1234"

    climate_2 = MockClimateEntity()
    climate_2._attr_name = "Climate 2"
    climate_2._attr_unique_id = "5678"

    await create_mock_platform(hass, [climate_1, climate_2])

    with pytest.raises(intent.MatchFailedError) as err:
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_SET_TEMPERATURE,
            {
                "area": {"value": ""},
                "floor": {"value": ""},
                "name": {"value": ""},
                "temperature": {"value": 20},
            },
            assistant=conversation.DOMAIN,
        )
    assert err.value.result.no_match_reason is intent.MatchFailedReason.MULTIPLE_TARGETS
    assert err.value.constraints.name is None
    assert err.value.constraints.area_name is None
    assert err.value.constraints.floor_name is None


@pytest.mark.parametrize("target", ["area", "floor", "name"])
async def test_set_temperature_whitespace_target(
    hass: HomeAssistant, target: str
) -> None:
    """Test whitespace-only targets are invalid."""
    await climate_intent.async_setup_intents(hass)

    with pytest.raises(intent.InvalidSlotInfo):
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_SET_TEMPERATURE,
            {target: {"value": " "}, "temperature": {"value": 20}},
            assistant=conversation.DOMAIN,
        )


async def test_set_temperature_no_entities(
    hass: HomeAssistant,
) -> None:
    """Test HassClimateSetTemperature intent with no climate entities."""
    assert await async_setup_component(hass, "homeassistant", {})
    await climate_intent.async_setup_intents(hass)

    await create_mock_platform(hass, [])

    with pytest.raises(intent.MatchFailedError) as err:
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_SET_TEMPERATURE,
            {"temperature": {"value": 20}},
            assistant=conversation.DOMAIN,
        )
    assert err.value.result.no_match_reason is intent.MatchFailedReason.DOMAIN


async def test_set_temperature_not_supported(hass: HomeAssistant) -> None:
    """Test HassClimateSetTemperature intent without support."""
    assert await async_setup_component(hass, "homeassistant", {})
    await climate_intent.async_setup_intents(hass)

    climate_1 = MockClimateEntityNoSetTemperature()
    climate_1._attr_name = "Climate 1"
    climate_1._attr_unique_id = "1234"
    climate_1._attr_current_temperature = 10.0
    climate_1._attr_target_temperature = 10.0

    await create_mock_platform(hass, [climate_1])

    with pytest.raises(intent.MatchFailedError) as error:
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_SET_TEMPERATURE,
            {"temperature": {"value": 20.0}},
            assistant=conversation.DOMAIN,
        )

    # Exception should contain details of what we tried to match
    assert isinstance(error.value, intent.MatchFailedError)
    assert error.value.result.no_match_reason is intent.MatchFailedReason.FEATURE


@pytest.mark.parametrize(
    ("requested_fan_mode", "expected_fan_mode"),
    [
        pytest.param("auto", "auto", id="exact"),
        pytest.param("LOW", "Low", id="differing_case"),
        pytest.param("Turbo", "Turbo", id="vendor_specific"),
    ],
)
async def test_set_fan_mode(
    hass: HomeAssistant,
    requested_fan_mode: str,
    expected_fan_mode: str,
) -> None:
    """Test HassClimateSetFanMode intent resolves against the entity's fan modes."""
    assert await async_setup_component(hass, "homeassistant", {})
    await climate_intent.async_setup_intents(hass)

    climate_1 = MockClimateEntityWithFanMode()
    climate_1._attr_name = "Climate 1"
    climate_1._attr_unique_id = "1234"

    await create_mock_platform(hass, [climate_1])

    response = await intent.async_handle(
        hass,
        "test",
        climate_intent.INTENT_SET_FAN_MODE,
        {"fan_mode": {"value": requested_fan_mode}},
        assistant=conversation.DOMAIN,
    )
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(response.matched_states) == 1
    assert response.matched_states[0].entity_id == climate_1.entity_id

    state = hass.states.get(climate_1.entity_id)
    assert state.attributes[ATTR_FAN_MODE] == expected_fan_mode


async def test_set_fan_mode_localized(hass: HomeAssistant) -> None:
    """Test HassClimateSetFanMode intent with a localized fan mode name."""
    assert await async_setup_component(hass, "homeassistant", {})
    await climate_intent.async_setup_intents(hass)

    climate_1 = MockClimateEntityWithFanMode()
    climate_1._attr_name = "Climate 1"
    climate_1._attr_unique_id = "1234"

    await create_mock_platform(hass, [climate_1])

    # Only English translations are generated for tests, so stub the German ones.
    with patch(
        "homeassistant.components.climate.intent.translation.async_get_translations",
        return_value={
            f"{climate_intent.FAN_MODE_TRANSLATION_PREFIX}auto": "Automatisch",
            f"{climate_intent.FAN_MODE_TRANSLATION_PREFIX}low": "Niedrig",
        },
    ):
        response = await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_SET_FAN_MODE,
            {"fan_mode": {"value": "niedrig"}},
            language="de",
            assistant=conversation.DOMAIN,
        )

    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    state = hass.states.get(climate_1.entity_id)
    assert state.attributes[ATTR_FAN_MODE] == "Low"


async def test_set_fan_mode_unsupported_mode(hass: HomeAssistant) -> None:
    """Test HassClimateSetFanMode intent with a mode the entity does not have."""
    assert await async_setup_component(hass, "homeassistant", {})
    await climate_intent.async_setup_intents(hass)

    climate_1 = MockClimateEntityWithFanMode()
    climate_1._attr_name = "Climate 1"
    climate_1._attr_unique_id = "1234"

    await create_mock_platform(hass, [climate_1])

    with pytest.raises(intent.IntentHandleError):
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_SET_FAN_MODE,
            {"fan_mode": {"value": "diffuse"}},
            assistant=conversation.DOMAIN,
        )

    # Mode was not affected by failed intent
    state = hass.states.get(climate_1.entity_id)
    assert state.attributes[ATTR_FAN_MODE] == "auto"


async def test_set_fan_mode_not_supported(hass: HomeAssistant) -> None:
    """Test HassClimateSetFanMode intent on an entity without fan mode support."""
    assert await async_setup_component(hass, "homeassistant", {})
    await climate_intent.async_setup_intents(hass)

    climate_1 = MockClimateEntity()
    climate_1._attr_name = "Climate 1"
    climate_1._attr_unique_id = "1234"

    await create_mock_platform(hass, [climate_1])

    with pytest.raises(intent.MatchFailedError) as error:
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_SET_FAN_MODE,
            {"fan_mode": {"value": "auto"}},
            assistant=conversation.DOMAIN,
        )

    assert error.value.result.no_match_reason is intent.MatchFailedReason.FEATURE


@pytest.mark.parametrize(
    "target_slots",
    [
        pytest.param({"name": {"value": "Climate 2"}}, id="name"),
        pytest.param({"area": {"value": "Bedroom"}}, id="area"),
        pytest.param({"floor": {"value": "Second floor"}}, id="floor"),
    ],
)
async def test_set_fan_mode_targeting(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    floor_registry: fr.FloorRegistry,
    target_slots: dict[str, dict[str, str]],
) -> None:
    """Test HassClimateSetFanMode intent targeting by name, area and floor."""
    assert await async_setup_component(hass, "homeassistant", {})
    await climate_intent.async_setup_intents(hass)

    climate_1, climate_2 = await setup_fan_mode_entities(
        hass, area_registry, entity_registry, floor_registry
    )

    response = await intent.async_handle(
        hass,
        "test",
        climate_intent.INTENT_SET_FAN_MODE,
        {"fan_mode": {"value": "Low"}} | target_slots,
        assistant=conversation.DOMAIN,
    )
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(response.matched_states) == 1
    assert response.matched_states[0].entity_id == climate_2.entity_id

    assert hass.states.get(climate_2.entity_id).attributes[ATTR_FAN_MODE] == "Low"
    # The entity in the other area/floor is untouched
    assert hass.states.get(climate_1.entity_id).attributes[ATTR_FAN_MODE] == "auto"


async def test_set_fan_mode_preferred_area_and_floor(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test HassClimateSetFanMode intent with an implicit area and floor."""
    assert await async_setup_component(hass, "homeassistant", {})
    await climate_intent.async_setup_intents(hass)

    climate_1, climate_2 = await setup_fan_mode_entities(
        hass, area_registry, entity_registry, floor_registry
    )
    bedroom_area = area_registry.async_get_area_by_name("Bedroom")
    second_floor = floor_registry.async_get_floor_by_name("Second floor")

    # Cannot target multiple climate devices without a preference
    with pytest.raises(intent.MatchFailedError) as err:
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_SET_FAN_MODE,
            {"fan_mode": {"value": "Low"}},
            assistant=conversation.DOMAIN,
        )
    assert err.value.result.no_match_reason is intent.MatchFailedReason.MULTIPLE_TARGETS

    # Select by area implicitly (climate_2)
    response = await intent.async_handle(
        hass,
        "test",
        climate_intent.INTENT_SET_FAN_MODE,
        {
            "fan_mode": {"value": "Low"},
            "preferred_area_id": {"value": bedroom_area.id},
        },
        assistant=conversation.DOMAIN,
    )
    assert response.matched_states[0].entity_id == climate_2.entity_id
    assert hass.states.get(climate_2.entity_id).attributes[ATTR_FAN_MODE] == "Low"

    # Select by floor implicitly (climate_2)
    response = await intent.async_handle(
        hass,
        "test",
        climate_intent.INTENT_SET_FAN_MODE,
        {
            "fan_mode": {"value": "Turbo"},
            "preferred_floor_id": {"value": second_floor.floor_id},
        },
        assistant=conversation.DOMAIN,
    )
    assert response.matched_states[0].entity_id == climate_2.entity_id
    assert hass.states.get(climate_2.entity_id).attributes[ATTR_FAN_MODE] == "Turbo"

    assert hass.states.get(climate_1.entity_id).attributes[ATTR_FAN_MODE] == "auto"


@pytest.mark.parametrize(
    ("entity_class", "requested_fan_mode"),
    [
        # Matches no fan mode and no translated fan mode name
        pytest.param(MockClimateEntityWithFanMode, "hyperdrive", id="unknown_mode"),
        # Entity claims fan mode support but reports no modes at all
        pytest.param(MockClimateEntityNoFanModes, "auto", id="no_fan_modes"),
    ],
)
async def test_set_fan_mode_unresolvable(
    hass: HomeAssistant,
    entity_class: type[ClimateEntity],
    requested_fan_mode: str,
) -> None:
    """Test HassClimateSetFanMode intent when the mode cannot be resolved."""
    assert await async_setup_component(hass, "homeassistant", {})
    await climate_intent.async_setup_intents(hass)

    climate_1 = entity_class()
    climate_1._attr_name = "Climate 1"
    climate_1._attr_unique_id = "1234"

    await create_mock_platform(hass, [climate_1])

    with pytest.raises(intent.IntentHandleError):
        await intent.async_handle(
            hass,
            "test",
            climate_intent.INTENT_SET_FAN_MODE,
            {"fan_mode": {"value": requested_fan_mode}},
            assistant=conversation.DOMAIN,
        )
