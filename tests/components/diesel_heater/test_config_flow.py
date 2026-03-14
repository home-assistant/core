"""Tests for Diesel Heater config flow.

Tests cover all flow paths: bluetooth discovery, user selection,
manual MAC entry, and options flow.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from homeassistant.data_entry_flow import AbortFlow

from homeassistant.components.diesel_heater.config_flow import (
    VevorHeaterConfigFlow,
    VevorHeaterOptionsFlowHandler,
)
from homeassistant.components.diesel_heater.const import (
    CONF_PIN,
    CONF_PRESET_AWAY_TEMP,
    CONF_PRESET_COMFORT_TEMP,
    DEFAULT_PIN,
    DEFAULT_PRESET_AWAY_TEMP,
    DEFAULT_PRESET_COMFORT_TEMP,
    DOMAIN,
    SERVICE_UUID,
)

CONF_ADDRESS = "address"  # matches homeassistant.const.CONF_ADDRESS
MOCK_ADDRESS = "AA:BB:CC:DD:EE:FF"


def _make_flow(*, configured_addresses=None):
    """Create a VevorHeaterConfigFlow with a mock hass."""
    flow = VevorHeaterConfigFlow()
    flow.hass = MagicMock()
    if configured_addresses:
        flow.hass.config_entries.async_entries.return_value = [
            MagicMock(unique_id=addr) for addr in configured_addresses
        ]
    else:
        flow.hass.config_entries.async_entries.return_value = []
    flow.hass.config_entries.flow.async_progress_by_handler.return_value = []
    return flow


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
    """Test async_step_bluetooth -> async_step_confirm."""

    async def test_discovery_proceeds_to_confirm(self):
        flow = _make_flow()
        discovery = _make_ble_discovery()

        result = await flow.async_step_bluetooth(discovery)

        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

    async def test_discovery_sets_unique_id(self):
        flow = _make_flow()
        discovery = _make_ble_discovery()

        await flow.async_step_bluetooth(discovery)

        assert flow.unique_id == MOCK_ADDRESS

    async def test_discovery_already_configured_aborts(self):
        flow = _make_flow(configured_addresses={MOCK_ADDRESS})
        discovery = _make_ble_discovery()

        with pytest.raises(AbortFlow, match="already_configured"):
            await flow.async_step_bluetooth(discovery)


# ---------------------------------------------------------------------------
# Confirm step (after bluetooth discovery)
# ---------------------------------------------------------------------------

class TestConfirmStep:
    """Test async_step_confirm."""

    async def test_shows_form_when_no_input(self):
        flow = _make_flow()
        flow._discovery_info = _make_ble_discovery()

        result = await flow.async_step_confirm()

        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

    async def test_creates_entry_with_default_pin(self):
        flow = _make_flow()
        flow._discovery_info = _make_ble_discovery()

        result = await flow.async_step_confirm(user_input={})

        assert result["type"] == "create_entry"
        assert result["data"][CONF_ADDRESS] == MOCK_ADDRESS
        assert result["data"][CONF_PIN] == DEFAULT_PIN

    async def test_creates_entry_with_custom_pin(self):
        flow = _make_flow()
        flow._discovery_info = _make_ble_discovery()

        result = await flow.async_step_confirm(user_input={CONF_PIN: 5678})

        assert result["type"] == "create_entry"
        assert result["data"][CONF_PIN] == 5678

    async def test_title_uses_last_chars_of_address(self):
        flow = _make_flow()
        flow._discovery_info = _make_ble_discovery(address="AA:BB:CC:DD:EE:FF")

        result = await flow.async_step_confirm(user_input={})

        assert "Diesel Heater (EEFF)" in result["title"]


# ---------------------------------------------------------------------------
# User step (manual device selection)
# ---------------------------------------------------------------------------

class TestUserStep:
    """Test async_step_user."""

    async def test_no_devices_redirects_to_manual(self):
        flow = _make_flow()

        with patch(
            "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = []
            result = await flow.async_step_user()

        assert result["type"] == "form"
        assert result["step_id"] == "manual"

    async def test_detects_device_by_service_uuid(self):
        flow = _make_flow()
        discovery = _make_ble_discovery(
            name="Unknown",
            service_uuids=[SERVICE_UUID],
            manufacturer_data={},
        )

        with patch(
            "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = [discovery]
            result = await flow.async_step_user()

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert MOCK_ADDRESS in flow._discovered_devices

    async def test_detects_device_by_name_vevor(self):
        flow = _make_flow()
        discovery = _make_ble_discovery(
            name="VEVOR_HT_123",
            service_uuids=[],
            manufacturer_data={},
        )

        with patch(
            "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = [discovery]
            result = await flow.async_step_user()

        assert result["step_id"] == "user"
        assert MOCK_ADDRESS in flow._discovered_devices

    async def test_detects_device_by_name_heater(self):
        flow = _make_flow()
        discovery = _make_ble_discovery(
            name="Air Heater Pro",
            service_uuids=[],
            manufacturer_data={},
        )

        with patch(
            "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = [discovery]
            result = await flow.async_step_user()

        assert MOCK_ADDRESS in flow._discovered_devices

    async def test_detects_device_by_manufacturer_id(self):
        flow = _make_flow()
        discovery = _make_ble_discovery(
            name="Unknown",
            service_uuids=[],
            manufacturer_data={65535: b"\x01\x02"},
        )

        with patch(
            "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = [discovery]
            result = await flow.async_step_user()

        assert result["step_id"] == "user"
        assert MOCK_ADDRESS in flow._discovered_devices

    async def test_skips_non_vevor_device(self):
        flow = _make_flow()
        discovery = _make_ble_discovery(
            name="Some speaker",
            service_uuids=["0000180a-0000-1000-8000-00805f9b34fb"],
            manufacturer_data={76: b"\x01"},  # Apple
        )

        with patch(
            "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = [discovery]
            result = await flow.async_step_user()

        assert result["step_id"] == "manual"

    async def test_filters_already_configured_addresses(self):
        flow = _make_flow(configured_addresses={MOCK_ADDRESS})
        discovery = _make_ble_discovery(service_uuids=[SERVICE_UUID])

        with patch(
            "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = [discovery]
            result = await flow.async_step_user()

        # Only device was filtered -> falls through to manual
        assert result["step_id"] == "manual"

    async def test_skips_already_discovered_devices(self):
        """Test that devices already discovered in this flow are skipped."""
        flow = _make_flow()
        existing_discovery = _make_ble_discovery(service_uuids=[SERVICE_UUID])
        flow._discovered_devices = {MOCK_ADDRESS: existing_discovery}
        new_discovery = _make_ble_discovery(service_uuids=[SERVICE_UUID])

        with patch(
            "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ) as mock_bt:
            mock_bt.async_discovered_service_info.return_value = [new_discovery]
            result = await flow.async_step_user()

        assert result["step_id"] == "user"
        assert len(flow._discovered_devices) == 1

    async def test_select_device_creates_entry(self):
        flow = _make_flow()

        result = await flow.async_step_user(
            user_input={CONF_ADDRESS: MOCK_ADDRESS, CONF_PIN: DEFAULT_PIN}
        )

        assert result["type"] == "create_entry"
        assert result["data"][CONF_ADDRESS] == MOCK_ADDRESS
        assert result["data"][CONF_PIN] == DEFAULT_PIN

    async def test_select_device_default_pin(self):
        flow = _make_flow()

        result = await flow.async_step_user(
            user_input={CONF_ADDRESS: MOCK_ADDRESS}
        )

        assert result["data"][CONF_PIN] == DEFAULT_PIN

    async def test_select_device_already_configured_aborts(self):
        flow = _make_flow(configured_addresses={MOCK_ADDRESS})

        with pytest.raises(AbortFlow, match="already_configured"):
            await flow.async_step_user(
                user_input={CONF_ADDRESS: MOCK_ADDRESS}
            )

    async def test_shows_multiple_devices(self):
        flow = _make_flow()
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
            "homeassistant.components.diesel_heater.config_flow.bluetooth"
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
        flow = _make_flow()

        result = await flow.async_step_manual()

        assert result["type"] == "form"
        assert result["step_id"] == "manual"

    async def test_valid_mac_creates_entry(self):
        flow = _make_flow()

        result = await flow.async_step_manual(
            user_input={CONF_ADDRESS: "aa:bb:cc:dd:ee:ff", CONF_PIN: DEFAULT_PIN}
        )

        assert result["type"] == "create_entry"
        assert result["data"][CONF_ADDRESS] == "AA:BB:CC:DD:EE:FF"
        assert result["data"][CONF_PIN] == DEFAULT_PIN

    async def test_mac_uppercased(self):
        flow = _make_flow()

        result = await flow.async_step_manual(
            user_input={CONF_ADDRESS: "aa:bb:cc:dd:ee:ff"}
        )

        assert result["data"][CONF_ADDRESS] == "AA:BB:CC:DD:EE:FF"

    async def test_mac_with_hyphens_accepted(self):
        flow = _make_flow()

        result = await flow.async_step_manual(
            user_input={CONF_ADDRESS: "AA-BB-CC-DD-EE-FF"}
        )

        assert result["type"] == "create_entry"

    async def test_invalid_mac_shows_error(self):
        flow = _make_flow()

        result = await flow.async_step_manual(
            user_input={CONF_ADDRESS: "not-a-mac"}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "manual"
        assert result["errors"][CONF_ADDRESS] == "invalid_mac"

    async def test_short_mac_shows_error(self):
        flow = _make_flow()

        result = await flow.async_step_manual(
            user_input={CONF_ADDRESS: "AA:BB:CC"}
        )

        assert result["errors"][CONF_ADDRESS] == "invalid_mac"

    async def test_mac_without_separators_shows_error(self):
        flow = _make_flow()

        result = await flow.async_step_manual(
            user_input={CONF_ADDRESS: "AABBCCDDEEFF"}
        )

        assert result["errors"][CONF_ADDRESS] == "invalid_mac"

    async def test_already_configured_aborts(self):
        flow = _make_flow(configured_addresses={"AA:BB:CC:DD:EE:FF"})

        with pytest.raises(AbortFlow, match="already_configured"):
            await flow.async_step_manual(
                user_input={CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"}
            )

    async def test_title_format(self):
        flow = _make_flow()

        result = await flow.async_step_manual(
            user_input={CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"}
        )

        assert "Diesel Heater (EEFF)" in result["title"]

    async def test_default_pin_when_not_provided(self):
        flow = _make_flow()

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

    def _create_flow(self, data=None, options=None):
        """Create an options flow with a mock config entry."""
        flow = VevorHeaterOptionsFlowHandler()
        entry = MagicMock()
        entry.data = data if data is not None else {
            CONF_ADDRESS: MOCK_ADDRESS,
            CONF_PIN: DEFAULT_PIN,
        }
        entry.options = options if options is not None else {}
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

    async def test_updates_pin(self):
        flow = self._create_flow()

        result = await flow.async_step_init(user_input={
            CONF_PIN: 9999,
            CONF_PRESET_AWAY_TEMP: DEFAULT_PRESET_AWAY_TEMP,
            CONF_PRESET_COMFORT_TEMP: DEFAULT_PRESET_COMFORT_TEMP,
        })

        assert result["type"] == "create_entry"
        assert result["data"][CONF_PIN] == 9999

    async def test_updates_preset_temperatures(self):
        flow = self._create_flow()

        result = await flow.async_step_init(user_input={
            CONF_PIN: DEFAULT_PIN,
            CONF_PRESET_AWAY_TEMP: 10,
            CONF_PRESET_COMFORT_TEMP: 25,
        })

        assert result["type"] == "create_entry"
        assert result["data"][CONF_PRESET_AWAY_TEMP] == 10
        assert result["data"][CONF_PRESET_COMFORT_TEMP] == 25

    async def test_preserves_all_submitted_options(self):
        """Options should contain all submitted fields."""
        flow = self._create_flow()

        result = await flow.async_step_init(user_input={
            CONF_PIN: 5678,
            CONF_PRESET_AWAY_TEMP: DEFAULT_PRESET_AWAY_TEMP,
            CONF_PRESET_COMFORT_TEMP: DEFAULT_PRESET_COMFORT_TEMP,
        })

        assert result["data"][CONF_PIN] == 5678
        assert result["data"][CONF_PRESET_AWAY_TEMP] == DEFAULT_PRESET_AWAY_TEMP
        assert result["data"][CONF_PRESET_COMFORT_TEMP] == DEFAULT_PRESET_COMFORT_TEMP
