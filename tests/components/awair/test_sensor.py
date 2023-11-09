"""Tests for the Awair sensor platform."""
from unittest.mock import patch

from homeassistant.components.awair.const import (
    API_CO2,
    API_HUMID,
    API_LUX,
    API_PM10,
    API_PM25,
    API_SCORE,
    API_SPL_A,
    API_TEMP,
    API_VOC,
)
from homeassistant.components.awair.sensor import (
    SENSOR_TYPE_SCORE,
    SENSOR_TYPES,
    SENSOR_TYPES_DUST,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import setup_awair
from .const import (
    AWAIR_UUID,
    CLOUD_CONFIG,
    CLOUD_UNIQUE_ID,
    LOCAL_CONFIG,
    LOCAL_UNIQUE_ID,
)

SENSOR_TYPES_MAP = {
    desc.key: desc for desc in (SENSOR_TYPE_SCORE, *SENSOR_TYPES, *SENSOR_TYPES_DUST)
}


def assert_expected_properties(
    hass: HomeAssistant,
    registry: er.RegistryEntry,
    name,
    unique_id,
    state_value,
    attributes: dict,
):
    """Assert expected properties from a dict."""

    entry = registry.async_get(name)
    assert entry.unique_id == unique_id
    state = hass.states.get(name)
    assert state
    assert state.state == state_value
    for attr, value in attributes.items():
        assert state.attributes.get(attr) == value


async def test_awair_gen1_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    user,
    cloud_devices,
    gen1_data,
) -> None:
    """Test expected sensors on a 1st gen Awair."""

    fixtures = [user, cloud_devices, gen1_data]
    await setup_awair(hass, fixtures, CLOUD_UNIQUE_ID, CLOUD_CONFIG)

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_score",
        f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_SCORE].unique_id_tag}",
        "88",
        {},
    )

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_temperature",
        f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_TEMP].unique_id_tag}",
        "21.8",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS, "awair_index": 1.0},
    )

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_humidity",
        f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_HUMID].unique_id_tag}",
        "41.59",
        {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE, "awair_index": 0.0},
    )

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_carbon_dioxide",
        f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_CO2].unique_id_tag}",
        "654.0",
        {
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_MILLION,
            "awair_index": 0.0,
        },
    )

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_vocs",
        f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_VOC].unique_id_tag}",
        "366",
        {
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
            "awair_index": 1.0,
        },
    )

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_pm2_5",
        # gen1 unique_id should be awair_12345-DUST, which matches old integration behavior
        f"{AWAIR_UUID}_DUST",
        "14.3",
        {
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            "awair_index": 1.0,
        },
    )

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_pm10",
        f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_PM10].unique_id_tag}",
        "14.3",
        {
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            "awair_index": 1.0,
        },
    )

    # We should not have a dust sensor; it's aliased as pm2.5
    # and pm10 sensors.
    assert hass.states.get("sensor.living_room_dust") is None

    # We should not have sound or lux sensors.
    assert hass.states.get("sensor.living_room_sound_level") is None
    assert hass.states.get("sensor.living_room_illuminance") is None


async def test_awair_gen2_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    user,
    cloud_devices,
    gen2_data,
) -> None:
    """Test expected sensors on a 2nd gen Awair."""

    fixtures = [user, cloud_devices, gen2_data]
    await setup_awair(hass, fixtures, CLOUD_UNIQUE_ID, CLOUD_CONFIG)

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_score",
        f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_SCORE].unique_id_tag}",
        "97",
        {},
    )

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_pm2_5",
        f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_PM25].unique_id_tag}",
        "2.0",
        {
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            "awair_index": 0.0,
        },
    )

    # The Awair 2nd gen reports specifically a pm2.5 sensor,
    # and so we don't alias anything. Make sure we didn't do that.
    assert hass.states.get("sensor.living_room_pm10") is None


