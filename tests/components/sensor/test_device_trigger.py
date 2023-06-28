"""The test for sensor device automation."""
from datetime import timedelta

import pytest
from pytest_unordered import unordered

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
    device_trigger,
)
from homeassistant.components.sensor.const import NON_NUMERIC_DEVICE_CLASSES
from homeassistant.components.sensor.device_trigger import ENTITY_TRIGGERS
from homeassistant.const import CONF_PLATFORM, PERCENTAGE, STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryHider
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.json import load_json

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_get_device_automation_capabilities,
    async_get_device_automations,
    async_mock_service,
)
from tests.testing_config.custom_components.test.sensor import UNITS_OF_MEASUREMENT


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.mark.parametrize(
    "device_class",
    [
        device_class
        for device_class in SensorDeviceClass
        if device_class not in NON_NUMERIC_DEVICE_CLASSES
    ],
)
def test_matches_device_classes(device_class: SensorDeviceClass) -> None:
    """Ensure device class constants are declared in device_trigger module."""
    # Ensure it has corresponding CONF_*** constant
    constant_name = {
        SensorDeviceClass.BATTERY: "CONF_BATTERY_LEVEL",
        SensorDeviceClass.CO: "CONF_CO",
        SensorDeviceClass.CO2: "CONF_CO2",
        SensorDeviceClass.ENERGY_STORAGE: "CONF_ENERGY",
        SensorDeviceClass.VOLUME_STORAGE: "CONF_VOLUME",
    }.get(device_class, f"CONF_{device_class.value.upper()}")
    assert hasattr(device_trigger, constant_name), f"Missing constant {constant_name}"

    # Ensure it has correct value
    constant_value = {
        SensorDeviceClass.BATTERY: "battery_level",
        SensorDeviceClass.ENERGY_STORAGE: "energy",
        SensorDeviceClass.VOLUME_STORAGE: "volume",
    }.get(device_class, device_class.value)
    assert getattr(device_trigger, constant_name) == constant_value

    # Ensure it is present in ENTITY_TRIGGERS
    assert device_class in ENTITY_TRIGGERS
    # Ensure it is present in TRIGGER_SCHEMA
    schema_types = device_trigger.TRIGGER_SCHEMA.validators[0].schema["type"].container
    assert constant_value in schema_types
    # Ensure it is present in string.json
    strings = load_json("homeassistant/components/sensor/strings.json")
    assert constant_value in strings["device_automation"]["trigger_type"]


async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    enable_custom_integrations: None,
) -> None:
    """Test we get the expected triggers from a sensor."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()
    sensor_entries: dict[SensorDeviceClass, er.RegistryEntry] = {}

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
            platform.ENTITIES[device_class].unique_id,
            device_id=device_entry.id,
        )

    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger["type"],
            "device_id": device_entry.id,
            "entity_id": sensor_entries[device_class].id,
            "metadata": {"secondary": False},
        }
        for device_class in SensorDeviceClass
        if device_class in UNITS_OF_MEASUREMENT
        for trigger in ENTITY_TRIGGERS[device_class]
        if device_class != "none"
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 27
    assert triggers == unordered(expected_triggers)


@pytest.mark.parametrize(
    ("hidden_by", "entity_category"),
    (
        (RegistryEntryHider.INTEGRATION, None),
        (RegistryEntryHider.USER, None),
        (None, EntityCategory.CONFIG),
        (None, EntityCategory.DIAGNOSTIC),
    ),
)
async def test_get_triggers_hidden_auxiliary(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hidden_by,
    entity_category,
) -> None:
    """Test we get the expected triggers from a hidden or auxiliary entity."""
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
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": True},
        }
        for trigger in ["value"]
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


@pytest.mark.parametrize(
    ("state_class", "unit", "trigger_types"),
    (
        (SensorStateClass.MEASUREMENT, None, ["value"]),
        (SensorStateClass.TOTAL, None, ["value"]),
        (SensorStateClass.TOTAL_INCREASING, None, ["value"]),
        (SensorStateClass.MEASUREMENT, "dogs", ["value"]),
        (None, None, []),
    ),
)
async def test_get_triggers_no_unit_or_stateclass(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    state_class,
    unit,
    trigger_types,
) -> None:
    """Test we get the expected triggers from an entity with no unit or state class."""
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
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger,
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        }
        for trigger in trigger_types
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


@pytest.mark.parametrize(
    ("set_state", "device_class_reg", "device_class_state", "unit_reg", "unit_state"),
    [
        (False, SensorDeviceClass.BATTERY, None, PERCENTAGE, None),
        (True, None, SensorDeviceClass.BATTERY, None, PERCENTAGE),
    ],
)
async def test_get_trigger_capabilities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    set_state,
    device_class_reg,
    device_class_state,
    unit_reg,
    unit_state,
) -> None:
    """Test we get the expected capabilities from a sensor trigger."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_id = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        platform.ENTITIES["battery"].unique_id,
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
            {"name": "for", "optional": True, "type": "positive_time_period_dict"},
        ]
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 1
    for trigger in triggers:
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.TRIGGER, trigger
        )
        assert capabilities == expected_capabilities


