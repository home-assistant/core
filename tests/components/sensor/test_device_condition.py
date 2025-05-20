"""The test for sensor device automation."""

import pytest
from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
    device_condition,
)
from homeassistant.components.sensor.const import NON_NUMERIC_DEVICE_CLASSES
from homeassistant.components.sensor.device_condition import ENTITY_CONDITIONS
from homeassistant.const import CONF_PLATFORM, PERCENTAGE, STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryHider
from homeassistant.setup import async_setup_component
from homeassistant.util.json import load_json

from .common import UNITS_OF_MEASUREMENT, MockSensor

from tests.common import (
    MockConfigEntry,
    async_get_device_automation_capabilities,
    async_get_device_automations,
    setup_test_component_platform,
)


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.mark.parametrize(
    "device_class",
    [
        device_class
        for device_class in SensorDeviceClass
        if device_class not in NON_NUMERIC_DEVICE_CLASSES
    ],
)
def test_matches_device_classes(device_class: SensorDeviceClass) -> None:
    """Ensure device class constants are declared in device_condition module."""
    # Ensure it has corresponding CONF_IS_*** constant
    constant_name = {
        SensorDeviceClass.BATTERY: "CONF_IS_BATTERY_LEVEL",
        SensorDeviceClass.CO: "CONF_IS_CO",
        SensorDeviceClass.CO2: "CONF_IS_CO2",
        SensorDeviceClass.ENERGY_STORAGE: "CONF_IS_ENERGY",
        SensorDeviceClass.VOLUME_STORAGE: "CONF_IS_VOLUME",
    }.get(device_class, f"CONF_IS_{device_class.value.upper()}")
    assert hasattr(device_condition, constant_name), f"Missing constant {constant_name}"

    # Ensure it has correct value
    constant_value = {
        SensorDeviceClass.BATTERY: "is_battery_level",
        SensorDeviceClass.ENERGY_STORAGE: "is_energy",
        SensorDeviceClass.VOLUME_STORAGE: "is_volume",
    }.get(device_class, f"is_{device_class.value}")
    assert getattr(device_condition, constant_name) == constant_value

    # Ensure it is present in ENTITY_CONDITIONS
    assert device_class in ENTITY_CONDITIONS
    # Ensure it is present in CONDITION_SCHEMA
    schema_types = (
        device_condition.CONDITION_SCHEMA.validators[0].schema["type"].container
    )
    assert constant_value in schema_types
    # Ensure it is present in string.json
    strings = load_json("homeassistant/components/sensor/strings.json")
    assert constant_value in strings["device_automation"]["condition_type"]


async def test_get_conditions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_sensor_entities: dict[str, MockSensor],
) -> None:
    """Test we get the expected conditions from a sensor."""
    setup_test_component_platform(hass, DOMAIN, mock_sensor_entities.values())
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()
    sensor_entries = {}

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    for device_class in SensorDeviceClass:
        sensor_entries[device_class] = entity_registry.async_get_or_create(
            DOMAIN,
            "test",
            mock_sensor_entities[device_class].unique_id,
            device_id=device_entry.id,
        )

    expected_conditions = [
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": condition["type"],
            "device_id": device_entry.id,
            "entity_id": sensor_entries[device_class].id,
            "metadata": {"secondary": False},
        }
        for device_class in SensorDeviceClass
        if device_class in UNITS_OF_MEASUREMENT
        for condition in ENTITY_CONDITIONS[device_class]
        if device_class != "none"
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert len(conditions) == 28
    assert conditions == unordered(expected_conditions)


