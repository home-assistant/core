"""Tests for Diesel Heater config flow.

Tests cover all flow paths: bluetooth discovery, user selection,
manual MAC entry, and options flow.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from tests.conftest import _AbortFlow

from custom_components.diesel_heater.config_flow import (
    VevorHeaterConfigFlow,
    VevorHeaterOptionsFlowHandler,
)
from custom_components.diesel_heater.const import (
    CONF_AUTO_OFFSET_MAX,
    CONF_EXTERNAL_TEMP_SENSOR,
    CONF_PIN,
    CONF_PRESET_AWAY_TEMP,
    CONF_PRESET_COMFORT_TEMP,
    DEFAULT_AUTO_OFFSET_MAX,
    DEFAULT_PIN,
    DEFAULT_PRESET_AWAY_TEMP,
    DEFAULT_PRESET_COMFORT_TEMP,
    SERVICE_UUID,
)

CONF_ADDRESS = "address"  # matches homeassistant.const.CONF_ADDRESS stub
MOCK_ADDRESS = "AA:BB:CC:DD:EE:FF"


def _make_ble_discovery(
    address=MOCK_ADDRESS,
    name="Diesel Heater",
    service_uuids=None,
    manufacturer_data=None,
):
    """Create a mock BluetoothServiceInfoBleak."""
    info = MagicMock()
    info.address = address
    info.name = name
    info.service_uuids = service_uuids if service_uuids is not None else [SERVICE_UUID]
    info.manufacturer_data = manufacturer_data or {}
    return info


# ---------------------------------------------------------------------------
# Bluetooth discovery flow
# ---------------------------------------------------------------------------

class TestBluetoothDiscovery:
    """Test async_step_bluetooth → async_step_confirm."""

    async def test_discovery_proceeds_to_confirm(self):
        flow = VevorHeaterConfigFlow()
        discovery = _make_ble_discovery()

        result = await flow.async_step_bluetooth(discovery)

        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

    async def test_discovery_sets_unique_id(self):
        flow = VevorHeaterConfigFlow()
        discovery = _make_ble_discovery()

        await flow.async_step_bluetooth(discovery)

        assert flow._unique_id == MOCK_ADDRESS

    async def test_discovery_already_configured_aborts(self):
        flow = VevorHeaterConfigFlow()
        flow._existing_unique_ids = {MOCK_ADDRESS}
        discovery = _make_ble_discovery()

        with pytest.raises(_AbortFlow, match="already_configured"):
            await flow.async_step_bluetooth(discovery)


# ---------------------------------------------------------------------------
# Confirm step (after bluetooth discovery)
# ---------------------------------------------------------------------------

class TestConfirmStep:
    """Test async_step_confirm."""

    async def test_shows_form_when_no_input(self):
        flow = VevorHeaterConfigFlow()
        flow._discovery_info = _make_ble_discovery()

        result = await flow.async_step_confirm()

        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

    async def test_creates_entry_with_default_pin(self):
        flow = VevorHeaterConfigFlow()
        flow._discovery_info = _make_ble_discovery()

        result = await flow.async_step_confirm(user_input={})

        assert result["type"] == "create_entry"
        assert result["data"][CONF_ADDRESS] == MOCK_ADDRESS
        assert result["data"][CONF_PIN] == DEFAULT_PIN

    async def test_creates_entry_with_custom_pin(self):
        flow = VevorHeaterConfigFlow()
        flow._discovery_info = _make_ble_discovery()

        result = await flow.async_step_confirm(user_input={CONF_PIN: 5678})

        assert result["type"] == "create_entry"
        assert result["data"][CONF_PIN] == 5678

    async def test_title_uses_last_chars_of_address(self):
        flow = VevorHeaterConfigFlow()
        flow._discovery_info = _make_ble_discovery(address="AA:BB:CC:DD:EE:FF")

        result = await flow.async_step_confirm(user_input={})

        # address[-5:] = "EE:FF" → replace ":" → "EEFF"
        assert "EEFF" in result["title"]


# ---------------------------------------------------------------------------
# User step (manual device selection)
# ---------------------------------------------------------------------------

class TestUserStep:
    """Test async_step_user."""

    async def test_no_devices_redirects_to_manual(self):
        flow = VevorHeaterConfigFlow()

        with patch(
            "custom_components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = []
            result = await flow.async_step_user()

        assert result["type"] == "form"
        assert result["step_id"] == "manual"

    async def test_detects_device_by_service_uuid(self):
        flow = VevorHeaterConfigFlow()
        discovery = _make_ble_discovery(
            name="Unknown",
            service_uuids=[SERVICE_UUID],
            manufacturer_data={},
        )

        with patch(
            "custom_components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = [discovery]
            result = await flow.async_step_user()

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert MOCK_ADDRESS in flow._discovered_devices

    async def test_detects_device_by_name_vevor(self):
        flow = VevorHeaterConfigFlow()
        discovery = _make_ble_discovery(
            name="VEVOR_HT_123",
            service_uuids=[],
            manufacturer_data={},
        )

        with patch(
            "custom_components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = [discovery]
            result = await flow.async_step_user()

        assert result["step_id"] == "user"
        assert MOCK_ADDRESS in flow._discovered_devices

    async def test_detects_device_by_name_heater(self):
        flow = VevorHeaterConfigFlow()
        discovery = _make_ble_discovery(
            name="Air Heater Pro",
            service_uuids=[],
            manufacturer_data={},
        )

        with patch(
            "custom_components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = [discovery]
            result = await flow.async_step_user()

        assert MOCK_ADDRESS in flow._discovered_devices

    async def test_detects_device_by_manufacturer_id(self):
        flow = VevorHeaterConfigFlow()
        discovery = _make_ble_discovery(
            name="Unknown",
            service_uuids=[],
            manufacturer_data={65535: b"\x01\x02"},
        )

        with patch(
            "custom_components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = [discovery]
            result = await flow.async_step_user()

        assert result["step_id"] == "user"
        assert MOCK_ADDRESS in flow._discovered_devices

    async def test_skips_non_vevor_device(self):
        flow = VevorHeaterConfigFlow()
        discovery = _make_ble_discovery(
            name="Some speaker",
            service_uuids=["0000180a-0000-1000-8000-00805f9b34fb"],
            manufacturer_data={76: b"\x01"},  # Apple
        )

        with patch(
            "custom_components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = [discovery]
            result = await flow.async_step_user()

        assert result["step_id"] == "manual"

    async def test_filters_already_configured_addresses(self):
        flow = VevorHeaterConfigFlow()
        flow._current_ids = {MOCK_ADDRESS}
        discovery = _make_ble_discovery(service_uuids=[SERVICE_UUID])

        with patch(
            "custom_components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = [discovery]
            result = await flow.async_step_user()

        # Only device was filtered → falls through to manual
        assert result["step_id"] == "manual"

    async def test_skips_already_discovered_devices(self):
        """Test that devices already discovered in this flow are skipped."""
        flow = VevorHeaterConfigFlow()
        # Pre-populate _discovered_devices with a mock discovery info
        existing_discovery = _make_ble_discovery(service_uuids=[SERVICE_UUID])
        flow._discovered_devices = {MOCK_ADDRESS: existing_discovery}
        # Create a new discovery with the same address
        new_discovery = _make_ble_discovery(service_uuids=[SERVICE_UUID])

        with patch(
            "custom_components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = [new_discovery]
            result = await flow.async_step_user()

        # Device was already discovered → shows form with existing device
        assert result["step_id"] == "user"
        # The device should still be in _discovered_devices (not added again)
        assert len(flow._discovered_devices) == 1

    async def test_select_device_creates_entry(self):
        flow = VevorHeaterConfigFlow()

        result = await flow.async_step_user(
            user_input={CONF_ADDRESS: MOCK_ADDRESS, CONF_PIN: DEFAULT_PIN}
        )

        assert result["type"] == "create_entry"
        assert result["data"][CONF_ADDRESS] == MOCK_ADDRESS
        assert result["data"][CONF_PIN] == DEFAULT_PIN

    async def test_select_device_default_pin(self):
        flow = VevorHeaterConfigFlow()

        result = await flow.async_step_user(
            user_input={CONF_ADDRESS: MOCK_ADDRESS}
        )

        assert result["data"][CONF_PIN] == DEFAULT_PIN

    async def test_select_device_already_configured_aborts(self):
        flow = VevorHeaterConfigFlow()
        flow._existing_unique_ids = {MOCK_ADDRESS}

        with pytest.raises(_AbortFlow, match="already_configured"):
            await flow.async_step_user(
                user_input={CONF_ADDRESS: MOCK_ADDRESS}
            )

    async def test_shows_multiple_devices(self):
        flow = VevorHeaterConfigFlow()
        d1 = _make_ble_discovery(
            address="11:22:33:44:55:66",
            name="Heater 1",
            service_uuids=[SERVICE_UUID],
        )
        d2 = _make_ble_discovery(
            address="77:88:99:AA:BB:CC",
            name="Heater 2",
            manufacturer_data={65535: b"\x00"},
        )

        with patch(
            "custom_components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = [d1, d2]
            result = await flow.async_step_user()

        assert result["step_id"] == "user"
        assert len(flow._discovered_devices) == 2


# ---------------------------------------------------------------------------
# Manual MAC entry
# ---------------------------------------------------------------------------

class TestManualStep:
    """Test async_step_manual."""

    async def test_shows_form_when_no_input(self):
        flow = VevorHeaterConfigFlow()

        result = await flow.async_step_manual()

        assert result["type"] == "form"
        assert result["step_id"] == "manual"

    async def test_valid_mac_creates_entry(self):
        flow = VevorHeaterConfigFlow()

        result = await flow.async_step_manual(
            user_input={CONF_ADDRESS: "aa:bb:cc:dd:ee:ff", CONF_PIN: DEFAULT_PIN}
        )

        assert result["type"] == "create_entry"
        assert result["data"][CONF_ADDRESS] == "AA:BB:CC:DD:EE:FF"
        assert result["data"][CONF_PIN] == DEFAULT_PIN

    async def test_mac_uppercased(self):
        flow = VevorHeaterConfigFlow()

        result = await flow.async_step_manual(
            user_input={CONF_ADDRESS: "aa:bb:cc:dd:ee:ff"}
        )

        assert result["data"][CONF_ADDRESS] == "AA:BB:CC:DD:EE:FF"

    async def test_mac_with_hyphens_accepted(self):
        flow = VevorHeaterConfigFlow()

        result = await flow.async_step_manual(
            user_input={CONF_ADDRESS: "AA-BB-CC-DD-EE-FF"}
        )

        assert result["type"] == "create_entry"

    async def test_invalid_mac_shows_error(self):
        flow = VevorHeaterConfigFlow()

        result = await flow.async_step_manual(
            user_input={CONF_ADDRESS: "not-a-mac"}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "manual"
        assert result["errors"][CONF_ADDRESS] == "invalid_mac"

    async def test_short_mac_shows_error(self):
        flow = VevorHeaterConfigFlow()

        result = await flow.async_step_manual(
            user_input={CONF_ADDRESS: "AA:BB:CC"}
        )

        assert result["errors"][CONF_ADDRESS] == "invalid_mac"

    async def test_mac_without_separators_shows_error(self):
        flow = VevorHeaterConfigFlow()

        result = await flow.async_step_manual(
            user_input={CONF_ADDRESS: "AABBCCDDEEFF"}
        )

        assert result["errors"][CONF_ADDRESS] == "invalid_mac"

    async def test_already_configured_aborts(self):
        flow = VevorHeaterConfigFlow()
        flow._existing_unique_ids = {"AA:BB:CC:DD:EE:FF"}

        with pytest.raises(_AbortFlow, match="already_configured"):
            await flow.async_step_manual(
                user_input={CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"}
            )

    async def test_title_format(self):
        flow = VevorHeaterConfigFlow()

        result = await flow.async_step_manual(
            user_input={CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"}
        )

        assert "EEFF" in result["title"]

    async def test_default_pin_when_not_provided(self):
        flow = VevorHeaterConfigFlow()

        result = await flow.async_step_manual(
            user_input={CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"}
        )

        assert result["data"][CONF_PIN] == DEFAULT_PIN


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------

class TestGetOptionsFlow:
    """Test async_get_options_flow static method."""

    def test_returns_options_handler(self):
        handler = VevorHeaterConfigFlow.async_get_options_flow(MagicMock())
        assert isinstance(handler, VevorHeaterOptionsFlowHandler)


class TestOptionsFlow:
    """Test VevorHeaterOptionsFlowHandler.async_step_init."""

    def _create_flow(self, data=None):
        """Create an options flow with a mock config entry."""
        flow = VevorHeaterOptionsFlowHandler()
        entry = MagicMock()
        entry.data = data if data is not None else {
            CONF_ADDRESS: MOCK_ADDRESS,
            CONF_PIN: DEFAULT_PIN,
        }
        flow._config_entry = entry
        return flow

    async def test_shows_form_when_no_input(self):
        flow = self._create_flow()

        result = await flow.async_step_init()

        assert result["type"] == "form"
        assert result["step_id"] == "init"

    async def test_schema_has_pin_field(self):
        flow = self._create_flow()

        result = await flow.async_step_init()

        schema_keys = {
            k.schema for k in result["data_schema"].schema.keys()
            if hasattr(k, "schema")
        }
        assert CONF_PIN in schema_keys

    async def test_schema_has_preset_fields(self):
        flow = self._create_flow()

        result = await flow.async_step_init()

        schema_keys = {
            k.schema for k in result["data_schema"].schema.keys()
            if hasattr(k, "schema")
        }
        assert CONF_PRESET_AWAY_TEMP in schema_keys
        assert CONF_PRESET_COMFORT_TEMP in schema_keys

    async def test_schema_has_external_sensor_field(self):
        flow = self._create_flow()

        result = await flow.async_step_init()

        schema_keys = {
            k.schema for k in result["data_schema"].schema.keys()
            if hasattr(k, "schema")
        }
        assert CONF_EXTERNAL_TEMP_SENSOR in schema_keys

    async def test_auto_offset_hidden_without_external_sensor(self):
        flow = self._create_flow()

        result = await flow.async_step_init()

        schema_keys = {
            k.schema for k in result["data_schema"].schema.keys()
            if hasattr(k, "schema")
        }
        assert CONF_AUTO_OFFSET_MAX not in schema_keys

    async def test_auto_offset_shown_with_external_sensor(self):
        flow = self._create_flow(data={
            CONF_ADDRESS: MOCK_ADDRESS,
            CONF_PIN: DEFAULT_PIN,
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.outside_temp",
        })

        result = await flow.async_step_init()

        schema_keys = {
            k.schema for k in result["data_schema"].schema.keys()
            if hasattr(k, "schema")
        }
        assert CONF_AUTO_OFFSET_MAX in schema_keys

    async def test_updates_pin(self):
        flow = self._create_flow()

        result = await flow.async_step_init(user_input={
            CONF_PIN: 9999,
            CONF_PRESET_AWAY_TEMP: DEFAULT_PRESET_AWAY_TEMP,
            CONF_PRESET_COMFORT_TEMP: DEFAULT_PRESET_COMFORT_TEMP,
        })

        assert result["type"] == "create_entry"
        call_kwargs = flow.hass.config_entries.async_update_entry.call_args
        new_data = call_kwargs[1]["data"]
        assert new_data[CONF_PIN] == 9999

    async def test_updates_preset_temperatures(self):
        flow = self._create_flow()

        result = await flow.async_step_init(user_input={
            CONF_PIN: DEFAULT_PIN,
            CONF_PRESET_AWAY_TEMP: 10,
            CONF_PRESET_COMFORT_TEMP: 25,
        })

        assert result["type"] == "create_entry"
        call_kwargs = flow.hass.config_entries.async_update_entry.call_args
        new_data = call_kwargs[1]["data"]
        assert new_data[CONF_PRESET_AWAY_TEMP] == 10
        assert new_data[CONF_PRESET_COMFORT_TEMP] == 25

    async def test_sets_external_sensor(self):
        flow = self._create_flow()

        result = await flow.async_step_init(user_input={
            CONF_PIN: DEFAULT_PIN,
            CONF_PRESET_AWAY_TEMP: DEFAULT_PRESET_AWAY_TEMP,
            CONF_PRESET_COMFORT_TEMP: DEFAULT_PRESET_COMFORT_TEMP,
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.outside_temp",
        })

        assert result["type"] == "create_entry"
        call_kwargs = flow.hass.config_entries.async_update_entry.call_args
        new_data = call_kwargs[1]["data"]
        assert new_data[CONF_EXTERNAL_TEMP_SENSOR] == "sensor.outside_temp"

    async def test_clears_external_sensor(self):
        flow = self._create_flow(data={
            CONF_ADDRESS: MOCK_ADDRESS,
            CONF_PIN: DEFAULT_PIN,
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.outside_temp",
        })

        result = await flow.async_step_init(user_input={
            CONF_PIN: DEFAULT_PIN,
            CONF_PRESET_AWAY_TEMP: DEFAULT_PRESET_AWAY_TEMP,
            CONF_PRESET_COMFORT_TEMP: DEFAULT_PRESET_COMFORT_TEMP,
            # No external sensor → cleared
        })

        assert result["type"] == "create_entry"
        call_kwargs = flow.hass.config_entries.async_update_entry.call_args
        new_data = call_kwargs[1]["data"]
        assert CONF_EXTERNAL_TEMP_SENSOR not in new_data

    async def test_clears_external_sensor_when_none(self):
        flow = self._create_flow(data={
            CONF_ADDRESS: MOCK_ADDRESS,
            CONF_PIN: DEFAULT_PIN,
            CONF_EXTERNAL_TEMP_SENSOR: "sensor.outside_temp",
        })

        result = await flow.async_step_init(user_input={
            CONF_PIN: DEFAULT_PIN,
            CONF_PRESET_AWAY_TEMP: DEFAULT_PRESET_AWAY_TEMP,
            CONF_PRESET_COMFORT_TEMP: DEFAULT_PRESET_COMFORT_TEMP,
            CONF_EXTERNAL_TEMP_SENSOR: None,
        })

        assert result["type"] == "create_entry"
        call_kwargs = flow.hass.config_entries.async_update_entry.call_args
        new_data = call_kwargs[1]["data"]
        assert CONF_EXTERNAL_TEMP_SENSOR not in new_data

    async def test_preserves_existing_data(self):
        """Options update should preserve data keys not in user_input."""
        flow = self._create_flow(data={
            CONF_ADDRESS: MOCK_ADDRESS,
            CONF_PIN: DEFAULT_PIN,
        })

        await flow.async_step_init(user_input={
            CONF_PIN: 5678,
            CONF_PRESET_AWAY_TEMP: DEFAULT_PRESET_AWAY_TEMP,
            CONF_PRESET_COMFORT_TEMP: DEFAULT_PRESET_COMFORT_TEMP,
        })

        call_kwargs = flow.hass.config_entries.async_update_entry.call_args
        new_data = call_kwargs[1]["data"]
        # Address should still be there (from original data)
        assert new_data[CONF_ADDRESS] == MOCK_ADDRESS
