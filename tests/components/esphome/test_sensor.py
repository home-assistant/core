"""Test ESPHome sensors."""

from collections.abc import Awaitable, Callable
import logging
import math

from aioesphomeapi import (
    APIClient,
    EntityCategory as ESPHomeEntityCategory,
    EntityInfo,
    EntityState,
    LastResetType,
    SensorInfo,
    SensorState,
    SensorStateClass as ESPHomeSensorStateClass,
    TextSensorInfo,
    TextSensorState,
    UserService,
)

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from .conftest import MockESPHomeDevice


async def test_generic_numeric_sensor(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a generic sensor entity."""
    logging.getLogger("homeassistant.components.esphome").setLevel(logging.DEBUG)
    entity_info = [
        SensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            unique_id="my_sensor",
        )
    ]
    states = [SensorState(key=1, state=50)]
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == "50"

    # Test updating state
    mock_device.set_state(SensorState(key=1, state=60))
    await hass.async_block_till_done()
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == "60"

    # Test sending the same state again
    mock_device.set_state(SensorState(key=1, state=60))
    await hass.async_block_till_done()
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == "60"

    # Test we can still update after the same state
    mock_device.set_state(SensorState(key=1, state=70))
    await hass.async_block_till_done()
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == "70"

    # Test invalid data from the underlying api does not crash us
    mock_device.set_state(SensorState(key=1, state=object()))
    await hass.async_block_till_done()
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == "70"


async def test_generic_numeric_sensor_with_entity_category_and_icon(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a generic sensor entity."""
    entity_info = [
        SensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            unique_id="my_sensor",
            entity_category=ESPHomeEntityCategory.DIAGNOSTIC,
            icon="mdi:leaf",
        )
    ]
    states = [SensorState(key=1, state=50)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == "50"
    assert state.attributes[ATTR_ICON] == "mdi:leaf"
    entry = entity_registry.async_get("sensor.test_mysensor")
    assert entry is not None
    # Note that ESPHome includes the EntityInfo type in the unique id
    # as this is not a 1:1 mapping to the entity platform (ie. text_sensor)
    assert entry.unique_id == "11:22:33:44:55:AA-sensor-mysensor"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_generic_numeric_sensor_state_class_measurement(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a generic sensor entity."""
    entity_info = [
        SensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            unique_id="my_sensor",
            state_class=ESPHomeSensorStateClass.MEASUREMENT,
            device_class="power",
            unit_of_measurement="W",
        )
    ]
    states = [SensorState(key=1, state=50)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == "50"
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    entry = entity_registry.async_get("sensor.test_mysensor")
    assert entry is not None
    # Note that ESPHome includes the EntityInfo type in the unique id
    # as this is not a 1:1 mapping to the entity platform (ie. text_sensor)
    assert entry.unique_id == "11:22:33:44:55:AA-sensor-mysensor"
    assert entry.entity_category is None


async def test_generic_numeric_sensor_device_class_timestamp(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a sensor entity that uses timestamp (epoch)."""
    entity_info = [
        SensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            unique_id="my_sensor",
            device_class="timestamp",
        )
    ]
    states = [SensorState(key=1, state=1687459432.466624)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == "2023-06-22T18:43:52+00:00"


async def test_generic_numeric_sensor_legacy_last_reset_convert(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a state class of measurement with last reset type of auto is converted to total increasing."""
    entity_info = [
        SensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            unique_id="my_sensor",
            last_reset_type=LastResetType.AUTO,
            state_class=ESPHomeSensorStateClass.MEASUREMENT,
        )
    ]
    states = [SensorState(key=1, state=50)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == "50"
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL_INCREASING


async def test_generic_numeric_sensor_no_state(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic numeric sensor that has no state."""
    entity_info = [
        SensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            unique_id="my_sensor",
        )
    ]
    states = []
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_generic_numeric_sensor_nan_state(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic numeric sensor that has nan state."""
    entity_info = [
        SensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            unique_id="my_sensor",
        )
    ]
    states = [SensorState(key=1, state=math.nan, missing_state=False)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_generic_numeric_sensor_missing_state(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic numeric sensor that is missing state."""
    entity_info = [
        SensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            unique_id="my_sensor",
        )
    ]
    states = [SensorState(key=1, state=True, missing_state=True)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_generic_text_sensor(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a generic text sensor entity."""
    entity_info = [
        TextSensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            unique_id="my_sensor",
        )
    ]
    states = [TextSensorState(key=1, state="i am a teapot")]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == "i am a teapot"


async def test_generic_text_sensor_missing_state(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic text sensor that is missing state."""
    entity_info = [
        TextSensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            unique_id="my_sensor",
        )
    ]
    states = [TextSensorState(key=1, state=True, missing_state=True)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_generic_text_sensor_device_class_timestamp(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a sensor entity that uses timestamp (datetime)."""
    entity_info = [
        TextSensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            unique_id="my_sensor",
            device_class=SensorDeviceClass.TIMESTAMP,
        )
    ]
    states = [TextSensorState(key=1, state="2023-06-22T18:43:52+00:00")]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == "2023-06-22T18:43:52+00:00"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP


async def test_generic_text_sensor_device_class_date(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a sensor entity that uses date (datetime)."""
    entity_info = [
        TextSensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            unique_id="my_sensor",
            device_class=SensorDeviceClass.DATE,
        )
    ]
    states = [TextSensorState(key=1, state="2023-06-22T18:43:52+00:00")]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == "2023-06-22"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DATE


async def test_generic_numeric_sensor_empty_string_uom(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic numeric sensor that has an empty string as the uom."""
    entity_info = [
        SensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            unique_id="my_sensor",
            unit_of_measurement="",
        )
    ]
    states = [SensorState(key=1, state=123, missing_state=False)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.test_mysensor")
    assert state is not None
    assert state.state == "123"
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
