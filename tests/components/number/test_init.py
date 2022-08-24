"""The tests for the Number component."""
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
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_PLATFORM,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from tests.common import mock_restore_cache_with_extra_data


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


async def test_deprecation_warnings(hass: HomeAssistant, caplog) -> None:
    """Test overriding the deprecated attributes is possible and warnings are logged."""
    number = MockDefaultNumberEntityDeprecated()
    number.hass = hass
    assert number.max_value == 100.0
    assert number.min_value == 0.0
    assert number.step == 1.0
    assert number.unit_of_measurement is None
    assert number.value == 0.5

    number_2 = MockNumberEntityDeprecated()
    number_2.hass = hass
    assert number_2.max_value == 0.5
    assert number_2.min_value == -0.5
    assert number_2.step == 0.1
    assert number_2.unit_of_measurement == "cats"
    assert number_2.value == 0.5

    number_3 = MockNumberEntityAttrDeprecated()
    number_3.hass = hass
    assert number_3.max_value == 1000.0
    assert number_3.min_value == -1000.0
    assert number_3.step == 100.0
    assert number_3.unit_of_measurement == "dogs"
    assert number_3.value == 500.0

    number_4 = MockNumberEntityDescrDeprecated()
    number_4.hass = hass
    assert number_4.max_value == 10.0
    assert number_4.min_value == -10.0
    assert number_4.step == 2.0
    assert number_4.unit_of_measurement == "rabbits"
    assert number_4.value == 0.5

    assert (
        "tests.components.number.test_init::MockNumberEntityDeprecated is overriding "
        " deprecated methods on an instance of NumberEntity"
    )
    assert (
        "Entity None (<class 'tests.components.number.test_init.MockNumberEntityAttrDeprecated'>) "
        "is using deprecated NumberEntity features" in caplog.text
    )
    assert (
        "Entity None (<class 'tests.components.number.test_init.MockNumberEntityDescrDeprecated'>) "
        "is using deprecated NumberEntity features" in caplog.text
    )
    assert (
        "tests.components.number.test_init is setting deprecated attributes on an "
        "instance of NumberEntityDescription" in caplog.text
    )


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


async def test_deprecated_attributes(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test entity using deprecated attributes."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init(empty=True)
    platform.ENTITIES.append(platform.LegacyMockNumberEntity())
    entity = platform.ENTITIES[0]
    entity._attr_name = "Test"
    entity._attr_max_value = 25
    entity._attr_min_value = -25
    entity._attr_step = 2.5
    entity._attr_value = 51.0

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("number.test")
    assert state.state == "51.0"
    assert state.attributes.get(ATTR_MAX) == 25.0
    assert state.attributes.get(ATTR_MIN) == -25.0
    assert state.attributes.get(ATTR_STEP) == 2.5

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 0.0, ATTR_ENTITY_ID: "number.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("number.test")
    assert state.state == "0.0"

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
    assert state.state == "0.0"


async def test_deprecated_methods(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test entity using deprecated methods."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.LegacyMockNumberEntity(
            name="Test",
            max_value=25.0,
            min_value=-25.0,
            step=2.5,
            value=51.0,
        )
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("number.test")
    assert state.state == "51.0"
    assert state.attributes.get(ATTR_MAX) == 25.0
    assert state.attributes.get(ATTR_MIN) == -25.0
    assert state.attributes.get(ATTR_STEP) == 2.5

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_VALUE: 0.0, ATTR_ENTITY_ID: "number.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("number.test")
    assert state.state == "0.0"

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
    assert state.state == "0.0"


@pytest.mark.parametrize(
    "unit_system, native_unit, state_unit, initial_native_value, initial_state_value, "
    "updated_native_value, updated_state_value, native_max_value, state_max_value, "
    "native_min_value, state_min_value, native_step, state_step",
    [
        (
            IMPERIAL_SYSTEM,
            TEMP_FAHRENHEIT,
            TEMP_FAHRENHEIT,
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
            IMPERIAL_SYSTEM,
            TEMP_CELSIUS,
            TEMP_FAHRENHEIT,
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
            TEMP_FAHRENHEIT,
            TEMP_CELSIUS,
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
            TEMP_CELSIUS,
            TEMP_CELSIUS,
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
    hass,
    enable_custom_integrations,
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
):
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
    hass,
    hass_storage,
    enable_custom_integrations,
):
    """Test RestoreNumber."""
    platform = getattr(hass.components, "test.number")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockRestoreNumber(
            name="Test",
            native_max_value=200.0,
            native_min_value=-10.0,
            native_step=2.0,
            native_unit_of_measurement=TEMP_FAHRENHEIT,
            native_value=123.0,
            device_class=NumberDeviceClass.TEMPERATURE,
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(hass, "number", {"number": {"platform": "test"}})
    await hass.async_block_till_done()

    # Trigger saving state
    await hass.async_stop()

    assert len(hass_storage[RESTORE_STATE_KEY]["data"]) == 1
    state = hass_storage[RESTORE_STATE_KEY]["data"][0]["state"]
    assert state["entity_id"] == entity0.entity_id
    extra_data = hass_storage[RESTORE_STATE_KEY]["data"][0]["extra_data"]
    assert extra_data == RESTORE_DATA
    assert type(extra_data["native_value"]) == float


@pytest.mark.parametrize(
    "native_max_value, native_min_value, native_step, native_value, native_value_type, extra_data, device_class, uom",
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
    hass,
    enable_custom_integrations,
    hass_storage,
    native_max_value,
    native_min_value,
    native_step,
    native_value,
    native_value_type,
    extra_data,
    device_class,
    uom,
):
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
    "device_class,native_unit,custom_unit,state_unit,native_value,custom_value",
    [
        # Not a supported temperature unit
        (
            NumberDeviceClass.TEMPERATURE,
            TEMP_CELSIUS,
            "my_temperature_unit",
            TEMP_CELSIUS,
            1000,
            1000,
        ),
        (
            NumberDeviceClass.TEMPERATURE,
            TEMP_CELSIUS,
            TEMP_FAHRENHEIT,
            TEMP_FAHRENHEIT,
            37.5,
            99.5,
        ),
        (
            NumberDeviceClass.TEMPERATURE,
            TEMP_FAHRENHEIT,
            TEMP_CELSIUS,
            TEMP_CELSIUS,
            100,
            38.0,
        ),
    ],
)
async def test_custom_unit(
    hass,
    enable_custom_integrations,
    device_class,
    native_unit,
    custom_unit,
    state_unit,
    native_value,
    custom_value,
):
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
    "native_unit, custom_unit, used_custom_unit, default_unit, native_value, custom_value, default_value",
    [
        (
            TEMP_CELSIUS,
            TEMP_FAHRENHEIT,
            TEMP_FAHRENHEIT,
            TEMP_CELSIUS,
            37.5,
            99.5,
            37.5,
        ),
        (
            TEMP_FAHRENHEIT,
            TEMP_FAHRENHEIT,
            TEMP_FAHRENHEIT,
            TEMP_CELSIUS,
            100,
            100,
            38.0,
        ),
        # Not a supported temperature unit
        (TEMP_CELSIUS, "no_unit", TEMP_CELSIUS, TEMP_CELSIUS, 1000, 1000, 1000),
    ],
)
async def test_custom_unit_change(
    hass,
    enable_custom_integrations,
    native_unit,
    custom_unit,
    used_custom_unit,
    default_unit,
    native_value,
    custom_value,
    default_value,
):
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
