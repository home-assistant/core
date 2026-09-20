"""Tests for the Hive integration __init__."""

from operator import attrgetter
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.hive.const import (
    DOMAIN,
    SERVICE_BOOST_HEATING_OFF,
    SERVICE_BOOST_HEATING_ON,
    SERVICE_BOOST_HOT_WATER,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

_CLIMATE_ENTITY_ID = "climate.thermostat_heating"
_WATER_HEATER_ENTITY_ID = "water_heater.hot_water"

_ENTRY_DATA = {
    CONF_USERNAME: "user@example.com",
    CONF_PASSWORD: "password",
    "tokens": {
        "AuthenticationResult": {
            "AccessToken": "mock-access-token",
            "RefreshToken": "mock-refresh-token",
        },
        "ChallengeName": "SUCCESS",
    },
}

_HUB_BASE = {
    "device_id": "hive-hub-id",
    "hiveName": "Hive Hub",
    "deviceData": {
        "model": "Hub",
        "version": "1.2.3",
        "manufacturer": "Hive",
        "online": True,
    },
}

_CHILD_BINARY_SENSOR = {
    "device_id": "hive-child-id",
    "hiveID": "hive-child-id",
    "hiveName": "Hive Hub Connectivity",
    "haName": "Hub Connectivity",
    "device_name": "Hive Hub",
    "hiveType": "Connectivity",
    "parentDevice": "hive-hub-id",
    "deviceData": {
        "model": "Hub",
        "version": "1.2.3",
        "manufacturer": "Hive",
        "online": True,
    },
    "status": {"state": True},
}

_GLASS_BREAK_BINARY_SENSOR = {
    "device_id": "hive-glass-break-id",
    "hiveID": "hive-glass-break-id",
    "hiveName": "Glass Break",
    "haName": "Glass Break",
    "device_name": "Glass Break Sensor",
    "hiveType": "GLASS_BREAK",
    "parentDevice": "hive-hub-id",
    "deviceData": {
        "model": "Glass Break Sensor",
        "version": "1.2.3",
        "manufacturer": "Hive",
        "online": True,
    },
    "status": {"state": False},
}

_CLIMATE_DEVICE = {
    "device_id": "hive-climate-id",
    "hiveID": "hive-climate-id",
    "hiveName": "Heating",
    "haName": "Heating",
    "device_name": "Thermostat",
    "hiveType": "Heating",
    "parentDevice": "hive-hub-id",
    "temperatureunit": "C",
    "min_temp": 7,
    "max_temp": 35,
    "deviceData": {
        "model": "Thermostat",
        "version": "1.2.3",
        "manufacturer": "Hive",
        "online": True,
    },
    "status": {
        "mode": "SCHEDULE",
        "action": False,
        "current_temperature": 20,
        "target_temperature": 21,
        "boost": "OFF",
    },
}

_WATER_HEATER_DEVICE = {
    "device_id": "hive-water-heater-id",
    "hiveID": "hive-water-heater-id",
    "hiveName": "Hot Water",
    "haName": "Hot Water",
    "device_name": "Hot Water",
    "hiveType": "HotWater",
    "parentDevice": "hive-hub-id",
    "deviceData": {
        "model": "Hot Water",
        "version": "1.2.3",
        "manufacturer": "Hive",
        "online": True,
    },
    "status": {"current_operation": "SCHEDULE"},
}

# The hub's own diagnostic sensor reports the hub as its own parent
# (parentDevice == device_id), which would link the hub device to itself.
_HUB_BINARY_SENSOR = {
    "device_id": "hive-hub-id",
    "hiveID": "hive-hub-id",
    "hiveName": "Hive Hub Status",
    "haName": "Hive Hub Status",
    "device_name": "Hive Hub",
    "hiveType": "Connectivity",
    "parentDevice": "hive-hub-id",
    "deviceData": {
        "model": "Hub",
        "version": "1.2.3",
        "manufacturer": "Hive",
        "online": True,
    },
    "status": {"state": True},
}


def _make_mock_hive(
    hub_extra: dict, extra_devices: dict[str, list[dict[str, Any]]] | None = None
) -> MagicMock:
    """Return a mocked Hive instance.

    startSession returns a minimal devices dict.
    """
    hub_data = {**_HUB_BASE, **hub_extra}
    devices = {"parent": [hub_data], **(extra_devices or {})}
    mock_hive = MagicMock()
    mock_hive.session.startSession = AsyncMock(return_value=devices)
    mock_hive.session.deviceList = devices
    return mock_hive


async def test_hub_device_registers_mac_connection(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Hub device entry includes a MAC connection when macAddress is present."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA)
    entry.add_to_hass(hass)

    mock_hive = _make_mock_hive({"macAddress": "00:1C:2B:1C:2E:68"})

    with patch(
        "homeassistant.components.hive.Hive",
        return_value=mock_hive,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "hive-hub-id"), entry.entry_id
    )
    assert device is not None
    assert (dr.CONNECTION_NETWORK_MAC, "00:1c:2b:1c:2e:68") in device.connections


async def test_hub_device_no_mac_connection_when_absent(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Hub device entry has no MAC connection when macAddress is absent."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA)
    entry.add_to_hass(hass)

    mock_hive = _make_mock_hive({})  # no macAddress key

    with patch(
        "homeassistant.components.hive.Hive",
        return_value=mock_hive,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "hive-hub-id"), entry.entry_id
    )
    assert device is not None
    assert not any(
        conn_type == dr.CONNECTION_NETWORK_MAC for conn_type, _ in device.connections
    )


async def test_child_device_links_to_hub_via_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A child device's via_device_id should point at the hub device's id."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA)
    entry.add_to_hass(hass)

    mock_hive = _make_mock_hive(
        {"macAddress": "00:1C:2B:1C:2E:68"},
        {"binary_sensor": [_CHILD_BINARY_SENSOR], "sensor": []},
    )
    mock_hive.session.updateData = AsyncMock()
    mock_hive.sensor.getSensor = AsyncMock(side_effect=lambda device: device)

    with patch(
        "homeassistant.components.hive.Hive",
        return_value=mock_hive,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hub_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "hive-hub-id"), entry.entry_id
    )
    child_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "hive-child-id"), entry.entry_id
    )
    assert hub_device is not None
    assert child_device is not None
    assert child_device.via_device_id == hub_device.id


