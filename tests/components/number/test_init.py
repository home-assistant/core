"""The tests for the Number component."""
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE,
    DOMAIN,
    SERVICE_SET_VALUE,
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.components.number.const import (
    DEVICE_CLASS_UNITS as NUMBER_DEVICE_CLASS_UNITS,
)
from homeassistant.components.sensor import (
    DEVICE_CLASS_UNITS as SENSOR_DEVICE_CLASS_UNITS,
    NON_NUMERIC_DEVICE_CLASSES,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_PLATFORM,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    async_mock_restore_state_shutdown_restart,
    mock_config_flow,
    mock_integration,
    mock_platform,
    mock_restore_cache_with_extra_data,
)

TEST_DOMAIN = "test"


class MockDefaultNumberEntity(NumberEntity):
    """Mock NumberEntity device to use in tests.

    This class falls back on defaults for min_value, max_value, step.
    """

    @property
    def native_value(self):
        """Return the current value."""
        return 0.5


class MockNumberEntity(NumberEntity):
    """Mock NumberEntity device to use in tests.

    This class customizes min_value, max_value as overridden methods.
    Step is calculated based on the smaller max_value and min_value.
    """

    @property
    def native_max_value(self) -> float:
        """Return the max value."""
        return 0.5

    @property
    def native_min_value(self) -> float:
        """Return the min value."""
        return -0.5

    @property
    def native_unit_of_measurement(self):
        """Return the current value."""
        return "native_cats"

    @property
    def native_value(self):
        """Return the current value."""
        return 0.5


class MockNumberEntityAttr(NumberEntity):
    """Mock NumberEntity device to use in tests.

    This class customizes min_value, max_value by setting _attr members.
    Step is calculated based on the smaller max_value and min_value.
    """

    _attr_native_max_value = 1000.0
    _attr_native_min_value = -1000.0
    _attr_native_step = 100.0
    _attr_native_unit_of_measurement = "native_dogs"
    _attr_native_value = 500.0


class MockNumberEntityDescr(NumberEntity):
    """Mock NumberEntity device to use in tests.

    This class customizes min_value, max_value by entity description.
    Step is calculated based on the smaller max_value and min_value.
    """

    def __init__(self):
        """Initialize the clas instance."""
        self.entity_description = NumberEntityDescription(
            "test",
            native_max_value=10.0,
            native_min_value=-10.0,
            native_step=2.0,
            native_unit_of_measurement="native_rabbits",
        )

    @property
    def native_value(self):
        """Return the current value."""
        return None


class MockDefaultNumberEntityDeprecated(NumberEntity):
    """Mock NumberEntity device to use in tests.

    This class falls back on defaults for min_value, max_value, step.
    """

    @property
    def native_value(self):
        """Return the current value."""
        return 0.5


class MockNumberEntityDeprecated(NumberEntity):
    """Mock NumberEntity device to use in tests.

    This class customizes min_value, max_value as overridden methods.
    Step is calculated based on the smaller max_value and min_value.
    """

    @property
    def max_value(self) -> float:
        """Return the max value."""
        return 0.5

    @property
    def min_value(self) -> float:
        """Return the min value."""
        return -0.5

    @property
    def unit_of_measurement(self):
        """Return the current value."""
        return "cats"

    @property
    def value(self):
        """Return the current value."""
        return 0.5


class MockNumberEntityAttrDeprecated(NumberEntity):
    """Mock NumberEntity device to use in tests.

    This class customizes min_value, max_value by setting _attr members.
    Step is calculated based on the smaller max_value and min_value.
    """

    _attr_max_value = 1000.0
    _attr_min_value = -1000.0
    _attr_step = 100.0
    _attr_unit_of_measurement = "dogs"
    _attr_value = 500.0


class MockNumberEntityDescrDeprecated(NumberEntity):
    """Mock NumberEntity device to use in tests.

    This class customizes min_value, max_value by entity description.
    Step is calculated based on the smaller max_value and min_value.
    """

    def __init__(self):
        """Initialize the clas instance."""
        self.entity_description = NumberEntityDescription(
            "test",
            max_value=10.0,
            min_value=-10.0,
            step=2.0,
            unit_of_measurement="rabbits",
        )

    @property
    def value(self):
        """Return the current value."""
        return 0.5