async def test_local_awair_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, local_devices, local_data
) -> None:
    """Test expected sensors on a local Awair."""

    fixtures = [local_devices, local_data]
    await setup_awair(hass, fixtures, LOCAL_UNIQUE_ID, LOCAL_CONFIG)

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.mock_title_score",
        f"{local_devices['device_uuid']}_{SENSOR_TYPES_MAP[API_SCORE].unique_id_tag}",
        "94",
        {},
    )


async def test_awair_mint_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    user,
    cloud_devices,
    mint_data,
) -> None:
    """Test expected sensors on an Awair mint."""

    fixtures = [user, cloud_devices, mint_data]
    await setup_awair(hass, fixtures, CLOUD_UNIQUE_ID, CLOUD_CONFIG)

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_score",
        f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_SCORE].unique_id_tag}",
        "98",
        {},
    )

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_pm2_5",
        f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_PM25].unique_id_tag}",
        "1.0",
        {
            ATTR_UNIT_OF_MEASUREMENT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            "awair_index": 0.0,
        },
    )

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_illuminance",
        f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_LUX].unique_id_tag}",
        "441.7",
        {ATTR_UNIT_OF_MEASUREMENT: LIGHT_LUX},
    )

    # The Mint does not have a CO2 sensor.
    assert hass.states.get("sensor.living_room_carbon_dioxide") is None


async def test_awair_glow_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    user,
    cloud_devices,
    glow_data,
) -> None:
    """Test expected sensors on an Awair glow."""

    fixtures = [user, cloud_devices, glow_data]
    await setup_awair(hass, fixtures, CLOUD_UNIQUE_ID, CLOUD_CONFIG)

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_score",
        f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_SCORE].unique_id_tag}",
        "93",
        {},
    )

    # The glow does not have a particle sensor
    assert hass.states.get("sensor.living_room_pm2_5") is None


async def test_awair_omni_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    user,
    cloud_devices,
    omni_data,
) -> None:
    """Test expected sensors on an Awair omni."""

    fixtures = [user, cloud_devices, omni_data]
    await setup_awair(hass, fixtures, CLOUD_UNIQUE_ID, CLOUD_CONFIG)

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_score",
        f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_SCORE].unique_id_tag}",
        "99",
        {},
    )

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_sound_level",
        f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_SPL_A].unique_id_tag}",
        "47.0",
        {ATTR_UNIT_OF_MEASUREMENT: "dBA"},
    )

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_illuminance",
        f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_LUX].unique_id_tag}",
        "804.9",
        {ATTR_UNIT_OF_MEASUREMENT: LIGHT_LUX},
    )


async def test_awair_offline(
    hass: HomeAssistant, user, cloud_devices, awair_offline
) -> None:
    """Test expected behavior when an Awair is offline."""

    fixtures = [user, cloud_devices, awair_offline]
    await setup_awair(hass, fixtures, CLOUD_UNIQUE_ID, CLOUD_CONFIG)

    # The expected behavior is that we won't have any sensors
    # if the device is not online when we set it up. python_awair
    # does not make any assumptions about what sensors a device
    # might have - they are created dynamically.

    # We check for the absence of the "awair score", which every
    # device *should* have if it's online. If we don't see it,
    # then we probably didn't set anything up. Which is correct,
    # in this case.
    assert hass.states.get("sensor.living_room_score") is None


async def test_awair_unavailable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    user,
    cloud_devices,
    gen1_data,
    awair_offline,
) -> None:
    """Test expected behavior when an Awair becomes offline later."""

    fixtures = [user, cloud_devices, gen1_data]
    await setup_awair(hass, fixtures, CLOUD_UNIQUE_ID, CLOUD_CONFIG)

    assert_expected_properties(
        hass,
        entity_registry,
        "sensor.living_room_score",
        f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_SCORE].unique_id_tag}",
        "88",
        {},
    )

    with patch("python_awair.AwairClient.query", side_effect=awair_offline):
        await async_update_entity(hass, "sensor.living_room_score")
        assert_expected_properties(
            hass,
            entity_registry,
            "sensor.living_room_score",
            f"{AWAIR_UUID}_{SENSOR_TYPES_MAP[API_SCORE].unique_id_tag}",
            STATE_UNAVAILABLE,
            {},
        )