async def test_hub_diagnostic_sensor_not_linked_to_itself(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The hub's own diagnostic sensor must not link the hub device to itself."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA)
    entry.add_to_hass(hass)

    mock_hive = _make_mock_hive(
        {"macAddress": "00:1C:2B:1C:2E:68"},
        {"binary_sensor": [_HUB_BINARY_SENSOR], "sensor": []},
    )
    mock_hive.session.updateData = AsyncMock()
    mock_hive.sensor.getSensor = AsyncMock(side_effect=lambda device: device)

    with patch(
        "homeassistant.components.hive.Hive",
        return_value=mock_hive,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    hub_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "hive-hub-id"), entry.entry_id
    )
    assert hub_device is not None
    assert hub_device.via_device_id is None


async def test_glass_break_device_class(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the glass break binary sensor device class."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA)
    entry.add_to_hass(hass)

    mock_hive = _make_mock_hive(
        {"macAddress": "00:1C:2B:1C:2E:68"},
        {"binary_sensor": [_GLASS_BREAK_BINARY_SENSOR], "sensor": []},
    )
    mock_hive.session.updateData = AsyncMock()
    mock_hive.sensor.getSensor = AsyncMock(side_effect=lambda device: device)

    with patch(
        "homeassistant.components.hive.Hive",
        return_value=mock_hive,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "hive-glass-break-id-GLASS_BREAK"
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.GLASS_BREAK


async def test_all_platforms_forwarded_without_devices(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """All platforms are set up and the entry reloads on a device-less account."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA)
    entry.add_to_hass(hass)

    mock_hive = _make_mock_hive({})

    with patch(
        "homeassistant.components.hive.Hive",
        return_value=mock_hive,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        # Entity services must not depend on device discovery.
        assert hass.services.has_service(DOMAIN, SERVICE_BOOST_HOT_WATER)
        assert hass.services.has_service(DOMAIN, SERVICE_BOOST_HEATING_ON)
        assert hass.services.has_service(DOMAIN, SERVICE_BOOST_HEATING_OFF)

        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert "Error setting up entry" not in caplog.text
    assert "Error unloading entry" not in caplog.text


@pytest.mark.parametrize(
    "service",
    [SERVICE_BOOST_HEATING_ON, SERVICE_BOOST_HEATING_OFF, SERVICE_BOOST_HOT_WATER],
)
async def test_services_registered_without_config_entry(
    hass: HomeAssistant, service: str
) -> None:
    """Services are registered on component setup, without any config entry."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert hass.services.has_service(DOMAIN, service)


@pytest.mark.parametrize(
    ("service", "service_data", "entity_id", "mock_path", "expected_args"),
    [
        pytest.param(
            SERVICE_BOOST_HEATING_ON,
            {"time_period": "01:30:00", "temperature": 24.5},
            _CLIMATE_ENTITY_ID,
            "heating.setBoostOn",
            (90, 24.5),
            id="boost_heating_on",
        ),
        pytest.param(
            SERVICE_BOOST_HEATING_OFF,
            {},
            _CLIMATE_ENTITY_ID,
            "heating.setBoostOff",
            (),
            id="boost_heating_off",
        ),
        pytest.param(
            SERVICE_BOOST_HOT_WATER,
            {"time_period": "00:45:00", "on_off": "on"},
            _WATER_HEATER_ENTITY_ID,
            "hotwater.setBoostOn",
            (45,),
            id="boost_hot_water_on",
        ),
        pytest.param(
            SERVICE_BOOST_HOT_WATER,
            {"on_off": "off"},
            _WATER_HEATER_ENTITY_ID,
            "hotwater.setBoostOff",
            (),
            id="boost_hot_water_off",
        ),
    ],
)
async def test_services_call_entity_method(
    hass: HomeAssistant,
    service: str,
    service_data: dict[str, Any],
    entity_id: str,
    mock_path: str,
    expected_args: tuple[Any, ...],
) -> None:
    """Calling a Hive service reaches the targeted entity's method."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA)
    entry.add_to_hass(hass)

    mock_hive = _make_mock_hive(
        {},
        {"climate": [_CLIMATE_DEVICE], "water_heater": [_WATER_HEATER_DEVICE]},
    )
    mock_hive.session.updateData = AsyncMock()
    mock_hive.heating.getClimate = AsyncMock(side_effect=lambda device: device)
    mock_hive.heating.setBoostOn = AsyncMock()
    mock_hive.heating.setBoostOff = AsyncMock()
    mock_hive.hotwater.getWaterHeater = AsyncMock(side_effect=lambda device: device)
    mock_hive.hotwater.setBoostOn = AsyncMock()
    mock_hive.hotwater.setBoostOff = AsyncMock()

    with patch(
        "homeassistant.components.hive.Hive",
        return_value=mock_hive,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id)

    await hass.services.async_call(
        DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )

    mock_method = attrgetter(mock_path)(mock_hive)
    assert mock_method.call_count == 1
    assert mock_method.call_args.args[1:] == expected_args