async def test_step(hass: HomeAssistant) -> None:
    """Test the step calculation."""
    number = MockDefaultNumberEntity()
    number.hass = hass
    assert number.step == 1.0

    number_2 = MockNumberEntity()
    number_2.hass = hass
    assert number_2.step == 0.1


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the attributes."""
    number = MockDefaultNumberEntity()
    number.hass = hass
    assert number.max_value == 100.0
    assert number.min_value == 0.0
    assert number.step == 1.0
    assert number.unit_of_measurement is None
    assert number.value == 0.5

    number_2 = MockNumberEntity()
    number_2.hass = hass
    assert number_2.max_value == 0.5
    assert number_2.min_value == -0.5
    assert number_2.step == 0.1
    assert number_2.unit_of_measurement == "native_cats"
    assert number_2.value == 0.5

    number_3 = MockNumberEntityAttr()
    number_3.hass = hass
    assert number_3.max_value == 1000.0
    assert number_3.min_value == -1000.0
    assert number_3.step == 100.0
    assert number_3.unit_of_measurement == "native_dogs"
    assert number_3.value == 500.0

    number_4 = MockNumberEntityDescr()
    number_4.hass = hass
    assert number_4.max_value == 10.0
    assert number_4.min_value == -10.0
    assert number_4.step == 2.0
    assert number_4.unit_of_measurement == "native_rabbits"
    assert number_4.value is None


async def test_sync_set_value(hass: HomeAssistant) -> None:
    """Test if async set_value calls sync set_value."""
    number = MockDefaultNumberEntity()
    number.hass = hass

    number.set_value = MagicMock()
    await number.async_set_value(42)

    assert number.set_value.called
    assert number.set_value.call_args[0][0] == 42


async def test_set_value(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    """Test we can only set valid values."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("number.test")
    assert state.state == "50.0"
    assert state.attributes.get(ATTR_STEP) == 1.0

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 60.0, ATTR_ENTITY_ID: "number.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("number.test")
    assert state.state == "60.0"

    # test ValueError trigger
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_VALUE: 110.0, ATTR_ENTITY_ID: "number.test"},
            blocking=True,
        )

    await hass.async_block_till_done()
    state = hass.states.get("number.test")
    assert state.state == "60.0"


