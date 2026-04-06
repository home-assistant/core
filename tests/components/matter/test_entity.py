"""Test Matter entity behavior."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize(
    ("node_fixture", "entity_id", "expected_translation_key", "expected_name"),
    [
        ("mock_onoff_light", "light.mock_onoff_light", "light", "Mock OnOff Light"),
        ("mock_door_lock", "lock.mock_door_lock", "lock", "Mock Door Lock"),
        ("mock_thermostat", "climate.mock_thermostat", "thermostat", "Mock Thermostat"),
        ("mock_valve", "valve.mock_valve", "valve", "Mock Valve"),
        ("mock_fan", "fan.mocked_fan_switch", "fan", "Mocked Fan Switch"),
        ("eve_energy_plug", "switch.eve_energy_plug", "switch", "Eve Energy Plug"),
        ("mock_vacuum_cleaner", "vacuum.mock_vacuum", "vacuum", "Mock Vacuum"),
        (
            "silabs_water_heater",
            "water_heater.water_heater",
            "water_heater",
            "Water Heater",
        ),
    ],
)
async def test_single_endpoint_platform_translation_key(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    expected_translation_key: str,
    expected_name: str,
) -> None:
    """Test single-endpoint entities on platforms with _platform_translation_key.

    The translation key must always be present for state_attributes translations
    and icon translations. When there is no endpoint postfix, the entity name
    should be suppressed (None) so only the device name is displayed.
    """
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.translation_key == expected_translation_key
    # No original_name means the entity name is suppressed,
    # so only the device name is shown
    assert entry.original_name is None

    state = hass.states.get(entity_id)
    assert state is not None
    # The friendly name should be just the device name (no entity name appended)
    assert state.name == expected_name


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["inovelli_vtm31"])
async def test_multi_endpoint_entity_translation_key(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that multi-endpoint entities have a translation key and a name postfix.

    When a device has the same primary attribute on multiple endpoints,
    the entity name gets postfixed with the endpoint ID. The translation key
    must still always be set for translations.
    """
    # Endpoint 1
    entry_1 = entity_registry.async_get("light.inovelli_light_1")
    assert entry_1 is not None
    assert entry_1.translation_key == "light"
    assert entry_1.original_name == "Light (1)"

    state_1 = hass.states.get("light.inovelli_light_1")
    assert state_1 is not None
    assert state_1.name == "Inovelli Light (1)"

    # Endpoint 6
    entry_6 = entity_registry.async_get("light.inovelli_light_6")
    assert entry_6 is not None
    assert entry_6.translation_key == "light"
    assert entry_6.original_name == "Light (6)"

    state_6 = hass.states.get("light.inovelli_light_6")
    assert state_6 is not None
    assert state_6.name == "Inovelli Light (6)"


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_label_modified_entity_translation_key(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that label-modified entities have a translation key and a label postfix.

    When a device uses Matter labels to differentiate endpoints,
    the entity name gets the label as a postfix. The translation key
    must still always be set for translations.
    """
    # Top outlet
    entry_top = entity_registry.async_get("switch.eve_energy_20ecn4101_switch_top")
    assert entry_top is not None
    assert entry_top.translation_key == "switch"
    assert entry_top.original_name == "Switch (top)"

    state_top = hass.states.get("switch.eve_energy_20ecn4101_switch_top")
    assert state_top is not None
    assert state_top.name == "Eve Energy 20ECN4101 Switch (top)"

    # Bottom outlet
    entry_bottom = entity_registry.async_get(
        "switch.eve_energy_20ecn4101_switch_bottom"
    )
    assert entry_bottom is not None
    assert entry_bottom.translation_key == "switch"
    assert entry_bottom.original_name == "Switch (bottom)"

    state_bottom = hass.states.get("switch.eve_energy_20ecn4101_switch_bottom")
    assert state_bottom is not None
    assert state_bottom.name == "Eve Energy 20ECN4101 Switch (bottom)"


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["eve_thermo_v4"])
async def test_description_translation_key_not_overridden(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a description-level translation key is not overridden.

    When an entity description already sets translation_key (e.g. "child_lock"),
    the _platform_translation_key logic should not override it. The entity keeps
    its description-level translation key and name.
    """
    entry = entity_registry.async_get("switch.eve_thermo_20ebp1701_child_lock")
    assert entry is not None
    # The description-level translation key should be preserved, not overridden
    # by _platform_translation_key ("switch")
    assert entry.translation_key == "child_lock"
    assert entry.original_name == "Child lock"

    state = hass.states.get("switch.eve_thermo_20ebp1701_child_lock")
    assert state is not None
    assert state.name == "Eve Thermo 20EBP1701 Child lock"


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["air_quality_sensor"])
async def test_entity_name_from_description_translation_key(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity name derived from an explicit description translation key.

    Sensor entities do not set _platform_translation_key on the platform class.
    When the entity description sets translation_key explicitly, the entity name
    is derived from that translation key.
    """
    entry = entity_registry.async_get(
        "sensor.lightfi_aq1_air_quality_sensor_air_quality"
    )
    assert entry is not None
    assert entry.translation_key == "air_quality"
    assert entry.original_name == "Air quality"

    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_air_quality")
    assert state is not None
    assert state.name == "lightfi-aq1-air-quality-sensor Air quality"


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["mock_temperature_sensor"])
async def test_entity_name_from_device_class(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity name derived from device class when no translation key is set.

    Sensor entities do not set _platform_translation_key on the platform class.
    When the entity description also has no translation_key, the entity name
    is derived from the device class instead.
    """
    entry = entity_registry.async_get("sensor.mock_temperature_sensor_temperature")
    assert entry is not None
    assert entry.translation_key is None
    # Name is derived from the device class
    assert entry.original_name == "Temperature"

    state = hass.states.get("sensor.mock_temperature_sensor_temperature")
    assert state is not None
    assert state.name == "Mock Temperature Sensor Temperature"
