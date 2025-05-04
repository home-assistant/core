"""The sensor tests for the nut platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.nut.const import DOMAIN
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_HOST,
    CONF_PORT,
    CONF_RESOURCES,
    PERCENTAGE,
    STATE_UNKNOWN,
    Platform,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, translation

from .util import (
    _get_mock_nutclient,
    _test_sensor_and_attributes,
    async_init_integration,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "model",
    [
        "CP1350C",
        "5E650I",
        "5E850I",
        "CP1500PFCLCD",
        "DL650ELCD",
        "EATON5P1550",
        "blazer_usb",
    ],
)
async def test_ups_devices(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, model: str
) -> None:
    """Test creation of device sensors."""

    config_entry = await async_init_integration(hass, model)
    entry = entity_registry.async_get("sensor.ups1_battery_charge")
    assert entry
    assert entry.unique_id == f"{config_entry.entry_id}_battery.charge"

    state = hass.states.get("sensor.ups1_battery_charge")
    assert state.state == "100"

    expected_attributes = {
        ATTR_DEVICE_CLASS: "battery",
        ATTR_FRIENDLY_NAME: "Ups1 Battery charge",
        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == attr for key, attr in expected_attributes.items()
    )


@pytest.mark.parametrize(
    ("model", "unique_id"),
    [
        ("PR3000RT2U", "CPS_PR3000RT2U_PYVJO2000034_battery.charge"),
        (
            "BACKUPSES600M1",
            "American Power Conversion_Back-UPS ES 600M1_4B1713P32195 _battery.charge",
        ),
    ],
)
async def test_ups_devices_with_unique_ids(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, model: str, unique_id: str
) -> None:
    """Test creation of device sensors with unique ids."""

    await async_init_integration(hass, model)
    entry = entity_registry.async_get("sensor.ups1_battery_charge")
    assert entry
    assert entry.unique_id == unique_id

    state = hass.states.get("sensor.ups1_battery_charge")
    assert state.state == "100"

    expected_attributes = {
        ATTR_DEVICE_CLASS: "battery",
        ATTR_FRIENDLY_NAME: "Ups1 Battery charge",
        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == attr for key, attr in expected_attributes.items()
    )


@pytest.mark.parametrize(
    ("model", "unique_id_base"),
    [
        (
            "EATON-EPDU-G3",
            "EATON_ePDU MA 00U-C IN: TYPE 00A 0P OUT: 00xTYPE_A000A00000",
        ),
    ],
)
async def test_pdu_devices_with_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    model: str,
    unique_id_base: str,
) -> None:
    """Test creation of device sensors with unique ids."""

    await async_init_integration(hass, model)

    _test_sensor_and_attributes(
        hass,
        entity_registry,
        unique_id=f"{unique_id_base}_input.voltage",
        device_id="sensor.ups1_input_voltage",
        state_value="122.91",
        expected_attributes={
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
            "state_class": SensorStateClass.MEASUREMENT,
            ATTR_FRIENDLY_NAME: "Ups1 Input voltage",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfElectricPotential.VOLT,
        },
    )

    _test_sensor_and_attributes(
        hass,
        entity_registry,
        unique_id=f"{unique_id_base}_ambient.humidity.status",
        device_id="sensor.ups1_ambient_humidity_status",
        state_value="good",
        expected_attributes={
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENUM,
            ATTR_FRIENDLY_NAME: "Ups1 Ambient humidity status",
        },
    )

    _test_sensor_and_attributes(
        hass,
        entity_registry,
        unique_id=f"{unique_id_base}_ambient.temperature.status",
        device_id="sensor.ups1_ambient_temperature_status",
        state_value="good",
        expected_attributes={
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENUM,
            ATTR_FRIENDLY_NAME: "Ups1 Ambient temperature status",
        },
    )


async def test_state_sensors(hass: HomeAssistant) -> None:
    """Test creation of status display sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "mock", CONF_PORT: "mock"},
    )
    entry.add_to_hass(hass)

    mock_pynut = _get_mock_nutclient(
        list_ups={"ups1": "UPS 1"}, list_vars={"ups.status": "OL"}
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state1 = hass.states.get("sensor.ups1_status")
        state2 = hass.states.get("sensor.ups1_status_data")
        assert state1.state == "Online"
        assert state2.state == "OL"


async def test_unknown_state_sensors(hass: HomeAssistant) -> None:
    """Test creation of unknown status display sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "mock", CONF_PORT: "mock"},
    )
    entry.add_to_hass(hass)

    mock_pynut = _get_mock_nutclient(
        list_ups={"ups1": "UPS 1"}, list_vars={"ups.status": "OQ"}
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state1 = hass.states.get("sensor.ups1_status")
        state2 = hass.states.get("sensor.ups1_status_data")
        assert state1.state == STATE_UNKNOWN
        assert state2.state == "OQ"


async def test_stale_options(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test creation of sensors with stale options to remove."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "mock",
            CONF_PORT: "mock",
            CONF_RESOURCES: ["ups.load"],
        },
        options={CONF_RESOURCES: ["battery.charge"]},
    )
    config_entry.add_to_hass(hass)

    mock_pynut = _get_mock_nutclient(
        list_ups={"ups1": "UPS 1"}, list_vars={"battery.charge": "10"}
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        entry = entity_registry.async_get("sensor.ups1_battery_charge")
        assert entry
        assert entry.unique_id == f"{config_entry.entry_id}_battery.charge"
        assert config_entry.data[CONF_RESOURCES] == ["battery.charge"]
        assert config_entry.options == {}

        state = hass.states.get("sensor.ups1_battery_charge")
        assert state.state == "10"


async def test_state_ambient_translation(hass: HomeAssistant) -> None:
    """Test translation of ambient state sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "mock", CONF_PORT: "mock"},
    )
    entry.add_to_hass(hass)

    mock_pynut = _get_mock_nutclient(
        list_ups={"ups1": "UPS 1"}, list_vars={"ambient.humidity.status": "good"}
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        key = "ambient_humidity_status"
        state = hass.states.get(f"sensor.ups1_{key}")
        assert state.state == "good"

        result = translation.async_translate_state(
            hass, state.state, Platform.SENSOR, DOMAIN, key, None
        )

        assert result == "Good"


@pytest.mark.parametrize(
    ("model", "unique_id_base"),
    [
        (
            "EATON-EPDU-G3-AMBIENT-NOT-PRESENT",
            "EATON_ePDU MA 00U-C IN: TYPE 00A 0P OUT: 00xTYPE_A000A00000",
        ),
    ],
)
async def test_pdu_devices_ambient_not_present(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    model: str,
    unique_id_base: str,
) -> None:
    """Test that ambient sensors not created."""

    await async_init_integration(hass, model)

    entry = entity_registry.async_get("sensor.ups1_ambient_humidity")
    assert not entry

    entry = entity_registry.async_get("sensor.ups1_ambient_humidity_status")
    assert not entry

    entry = entity_registry.async_get("sensor.ups1_ambient_temperature")
    assert not entry

    entry = entity_registry.async_get("sensor.ups1_ambient_temperature_status")
    assert not entry


@pytest.mark.parametrize(
    ("model", "unique_id_base"),
    [
        (
            "EATON-EPDU-G3",
            "EATON_ePDU MA 00U-C IN: TYPE 00A 0P OUT: 00xTYPE_A000A00000",
        ),
    ],
)
async def test_pdu_dynamic_outlets(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    model: str,
    unique_id_base: str,
) -> None:
    """Test for dynamically created outlet sensors."""

    await async_init_integration(hass, model)

    _test_sensor_and_attributes(
        hass,
        entity_registry,
        unique_id=f"{unique_id_base}_outlet.1.current",
        device_id="sensor.ups1_outlet_a1_current",
        state_value="0",
        expected_attributes={
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_FRIENDLY_NAME: "Ups1 Outlet A1 current",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfElectricCurrent.AMPERE,
        },
    )

    _test_sensor_and_attributes(
        hass,
        entity_registry,
        unique_id=f"{unique_id_base}_outlet.24.current",
        device_id="sensor.ups1_outlet_a24_current",
        state_value="0.19",
        expected_attributes={
            ATTR_DEVICE_CLASS: SensorDeviceClass.CURRENT,
            ATTR_FRIENDLY_NAME: "Ups1 Outlet A24 current",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfElectricCurrent.AMPERE,
        },
    )

    entry = entity_registry.async_get("sensor.ups1_outlet_25_current")
    assert not entry

    entry = entity_registry.async_get("sensor.ups1_outlet_a25_current")
    assert not entry