@pytest.mark.parametrize(
    (
        "unit_system",
        "native_unit",
        "state_unit",
        "initial_native_value",
        "initial_state_value",
        "updated_native_value",
        "updated_state_value",
        "native_max_value",
        "state_max_value",
        "native_min_value",
        "state_min_value",
        "native_step",
        "state_step",
    ),
    [
        (
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.FAHRENHEIT,
            100,
            100,
            50,
            50,
            140,
            140,
            -9,
            -9,
            3,
            3,
        ),
        (
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.FAHRENHEIT,
            38,
            100,
            10,
            50,
            60,
            140,
            -23,
            -10,
            3,
            3,
        ),
        (
            METRIC_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.CELSIUS,
            100,
            38,
            50,
            10,
            140,
            60,
            -9,
            -23,
            3,
            3,
        ),
        (
            METRIC_SYSTEM,
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.CELSIUS,
            38,
            38,
            10,
            10,
            60,
            60,
            -23,
            -23,
            3,
            3,
        ),
    ],
)
async def test_temperature_conversion(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    unit_system,
    native_unit,
    state_unit,
    initial_native_value,
    initial_state_value,
    updated_native_value,
    updated_state_value,
    native_max_value,
    state_max_value,
    native_min_value,
    state_min_value,
    native_step,
    state_step,
) -> None:
    """Test temperature conversion."""
    hass.config.units = unit_system
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockNumberEntity(
            name="Test",
            native_max_value=native_max_value,
            native_min_value=native_min_value,
            native_step=native_step,
            native_unit_of_measurement=native_unit,
            native_value=initial_native_value,
            device_class=NumberDeviceClass.TEMPERATURE,
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(float(initial_state_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == state_unit
    assert state.attributes[ATTR_MAX] == state_max_value
    assert state.attributes[ATTR_MIN] == state_min_value
    assert state.attributes[ATTR_STEP] == state_step

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: updated_state_value, ATTR_ENTITY_ID: entity0.entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(float(updated_state_value))
    assert entity0._values["native_value"] == updated_native_value

    # Set to the minimum value
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: state_min_value, ATTR_ENTITY_ID: entity0.entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(float(state_min_value), rel=0.1)

    # Set to the maximum value
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: state_max_value, ATTR_ENTITY_ID: entity0.entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(float(state_max_value), rel=0.1)


RESTORE_DATA = {
    "native_max_value": 200.0,
    "native_min_value": -10.0,
    "native_step": 2.0,
    "native_unit_of_measurement": "°F",
    "native_value": 123.0,
}


async def test_restore_number_save_state(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    enable_custom_integrations: None,
) -> None:
    """Test RestoreNumber."""
    platform = getattr(hass.components, "test.number")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockRestoreNumber(
            name="Test",
            native_max_value=200.0,
            native_min_value=-10.0,
            native_step=2.0,
            native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
            native_value=123.0,
            device_class=NumberDeviceClass.TEMPERATURE,
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(hass, "number", {"number": {"platform": "test"}})
    await hass.async_block_till_done()

    # Trigger saving state
    await async_mock_restore_state_shutdown_restart(hass)

    assert len(hass_storage[RESTORE_STATE_KEY]["data"]) == 1
    state = hass_storage[RESTORE_STATE_KEY]["data"][0]["state"]
    assert state["entity_id"] == entity0.entity_id
    extra_data = hass_storage[RESTORE_STATE_KEY]["data"][0]["extra_data"]
    assert extra_data == RESTORE_DATA
    assert type(extra_data["native_value"]) == float


@pytest.mark.parametrize(
    (
        "native_max_value",
        "native_min_value",
        "native_step",
        "native_value",
        "native_value_type",
        "extra_data",
        "device_class",
        "uom",
    ),
    [
        (
            200.0,
            -10.0,
            2.0,
            123.0,
            float,
            RESTORE_DATA,
            NumberDeviceClass.TEMPERATURE,
            "°F",
        ),
        (100.0, 0.0, None, None, type(None), None, None, None),
        (100.0, 0.0, None, None, type(None), {}, None, None),
        (100.0, 0.0, None, None, type(None), {"beer": 123}, None, None),
        (
            100.0,
            0.0,
            None,
            None,
            type(None),
            {"native_unit_of_measurement": "°F", "native_value": {}},
            None,
            None,
        ),
    ],
)
async def test_restore_number_restore_state(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    hass_storage: dict[str, Any],
    native_max_value,
    native_min_value,
    native_step,
    native_value,
    native_value_type,
    extra_data,
    device_class,
    uom,
) -> None:
    """Test RestoreNumber."""
    mock_restore_cache_with_extra_data(hass, ((State("number.test", ""), extra_data),))

    platform = getattr(hass.components, "test.number")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockRestoreNumber(
            device_class=device_class,
            name="Test",
            native_value=None,
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(hass, "number", {"number": {"platform": "test"}})
    await hass.async_block_till_done()

    assert hass.states.get(entity0.entity_id)

    assert entity0.native_max_value == native_max_value
    assert entity0.native_min_value == native_min_value
    assert entity0.native_step == native_step
    assert entity0.native_value == native_value
    assert type(entity0.native_value) == native_value_type
    assert entity0.native_unit_of_measurement == uom


@pytest.mark.parametrize(
    (
        "device_class",
        "native_unit",
        "custom_unit",
        "state_unit",
        "native_value",
        "custom_value",
    ),
    [
        # Not a supported temperature unit
        (
            NumberDeviceClass.TEMPERATURE,
            UnitOfTemperature.CELSIUS,
            "my_temperature_unit",
            UnitOfTemperature.CELSIUS,
            1000,
            1000,
        ),
        (
            NumberDeviceClass.TEMPERATURE,
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.FAHRENHEIT,
            37.5,
            99.5,
        ),
        (
            NumberDeviceClass.TEMPERATURE,
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.CELSIUS,
            100,
            38.0,
        ),
    ],
)
async def test_custom_unit(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    device_class,
    native_unit,
    custom_unit,
    state_unit,
    native_value,
    custom_value,
) -> None:
    """Test custom unit."""
    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get_or_create("number", "test", "very_unique")
    entity_registry.async_update_entity_options(
        entry.entity_id, "number", {"unit_of_measurement": custom_unit}
    )
    await hass.async_block_till_done()

    platform = getattr(hass.components, "test.number")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockNumberEntity(
            name="Test",
            native_value=native_value,
            native_unit_of_measurement=native_unit,
            device_class=device_class,
            unique_id="very_unique",
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(hass, "number", {"number": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(float(custom_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == state_unit


@pytest.mark.parametrize(
    (
        "native_unit",
        "custom_unit",
        "used_custom_unit",
        "default_unit",
        "native_value",
        "custom_value",
        "default_value",
    ),
    [
        (
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.CELSIUS,
            37.5,
            99.5,
            37.5,
        ),
        (
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.CELSIUS,
            100,
            100,
            38.0,
        ),
        # Not a supported temperature unit
        (
            UnitOfTemperature.CELSIUS,
            "no_unit",
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.CELSIUS,
            1000,
            1000,
            1000,
        ),
    ],
)
async def test_custom_unit_change(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    native_unit,
    custom_unit,
    used_custom_unit,
    default_unit,
    native_value,
    custom_value,
    default_value,
) -> None:
    """Test custom unit changes are picked up."""
    entity_registry = er.async_get(hass)
    platform = getattr(hass.components, "test.number")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockNumberEntity(
            name="Test",
            native_value=native_value,
            native_unit_of_measurement=native_unit,
            device_class=NumberDeviceClass.TEMPERATURE,
            unique_id="very_unique",
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(hass, "number", {"number": {"platform": "test"}})
    await hass.async_block_till_done()

    # Default unit conversion according to unit system
    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(float(default_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == default_unit

    entity_registry.async_update_entity_options(
        "number.test", "number", {"unit_of_measurement": custom_unit}
    )
    await hass.async_block_till_done()

    # Unit conversion to the custom unit
    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(float(custom_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == used_custom_unit

    entity_registry.async_update_entity_options(
        "number.test", "number", {"unit_of_measurement": native_unit}
    )
    await hass.async_block_till_done()

    # Unit conversion to another custom unit
    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(float(native_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == native_unit

    entity_registry.async_update_entity_options("number.test", "number", None)
    await hass.async_block_till_done()

    # Default unit conversion according to unit system
    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(float(default_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == default_unit


def test_device_classes_aligned() -> None:
    """Make sure all sensor device classes are also available in NumberDeviceClass."""

    for device_class in SensorDeviceClass:
        if device_class in NON_NUMERIC_DEVICE_CLASSES:
            continue

        assert hasattr(NumberDeviceClass, device_class.name)
        assert getattr(NumberDeviceClass, device_class.name).value == device_class.value

    for device_class in SENSOR_DEVICE_CLASS_UNITS:
        if device_class in NON_NUMERIC_DEVICE_CLASSES:
            continue
        assert (
            SENSOR_DEVICE_CLASS_UNITS[device_class]
            == NUMBER_DEVICE_CLASS_UNITS[device_class]
        )


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None, None, None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


async def test_name(hass: HomeAssistant) -> None:
    """Test number name."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setup(config_entry, DOMAIN)
        return True

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
        ),
    )

    # Unnamed sensor without device class -> no name
    entity1 = NumberEntity()
    entity1.entity_id = "number.test1"

    # Unnamed sensor with device class but has_entity_name False -> no name
    entity2 = NumberEntity()
    entity2.entity_id = "number.test2"
    entity2._attr_device_class = NumberDeviceClass.TEMPERATURE

    # Unnamed sensor with device class and has_entity_name True -> named
    entity3 = NumberEntity()
    entity3.entity_id = "number.test3"
    entity3._attr_device_class = NumberDeviceClass.TEMPERATURE
    entity3._attr_has_entity_name = True

    # Unnamed sensor with device class and has_entity_name True -> named
    entity4 = NumberEntity()
    entity4.entity_id = "number.test4"
    entity4.entity_description = NumberEntityDescription(
        "test",
        NumberDeviceClass.TEMPERATURE,
        has_entity_name=True,
    )

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test number platform via config entry."""
        async_add_entities([entity1, entity2, entity3, entity4])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity1.entity_id)
    assert state
    assert state.attributes == {
        "max": 100.0,
        "min": 0.0,
        "mode": NumberMode.AUTO,
        "step": 1.0,
    }

    state = hass.states.get(entity2.entity_id)
    assert state
    assert state.attributes == {
        "device_class": "temperature",
        "max": 100.0,
        "min": 0.0,
        "mode": NumberMode.AUTO,
        "step": 1.0,
    }

    state = hass.states.get(entity3.entity_id)
    assert state
    assert state.attributes == {
        "device_class": "temperature",
        "friendly_name": "Temperature",
        "max": 100.0,
        "min": 0.0,
        "mode": NumberMode.AUTO,
        "step": 1.0,
    }

    state = hass.states.get(entity4.entity_id)
    assert state
    assert state.attributes == {
        "device_class": "temperature",
        "friendly_name": "Temperature",
        "max": 100.0,
        "min": 0.0,
        "mode": NumberMode.AUTO,
        "step": 1.0,
    }
