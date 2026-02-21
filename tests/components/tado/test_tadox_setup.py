"""Test the Tado X integration setup logic."""

from unittest.mock import MagicMock, patch

from homeassistant.components.tado import DOMAIN
from homeassistant.components.tado.const import TYPE_HEATING, TYPE_HOT_WATER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


def _mock_tado_x_base(mock_tado_api: MagicMock) -> None:
    """Set up shared Tado X mock state."""
    mock_tado_api._http.is_x_line = True
    mock_tado_api.get_me.return_value = {"homes": [{"id": 123, "name": "My Home"}]}
    mock_tado_api.get_weather.return_value = {}
    mock_tado_api.get_home.return_value = {"weather": {}, "geofence": {}}
    mock_tado_api.get_zone_state.return_value = MagicMock()


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create and set up a Tado config entry, skipping platform setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PASSWORD: "test"},
        unique_id="1",
        version=2,
    )
    entry.add_to_hass(hass)
    with patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_tadox_setup(hass: HomeAssistant, mock_tado_api: MagicMock) -> None:
    """Test setup of Tado X devices properly parses new dict keys."""

    _mock_tado_x_base(mock_tado_api)

    # Simulate PyTado 0.19.2 "get_devices" returning lists inside a list
    # (PyTado 0.19.2 bug: otherDevices appended as a sub-list)
    mock_tado_api.get_devices.return_value = [
        [
            {
                "type": "IB01",
                "serialNumber": "bridgeX_serial",
                "firmwareVersion": "99.9",
            }
        ],
        {
            "type": "VA02",
            "serialNumber": "thermostatX_serial",
            "firmwareVersion": "1.2",
        },
    ]

    mock_tado_api.get_zones.return_value = [
        {"roomId": 1, "roomName": "Living Room", "type": TYPE_HEATING}
    ]

    mock_tado_api.get_zone_states.return_value = [
        {"id": 1, "setting": {"power": "ON"}}
    ]

    entry = await _setup_entry(hass)

    # Verify that the coordinator flattened the device list and loaded both devices
    coordinator = entry.runtime_data
    assert coordinator is not None
    assert "bridgeX_serial" in coordinator.data["device"]
    assert "thermostatX_serial" in coordinator.data["device"]

    # Verify that the Tado X Bridge was pre-registered with correct fallback keys
    device_registry = dr.async_get(hass)
    bridge_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "bridgeX_serial")}
    )
    assert bridge_device is not None
    assert bridge_device.model == "IB01"
    assert bridge_device.name == "bridgeX_serial"
    assert bridge_device.sw_version == "99.9"

    # Verify zones were normalized correctly
    zone = coordinator.data["zone"][1]
    assert zone is not None


async def test_tadox_hot_water_zone_preserved(
    hass: HomeAssistant, mock_tado_api: MagicMock
) -> None:
    """Test that Tado X zones with TYPE_HOT_WATER keep their type during normalization.

    PyTado 0.19.2 returns zone types in the raw dict; the coordinator must
    preserve the original type rather than blindly defaulting to TYPE_HEATING.
    """

    _mock_tado_x_base(mock_tado_api)

    mock_tado_api.get_devices.return_value = [
        {
            "type": "VA02",
            "serialNumber": "thermostatX_serial",
            "firmwareVersion": "1.0",
        }
    ]

    # Two zones: one heating, one hot water
    mock_tado_api.get_zones.return_value = [
        {"roomId": 1, "roomName": "Living Room", "type": TYPE_HEATING},
        {"roomId": 2, "roomName": "Hot Water", "type": TYPE_HOT_WATER},
    ]

    mock_tado_api.get_zone_states.return_value = [
        {"id": 1, "setting": {"power": "ON"}},
        {"id": 2, "setting": {"power": "ON"}},
    ]

    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data

    # Verify both zones were loaded
    assert 1 in coordinator.data["zone"]
    assert 2 in coordinator.data["zone"]

    # Verify the zone types on the coordinator's self.zones list
    zone_types = {z["id"]: z["type"] for z in coordinator.zones}
    assert zone_types[1] == TYPE_HEATING, "Heating zone type should be preserved"
    assert zone_types[2] == TYPE_HOT_WATER, "Hot water zone type must NOT be overridden"


async def test_tadox_zone_without_type_defaults_to_heating(
    hass: HomeAssistant, mock_tado_api: MagicMock
) -> None:
    """Test that Tado X zones missing a 'type' key default to TYPE_HEATING."""

    _mock_tado_x_base(mock_tado_api)

    mock_tado_api.get_devices.return_value = [
        {
            "type": "VA02",
            "serialNumber": "thermostatX_serial",
            "firmwareVersion": "1.0",
        }
    ]

    # Zone without an explicit "type" key
    mock_tado_api.get_zones.return_value = [
        {"roomId": 1, "roomName": "Bedroom"},
    ]

    mock_tado_api.get_zone_states.return_value = [
        {"id": 1, "setting": {"power": "ON"}},
    ]

    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data

    # Zone without type should default to TYPE_HEATING
    zone_types = {z["id"]: z["type"] for z in coordinator.zones}
    assert zone_types[1] == TYPE_HEATING, "Zone without type should default to HEATING"
