"""Tests for WATERCryst BIOCAT sensors."""

from collections.abc import Sequence
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.watercryst import sensor as sensor_module
from homeassistant.components.watercryst.const import CONF_BSN, DOMAIN
from homeassistant.components.watercryst.sensor import (
    EVENT_SENSORS,
    FLOWRATE_SENSORS,
    LEAKAGE_PROTECTION_SENSORS,
    PRESSURE_SENSORS,
    STATE_SENSORS,
    TEMPERATURE_SENSORS,
    WatercrystEventSensorEntity,
    WatercrystStateSensorEntity,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo

from tests.common import MockConfigEntry

MOCK_API_KEY = "test-api-key"
MOCK_BSN = "1234567890"


def _device_info(**capabilities: bool) -> SimpleNamespace:
    """Create mock WATERCryst device information."""
    values = {
        "has_flow_rate_sensor": False,
        "has_leakage_protection_system": False,
        "has_pressure_sensor": False,
        "has_temperature_sensor": False,
    }
    values.update(capabilities)

    return SimpleNamespace(
        biocat_serial=MOCK_BSN,
        system_mac_address=None,
        ble_mac_address=None,
        line="BIOCAT",
        series="KS 3000",
        device_type_number="1234",
        name="BIOCAT utility room",
        current_firmware_version="1.2.3",
        current_hardware_version="4.5.6",
        **values,
    )


def _state() -> SimpleNamespace:
    """Create state data used during setup and the first refresh."""
    return SimpleNamespace(
        online=True,
        mode=SimpleNamespace(id=1),
        event=None,
        water_protection=SimpleNamespace(pause_leakage_protection_until_utc=None),
        ml_state=None,
    )


def _measurements() -> SimpleNamespace:
    """Create measurement data used during the first refresh."""
    return SimpleNamespace(
        water_temp=None,
        pressure=None,
        flow_rate=None,
        todays_consumption=None,
        total_consumption=None,
        last_water_tap_volume=None,
        last_water_tap_duration=None,
    )


def _entity_keys(
    entity_type: str,
    descriptions: Sequence[SensorEntityDescription],
) -> list[tuple[str, str]]:
    """Return entity type and description key pairs."""
    return [(entity_type, description.key) for description in descriptions]


BASE_ENTITIES = [
    *_entity_keys("state", STATE_SENSORS),
    *_entity_keys("event", EVENT_SENSORS),
]


@pytest.mark.parametrize(
    ("capabilities", "optional_entities"),
    [
        ({}, []),
        (
            {"has_leakage_protection_system": True},
            _entity_keys("state", LEAKAGE_PROTECTION_SENSORS),
        ),
        (
            {"has_temperature_sensor": True},
            _entity_keys("measurement", TEMPERATURE_SENSORS),
        ),
        (
            {"has_pressure_sensor": True},
            _entity_keys("measurement", PRESSURE_SENSORS),
        ),
        (
            {"has_flow_rate_sensor": True},
            _entity_keys("measurement", FLOWRATE_SENSORS),
        ),
        (
            {
                "has_flow_rate_sensor": True,
                "has_leakage_protection_system": True,
                "has_pressure_sensor": True,
                "has_temperature_sensor": True,
            },
            [
                *_entity_keys(
                    "state",
                    LEAKAGE_PROTECTION_SENSORS,
                ),
                *_entity_keys(
                    "measurement",
                    TEMPERATURE_SENSORS,
                ),
                *_entity_keys(
                    "measurement",
                    PRESSURE_SENSORS,
                ),
                *_entity_keys(
                    "measurement",
                    FLOWRATE_SENSORS,
                ),
            ],
        ),
    ],
)
async def test_async_setup_entry_adds_supported_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    capabilities: dict[str, bool],
    optional_entities: list[tuple[str, str]],
) -> None:
    """Test config-entry setup adds only supported sensors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="BIOCAT utility room",
        data={
            CONF_BSN: MOCK_BSN,
            CONF_API_KEY: MOCK_API_KEY,
        },
        unique_id=MOCK_BSN,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.watercryst.AsyncApiClient",
        autospec=True,
    ) as client_class:
        client = client_class.return_value
        client.get_device_info = AsyncMock(return_value=_device_info(**capabilities))
        client.get_state = AsyncMock(return_value=_state())
        client.get_measurements = AsyncMock(return_value=_measurements())

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    registry_entries = er.async_entries_for_config_entry(
        entity_registry,
        config_entry.entry_id,
    )

    expected_keys = {
        key
        for _, key in (
            *BASE_ENTITIES,
            *optional_entities,
        )
    }

    assert {registry_entry.unique_id for registry_entry in registry_entries} == {
        f"{MOCK_BSN}_{key}" for key in expected_keys
    }

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("key", "data", "expected"),
    [
        (
            "mode.id",
            SimpleNamespace(
                mode=SimpleNamespace(id=4),
            ),
            4,
        ),
        (
            "event.category",
            SimpleNamespace(
                event=SimpleNamespace(
                    category="warning",
                )
            ),
            "warning",
        ),
        (
            "water_temp",
            SimpleNamespace(water_temp=18.5),
            18.5,
        ),
        (
            "mode.id",
            SimpleNamespace(mode=None),
            None,
        ),
        (
            "pressure",
            SimpleNamespace(),
            None,
        ),
        (
            "pressure",
            None,
            None,
        ),
    ],
)
def test_native_value(
    key: str,
    data: SimpleNamespace | None,
    expected: object,
) -> None:
    """Test reading flat and nested coordinator values."""
    entity = object.__new__(WatercrystStateSensorEntity)
    entity.coordinator = SimpleNamespace(data=data)
    entity.entity_description = SensorEntityDescription(key=key)

    assert entity.native_value == expected


def test_event_extra_state_attributes() -> None:
    """Test exposing all event properties as attributes."""
    attributes = {
        "event_id": "leakage_detected",
        "category": "warning",
        "message": "Leakage protection activated",
    }
    event = MagicMock()
    event.model_dump.return_value = attributes

    entity = object.__new__(WatercrystEventSensorEntity)
    entity.coordinator = SimpleNamespace(data=SimpleNamespace(event=event))

    assert entity.extra_state_attributes == attributes
    event.model_dump.assert_called_once_with(by_alias=False)


@pytest.mark.parametrize(
    "data",
    [
        None,
        SimpleNamespace(event=None),
    ],
)
def test_event_extra_state_attributes_without_event(
    data: SimpleNamespace | None,
) -> None:
    """Test attributes are absent without event data."""
    entity = object.__new__(WatercrystEventSensorEntity)
    entity.coordinator = SimpleNamespace(data=data)

    assert entity.extra_state_attributes is None


def test_sensor_description_keys_are_unique() -> None:
    """Test every sensor has a unique data key."""
    descriptions = [
        *STATE_SENSORS,
        *EVENT_SENSORS,
        *LEAKAGE_PROTECTION_SENSORS,
        *TEMPERATURE_SENSORS,
        *PRESSURE_SENSORS,
        *FLOWRATE_SENSORS,
    ]
    keys = [description.key for description in descriptions]

    assert len(keys) == len(set(keys))


def test_sensor_entity_initialization() -> None:
    """Test measurement and state entity initialization."""
    device_info = DeviceInfo(identifiers={(DOMAIN, MOCK_BSN)})
    client = MagicMock()
    measurements = MagicMock()
    state = MagicMock()

    config_entry = MagicMock()
    config_entry.runtime_data = SimpleNamespace(
        bsn=MOCK_BSN,
        device_info=device_info,
        client=client,
        measurements=measurements,
        state=state,
    )

    measurement_description = SensorEntityDescription(key="pressure")
    state_description = SensorEntityDescription(key="mode.id")

    measurement_entity = sensor_module.WatercrystMeasurementSensorEntity(
        config_entry,
        measurement_description,
    )
    state_entity = WatercrystStateSensorEntity(
        config_entry,
        state_description,
    )

    assert measurement_entity.coordinator is measurements
    assert measurement_entity.entity_description is measurement_description
    assert measurement_entity.device_info is device_info
    assert measurement_entity.unique_id == f"{MOCK_BSN}_pressure"
    assert measurement_entity._client is client

    assert state_entity.coordinator is state
    assert state_entity.entity_description is state_description
    assert state_entity.device_info is device_info
    assert state_entity.unique_id == f"{MOCK_BSN}_mode.id"
    assert state_entity._client is client