@pytest.mark.parametrize(
    ("hidden_by", "entity_category"),
    [
        (RegistryEntryHider.INTEGRATION, None),
        (RegistryEntryHider.USER, None),
        (None, EntityCategory.CONFIG),
        (None, EntityCategory.DIAGNOSTIC),
    ],
)
async def test_get_conditions_hidden_auxiliary(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hidden_by,
    entity_category,
) -> None:
    """Test we get the expected conditions from a hidden or auxiliary entity."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        "5678",
        device_id=device_entry.id,
        entity_category=entity_category,
        hidden_by=hidden_by,
        unit_of_measurement="dogs",
    )
    expected_conditions = [
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": condition,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": True},
        }
        for condition in ("is_value",)
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert conditions == unordered(expected_conditions)


async def test_get_conditions_no_state(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected conditions from a sensor."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    sensor_entries = {}
    for device_class in SensorDeviceClass:
        sensor_entries[device_class] = entity_registry.async_get_or_create(
            DOMAIN,
            "test",
            f"5678_{device_class}",
            device_id=device_entry.id,
            original_device_class=device_class,
            unit_of_measurement=UNITS_OF_MEASUREMENT.get(device_class),
        )

    await hass.async_block_till_done()

    expected_conditions = [
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": condition["type"],
            "device_id": device_entry.id,
            "entity_id": sensor_entries[device_class].id,
            "metadata": {"secondary": False},
        }
        for device_class in SensorDeviceClass
        if device_class in UNITS_OF_MEASUREMENT
        for condition in ENTITY_CONDITIONS[device_class]
        if device_class != "none"
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert conditions == unordered(expected_conditions)


@pytest.mark.parametrize(
    ("state_class", "unit", "condition_types"),
    [
        (SensorStateClass.MEASUREMENT, None, ["is_value"]),
        (SensorStateClass.TOTAL, None, ["is_value"]),
        (SensorStateClass.TOTAL_INCREASING, None, ["is_value"]),
        (SensorStateClass.MEASUREMENT, "dogs", ["is_value"]),
        (None, None, []),
    ],
)
async def test_get_conditions_no_unit_or_stateclass(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    state_class,
    unit,
    condition_types,
) -> None:
    """Test we get the expected conditions from an entity with no unit or state class."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        "5678",
        capabilities={ATTR_STATE_CLASS: state_class},
        device_id=device_entry.id,
        unit_of_measurement=unit,
    )
    expected_conditions = [
        {
            "condition": "device",
            "domain": DOMAIN,
            "type": condition,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        }
        for condition in condition_types
    ]
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert conditions == unordered(expected_conditions)


@pytest.mark.parametrize(
    ("set_state", "device_class_reg", "device_class_state", "unit_reg", "unit_state"),
    [
        (False, SensorDeviceClass.BATTERY, None, PERCENTAGE, None),
        (True, None, SensorDeviceClass.BATTERY, None, PERCENTAGE),
    ],
)
async def test_get_condition_capabilities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_sensor_entities: dict[str, MockSensor],
    set_state,
    device_class_reg,
    device_class_state,
    unit_reg,
    unit_state,
) -> None:
    """Test we get the expected capabilities from a sensor condition."""
    setup_test_component_platform(hass, DOMAIN, mock_sensor_entities.values())

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_id = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        mock_sensor_entities["battery"].unique_id,
        device_id=device_entry.id,
        original_device_class=device_class_reg,
        unit_of_measurement=unit_reg,
    ).entity_id
    if set_state:
        hass.states.async_set(
            entity_id,
            None,
            {"device_class": device_class_state, "unit_of_measurement": unit_state},
        )

    expected_capabilities = {
        "extra_fields": [
            {
                "description": {"suffix": PERCENTAGE},
                "name": "above",
                "optional": True,
                "type": "float",
            },
            {
                "description": {"suffix": PERCENTAGE},
                "name": "below",
                "optional": True,
                "type": "float",
            },
        ]
    }
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert len(conditions) == 1
    for condition in conditions:
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.CONDITION, condition
        )
        assert capabilities == expected_capabilities


@pytest.mark.parametrize(
    ("set_state", "device_class_reg", "device_class_state", "unit_reg", "unit_state"),
    [
        (False, SensorDeviceClass.BATTERY, None, PERCENTAGE, None),
        (True, None, SensorDeviceClass.BATTERY, None, PERCENTAGE),
    ],
)
async def test_get_condition_capabilities_legacy(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_sensor_entities: dict[str, MockSensor],
    set_state,
    device_class_reg,
    device_class_state,
    unit_reg,
    unit_state,
) -> None:
    """Test we get the expected capabilities from a sensor condition."""
    setup_test_component_platform(hass, DOMAIN, mock_sensor_entities.values())

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_id = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        mock_sensor_entities["battery"].unique_id,
        device_id=device_entry.id,
        original_device_class=device_class_reg,
        unit_of_measurement=unit_reg,
    ).entity_id
    if set_state:
        hass.states.async_set(
            entity_id,
            None,
            {"device_class": device_class_state, "unit_of_measurement": unit_state},
        )

    expected_capabilities = {
        "extra_fields": [
            {
                "description": {"suffix": PERCENTAGE},
                "name": "above",
                "optional": True,
                "type": "float",
            },
            {
                "description": {"suffix": PERCENTAGE},
                "name": "below",
                "optional": True,
                "type": "float",
            },
        ]
    }
    conditions = await async_get_device_automations(
        hass, DeviceAutomationType.CONDITION, device_entry.id
    )
    assert len(conditions) == 1
    for condition in conditions:
        condition["entity_id"] = entity_registry.async_get(
            condition["entity_id"]
        ).entity_id
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.CONDITION, condition
        )
        assert capabilities == expected_capabilities