@pytest.mark.parametrize(
    ("set_state", "device_class_reg", "device_class_state", "unit_reg", "unit_state"),
    [
        (False, SensorDeviceClass.BATTERY, None, PERCENTAGE, None),
        (True, None, SensorDeviceClass.BATTERY, None, PERCENTAGE),
    ],
)
async def test_get_trigger_capabilities_legacy(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    set_state,
    device_class_reg,
    device_class_state,
    unit_reg,
    unit_state,
) -> None:
    """Test we get the expected capabilities from a sensor trigger."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_id = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        platform.ENTITIES["battery"].unique_id,
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
            {"name": "for", "optional": True, "type": "positive_time_period_dict"},
        ]
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 1
    for trigger in triggers:
        trigger["entity_id"] = entity_registry.async_get(trigger["entity_id"]).entity_id
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.TRIGGER, trigger
        )
        assert capabilities == expected_capabilities


async def test_get_trigger_capabilities_none(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    enable_custom_integrations: None,
) -> None:
    """Test we get the expected capabilities from a sensor trigger."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)

    entry_none = entity_registry.async_get_or_create(
        DOMAIN,
        "test",
        platform.ENTITIES["none"].unique_id,
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    triggers = [
        {
            "platform": "device",
            "device_id": "8770c43885354d5fa27604db6817f63f",
            "domain": "sensor",
            "entity_id": "01234567890123456789012345678901",
            "type": "is_battery_level",
        },
        {
            "platform": "device",
            "device_id": "8770c43885354d5fa27604db6817f63f",
            "domain": "sensor",
            "entity_id": entry_none.id,
            "type": "is_battery_level",
        },
    ]

    expected_capabilities = {}
    for trigger in triggers:
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.TRIGGER, trigger
        )
        assert capabilities == expected_capabilities


async def test_if_fires_not_on_above_below(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    calls,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
) -> None:
    """Test for value triggers firing."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": entry.id,
                        "type": "battery_level",
                    },
                    "action": {"service": "test.automation"},
                }
            ]
        },
    )
    assert "must contain at least one of below, above" in caplog.text


async def test_if_fires_on_state_above(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    calls,
    enable_custom_integrations: None,
) -> None:
    """Test for value triggers firing."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

    hass.states.async_set(entry.entity_id, STATE_UNKNOWN, {"device_class": "battery"})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": entry.id,
                        "type": "battery_level",
                        "above": 10,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "bat_low {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(
                                (
                                    "platform",
                                    "entity_id",
                                    "from_state.state",
                                    "to_state.state",
                                    "for",
                                )
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.states.async_set(entry.entity_id, 9)
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.states.async_set(entry.entity_id, 11)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert (
        calls[0].data["some"] == f"bat_low device - {entry.entity_id} - 9 - 11 - None"
    )


async def test_if_fires_on_state_below(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    calls,
    enable_custom_integrations: None,
) -> None:
    """Test for value triggers firing."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

    hass.states.async_set(entry.entity_id, STATE_UNKNOWN, {"device_class": "battery"})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": entry.id,
                        "type": "battery_level",
                        "below": 10,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "bat_low {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(
                                (
                                    "platform",
                                    "entity_id",
                                    "from_state.state",
                                    "to_state.state",
                                    "for",
                                )
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.states.async_set(entry.entity_id, 11)
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.states.async_set(entry.entity_id, 9)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert (
        calls[0].data["some"] == f"bat_low device - {entry.entity_id} - 11 - 9 - None"
    )


async def test_if_fires_on_state_between(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    calls,
    enable_custom_integrations: None,
) -> None:
    """Test for value triggers firing."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

    hass.states.async_set(entry.entity_id, STATE_UNKNOWN, {"device_class": "battery"})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": entry.id,
                        "type": "battery_level",
                        "above": 10,
                        "below": 20,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "bat_low {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(
                                (
                                    "platform",
                                    "entity_id",
                                    "from_state.state",
                                    "to_state.state",
                                    "for",
                                )
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.states.async_set(entry.entity_id, 9)
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.states.async_set(entry.entity_id, 11)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert (
        calls[0].data["some"] == f"bat_low device - {entry.entity_id} - 9 - 11 - None"
    )

    hass.states.async_set(entry.entity_id, 21)
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.states.async_set(entry.entity_id, 19)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert (
        calls[1].data["some"] == f"bat_low device - {entry.entity_id} - 21 - 19 - None"
    )


async def test_if_fires_on_state_legacy(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    calls,
    enable_custom_integrations: None,
) -> None:
    """Test for value triggers firing."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

    hass.states.async_set(entry.entity_id, STATE_UNKNOWN, {"device_class": "battery"})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": entry.entity_id,
                        "type": "battery_level",
                        "above": 10,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "bat_low {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(
                                (
                                    "platform",
                                    "entity_id",
                                    "from_state.state",
                                    "to_state.state",
                                    "for",
                                )
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.states.async_set(entry.entity_id, 9)
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.states.async_set(entry.entity_id, 11)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert (
        calls[0].data["some"] == f"bat_low device - {entry.entity_id} - 9 - 11 - None"
    )


async def test_if_fires_on_state_change_with_for(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    calls,
    enable_custom_integrations: None,
) -> None:
    """Test for triggers firing with delay."""
    entry = entity_registry.async_get_or_create(DOMAIN, "test", "5678")

    hass.states.async_set(entry.entity_id, STATE_UNKNOWN, {"device_class": "battery"})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": entry.id,
                        "type": "battery_level",
                        "above": 10,
                        "for": {"seconds": 5},
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "turn_off {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(
                                (
                                    "platform",
                                    "entity_id",
                                    "from_state.state",
                                    "to_state.state",
                                    "for",
                                )
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.states.async_set(entry.entity_id, 10)
    hass.states.async_set(entry.entity_id, 11)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1
    await hass.async_block_till_done()
    assert (
        calls[0].data["some"]
        == f"turn_off device - {entry.entity_id} - 10 - 11 - 0:00:05"
    )