async def test_get_condition_capabilities_none(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected capabilities from a sensor condition."""
    entity = MockSensor(
        name="none sensor",
        unique_id="unique_none",
    )
    setup_test_component_platform(hass, DOMAIN, [entity])

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)

    entry_none = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        entity.unique_id,
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    conditions = [
        {
            "condition": "device",
            "device_id": "8770c43885354d5fa27604db6817f63f",
            "domain": "sensor",
            "entity_id": "01234567890123456789012345678901",
            "type": "is_battery_level",
        },
        {
            "condition": "device",
            "device_id": "8770c43885354d5fa27604db6817f63f",
            "domain": "sensor",
            "entity_id": entry_none.id,
            "type": "is_battery_level",
        },
    ]

    expected_capabilities = {}
    for condition in conditions:
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.CONDITION, condition
        )
        assert capabilities == expected_capabilities


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_if_state_not_above_below(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test for bad value conditions."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device_entry.id,
                            "entity_id": entry.id,
                            "type": "is_battery_level",
                        }
                    ],
                    "action": {"service": "test.automation"},
                }
            ]
        },
    )
    assert "must contain at least one of below, above" in caplog.text


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_if_state_above(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test for value conditions."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    hass.states.async_set(entry.entity_id, STATE_UNKNOWN, {"device_class": "battery"})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device_entry.id,
                            "entity_id": entry.id,
                            "type": "is_battery_level",
                            "above": 10,
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "{{ trigger.platform }}"
                                " - {{ trigger.event.event_type }}"
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(entry.entity_id, 9)
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(entry.entity_id, 11)
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "event - test_event1"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_if_state_above_legacy(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test for value conditions."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    hass.states.async_set(entry.entity_id, STATE_UNKNOWN, {"device_class": "battery"})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device_entry.id,
                            "entity_id": entry.entity_id,
                            "type": "is_battery_level",
                            "above": 10,
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "{{ trigger.platform }}"
                                " - {{ trigger.event.event_type }}"
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(entry.entity_id, 9)
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(entry.entity_id, 11)
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "event - test_event1"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_if_state_below(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test for value conditions."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    hass.states.async_set(entry.entity_id, STATE_UNKNOWN, {"device_class": "battery"})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device_entry.id,
                            "entity_id": entry.id,
                            "type": "is_battery_level",
                            "below": 10,
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "{{ trigger.platform }}"
                                " - {{ trigger.event.event_type }}"
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(entry.entity_id, 11)
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(entry.entity_id, 9)
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "event - test_event1"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_if_state_between(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test for value conditions."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry = entity_registry.async_get_or_create(
        DOMAIN, "test", "5678", device_id=device_entry.id
    )

    hass.states.async_set(entry.entity_id, STATE_UNKNOWN, {"device_class": "battery"})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "condition": [
                        {
                            "condition": "device",
                            "domain": DOMAIN,
                            "device_id": device_entry.id,
                            "entity_id": entry.id,
                            "type": "is_battery_level",
                            "above": 10,
                            "below": 20,
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "{{ trigger.platform }}"
                                " - {{ trigger.event.event_type }}"
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(entry.entity_id, 9)
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(entry.entity_id, 11)
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "event - test_event1"

    hass.states.async_set(entry.entity_id, 21)
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    hass.states.async_set(entry.entity_id, 19)
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(service_calls) == 2
    assert service_calls[1].data["some"] == "event - test_event1"
