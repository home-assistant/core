"""Tests for the Energy Tracker __init__ module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import pytest
from tests.common import MockConfigEntry

from homeassistant.components.energy_tracker import (
    async_handle_send_meter_reading,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.energy_tracker.const import (
    CONF_API_TOKEN,
    DOMAIN,
    SERVICE_SEND_METER_READING,
)


def create_service_call(
    hass: HomeAssistant,
    domain: str,
    service: str,
    data: dict,
) -> ServiceCall:
    """Create a ServiceCall instance for testing."""
    return ServiceCall(hass, domain, service, data=data)


class TestAsyncSetup:
    """Test async_setup function."""

    async def test_async_setup_returns_true(self, hass: HomeAssistant):
        """Test that async_setup returns True (YAML not supported)."""
        # Arrange
        config = {}

        # Act
        result = await async_setup(hass, config)

        # Assert
        assert result is True


class TestAsyncSetupEntry:
    """Test async_setup_entry function."""

    async def test_setup_entry_stores_token_in_runtime_data(self, hass: HomeAssistant):
        """Test that setup_entry stores API token in runtime_data."""
        # Arrange
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Account",
            data={
                "name": "Test Account",
                CONF_API_TOKEN: "test-token-123",
            },
            entry_id="test-entry-id",
        )
        entry.add_to_hass(hass)

        # Act
        result = await async_setup_entry(hass, entry)

        # Assert
        assert result is True
        assert entry.runtime_data == "test-token-123"

    async def test_setup_entry_registers_service_once(self, hass: HomeAssistant):
        """Test that service is registered only once for multiple entries."""
        # Arrange
        entry1 = MockConfigEntry(
            domain=DOMAIN,
            title="Account 1",
            data={"name": "Account 1", CONF_API_TOKEN: "token-1"},
            entry_id="entry-1",
        )
        entry1.add_to_hass(hass)

        entry2 = MockConfigEntry(
            domain=DOMAIN,
            title="Account 2",
            data={"name": "Account 2", CONF_API_TOKEN: "token-2"},
            entry_id="entry-2",
        )
        entry2.add_to_hass(hass)

        # Act
        await async_setup_entry(hass, entry1)
        await async_setup_entry(hass, entry2)

        # Assert
        assert hass.services.has_service(DOMAIN, SERVICE_SEND_METER_READING)
        # Service should only be registered once
        assert len(list(hass.services.async_services()[DOMAIN])) == 1


class TestAsyncUnloadEntry:
    """Test async_unload_entry function."""

    async def test_unload_entry_returns_true(self, hass: HomeAssistant):
        """Test that unload_entry returns True."""
        # Arrange
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Account",
            data={"name": "Test Account", CONF_API_TOKEN: "test-token"},
            entry_id="test-entry-id",
        )
        entry.add_to_hass(hass)
        await async_setup_entry(hass, entry)

        # Act
        result = await async_unload_entry(hass, entry)

        # Assert
        assert result is True

    async def test_unload_last_entry_removes_service(self, hass: HomeAssistant):
        """Test that unloading last entry removes service."""
        # Arrange
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Account",
            data={"name": "Test Account", CONF_API_TOKEN: "test-token"},
            entry_id="test-entry-id",
        )
        entry.add_to_hass(hass)
        await async_setup_entry(hass, entry)
        assert hass.services.has_service(DOMAIN, SERVICE_SEND_METER_READING)

        # Act
        await async_unload_entry(hass, entry)

        # Assert
        assert not hass.services.has_service(DOMAIN, SERVICE_SEND_METER_READING)

    async def test_unload_one_of_multiple_entries_keeps_service(
        self, hass: HomeAssistant
    ):
        """Test that unloading one entry keeps service when others exist."""
        # Arrange
        entry1 = MockConfigEntry(
            domain=DOMAIN,
            title="Account 1",
            data={"name": "Account 1", CONF_API_TOKEN: "token-1"},
            entry_id="entry-1",
        )
        entry1.add_to_hass(hass)

        entry2 = MockConfigEntry(
            domain=DOMAIN,
            title="Account 2",
            data={"name": "Account 2", CONF_API_TOKEN: "token-2"},
            entry_id="entry-2",
        )
        entry2.add_to_hass(hass)

        await async_setup_entry(hass, entry1)
        await async_setup_entry(hass, entry2)

        # Act
        await async_unload_entry(hass, entry1)

        # Assert
        assert hass.services.has_service(DOMAIN, SERVICE_SEND_METER_READING)
        # entry2 still has its runtime_data
        assert entry2.runtime_data == "token-2"


class TestAsyncHandleSendMeterReading:
    """Test async_handle_send_meter_reading function."""

    async def test_send_meter_reading_success(self, hass: HomeAssistant):
        """Test successful meter reading submission."""
        # Arrange
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Account",
            data={"name": "Test Account", CONF_API_TOKEN: "test-token"},
            entry_id="test-entry-id",
        )
        entry.add_to_hass(hass)
        await async_setup_entry(hass, entry)

        # Set up entity state
        hass.states.async_set(
            "sensor.energy_meter",
            "123.45",
            {"unit_of_measurement": "kWh"},
        )

        call = create_service_call(
            hass,
            DOMAIN,
            SERVICE_SEND_METER_READING,
            {
                "entry_id": "test-entry-id",
                "device_id": "device-123",
                "source_entity_id": "sensor.energy_meter",
                "allow_rounding": True,
            },
        )

        # Act
        with patch(
            "homeassistant.components.energy_tracker.EnergyTrackerApi.send_meter_reading",
            new_callable=AsyncMock,
        ) as mock_send:
            await async_handle_send_meter_reading(hass, call)

        # Assert
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["source_entity_id"] == "sensor.energy_meter"
        assert call_kwargs["device_id"] == "device-123"
        assert call_kwargs["value"] == 123.45
        assert call_kwargs["allow_rounding"] is True

    async def test_entity_not_found_raises_error(self, hass: HomeAssistant):
        """Test that non-existent entity raises localized error."""
        # Arrange
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Account",
            data={"name": "Test Account", CONF_API_TOKEN: "test-token"},
            entry_id="test-entry-id",
        )
        entry.add_to_hass(hass)
        await async_setup_entry(hass, entry)

        call = create_service_call(
            hass,
            DOMAIN,
            SERVICE_SEND_METER_READING,
            {
                "entry_id": "test-entry-id",
                "device_id": "device-123",
                "source_entity_id": "sensor.nonexistent",
                "allow_rounding": True,
            },
        )

        # Act & Assert
        with pytest.raises(HomeAssistantError) as exc_info:
            await async_handle_send_meter_reading(hass, call)

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "entity_not_found"
        assert (
            exc_info.value.translation_placeholders["entity_id"] == "sensor.nonexistent"
        )

    async def test_entity_unavailable_raises_error(self, hass: HomeAssistant):
        """Test that unavailable entity raises localized error."""
        # Arrange
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Account",
            data={"name": "Test Account", CONF_API_TOKEN: "test-token"},
            entry_id="test-entry-id",
        )
        entry.add_to_hass(hass)
        await async_setup_entry(hass, entry)

        hass.states.async_set("sensor.energy_meter", STATE_UNAVAILABLE)

        call = create_service_call(
            hass,
            DOMAIN,
            SERVICE_SEND_METER_READING,
            {
                "entry_id": "test-entry-id",
                "device_id": "device-123",
                "source_entity_id": "sensor.energy_meter",
                "allow_rounding": True,
            },
        )

        # Act & Assert
        with pytest.raises(HomeAssistantError) as exc_info:
            await async_handle_send_meter_reading(hass, call)

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "entity_unavailable"
        assert (
            exc_info.value.translation_placeholders["entity_id"]
            == "sensor.energy_meter"
        )
        assert exc_info.value.translation_placeholders["state"] == STATE_UNAVAILABLE

    async def test_entity_unknown_raises_error(self, hass: HomeAssistant):
        """Test that unknown entity state raises localized error."""
        # Arrange
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Account",
            data={"name": "Test Account", CONF_API_TOKEN: "test-token"},
            entry_id="test-entry-id",
        )
        entry.add_to_hass(hass)
        await async_setup_entry(hass, entry)

        hass.states.async_set("sensor.energy_meter", STATE_UNKNOWN)

        call = create_service_call(
            hass,
            DOMAIN,
            SERVICE_SEND_METER_READING,
            {
                "entry_id": "test-entry-id",
                "device_id": "device-123",
                "source_entity_id": "sensor.energy_meter",
                "allow_rounding": True,
            },
        )

        # Act & Assert
        with pytest.raises(HomeAssistantError) as exc_info:
            await async_handle_send_meter_reading(hass, call)

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "entity_unavailable"
        assert exc_info.value.translation_placeholders["state"] == STATE_UNKNOWN

    async def test_invalid_number_raises_error(self, hass: HomeAssistant):
        """Test that non-numeric entity state raises localized error."""
        # Arrange
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Account",
            data={"name": "Test Account", CONF_API_TOKEN: "test-token"},
            entry_id="test-entry-id",
        )
        entry.add_to_hass(hass)
        await async_setup_entry(hass, entry)

        hass.states.async_set("sensor.energy_meter", "not_a_number")

        call = create_service_call(
            hass,
            DOMAIN,
            SERVICE_SEND_METER_READING,
            {
                "entry_id": "test-entry-id",
                "device_id": "device-123",
                "source_entity_id": "sensor.energy_meter",
                "allow_rounding": True,
            },
        )

        # Act & Assert
        with pytest.raises(HomeAssistantError) as exc_info:
            await async_handle_send_meter_reading(hass, call)

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "invalid_number"
        assert (
            exc_info.value.translation_placeholders["entity_id"]
            == "sensor.energy_meter"
        )
        assert exc_info.value.translation_placeholders["state"] == "not_a_number"

    async def test_missing_timestamp_raises_error(self, hass: HomeAssistant):
        """Test that entity without timestamp raises localized error."""
        # Arrange
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Account",
            data={"name": "Test Account", CONF_API_TOKEN: "test-token"},
            entry_id="test-entry-id",
        )
        entry.add_to_hass(hass)
        await async_setup_entry(hass, entry)

        # Create state with None timestamp
        mock_state = MagicMock()
        mock_state.state = "123.45"
        mock_state.last_updated = None

        call = create_service_call(
            hass,
            DOMAIN,
            SERVICE_SEND_METER_READING,
            {
                "entry_id": "test-entry-id",
                "device_id": "device-123",
                "source_entity_id": "sensor.energy_meter",
                "allow_rounding": True,
            },
        )

        # Act & Assert
        # Patch the hass.states.get call at module level
        with (
            patch("homeassistant.core.StateMachine.get", return_value=mock_state),
            pytest.raises(HomeAssistantError) as exc_info,
        ):
            await async_handle_send_meter_reading(hass, call)

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "missing_timestamp"
        assert (
            exc_info.value.translation_placeholders["entity_id"]
            == "sensor.energy_meter"
        )

    async def test_no_api_token_raises_error(self, hass: HomeAssistant):
        """Test that missing API token raises localized error."""
        # Arrange
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Account",
            data={CONF_API_TOKEN: "valid-token"},
            entry_id="test-entry-id",
        )
        entry.add_to_hass(hass)
        await async_setup_entry(hass, entry)

        # Simulate runtime_data being empty/missing
        entry.runtime_data = ""

        hass.states.async_set("sensor.energy_meter", "123.45")

        call = create_service_call(
            hass,
            DOMAIN,
            SERVICE_SEND_METER_READING,
            {
                "entry_id": "test-entry-id",
                "device_id": "device-123",
                "source_entity_id": "sensor.energy_meter",
                "allow_rounding": True,
            },
        )

        # Act & Assert
        with pytest.raises(HomeAssistantError) as exc_info:
            await async_handle_send_meter_reading(hass, call)

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "no_api_token"

    async def test_deleted_integration_raises_error(self, hass: HomeAssistant):
        """Test that deleted integration entry raises localized error."""
        # Arrange
        hass.states.async_set("sensor.energy_meter", "123.45")

        call = create_service_call(
            hass,
            DOMAIN,
            SERVICE_SEND_METER_READING,
            {
                "entry_id": "nonexistent-entry-id",
                "device_id": "device-123",
                "source_entity_id": "sensor.energy_meter",
                "allow_rounding": True,
            },
        )

        # Act & Assert
        with pytest.raises(HomeAssistantError) as exc_info:
            await async_handle_send_meter_reading(hass, call)

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "no_api_token"

    async def test_device_id_whitespace_stripped(self, hass: HomeAssistant):
        """Test that device_id whitespace is properly stripped."""
        # Arrange
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Account",
            data={"name": "Test Account", CONF_API_TOKEN: "test-token"},
            entry_id="test-entry-id",
        )
        entry.add_to_hass(hass)
        await async_setup_entry(hass, entry)

        hass.states.async_set("sensor.energy_meter", "123.45")

        call = create_service_call(
            hass,
            DOMAIN,
            SERVICE_SEND_METER_READING,
            {
                "entry_id": "test-entry-id",
                "device_id": "  device-123  ",
                "source_entity_id": "sensor.energy_meter",
                "allow_rounding": True,
            },
        )

        # Act
        with patch(
            "homeassistant.components.energy_tracker.EnergyTrackerApi.send_meter_reading",
            new_callable=AsyncMock,
        ) as mock_send:
            await async_handle_send_meter_reading(hass, call)

        # Assert
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["device_id"] == "device-123"

    async def test_empty_entry_id_logs_debug(self, hass: HomeAssistant):
        """Test that empty entry_id logs debug message."""
        # Arrange
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Account",
            data={"name": "Test Account", CONF_API_TOKEN: "test-token"},
            entry_id="test-entry-id",
        )
        entry.add_to_hass(hass)
        await async_setup_entry(hass, entry)

        hass.states.async_set("sensor.energy_meter", "123.45")

        call = create_service_call(
            hass,
            DOMAIN,
            SERVICE_SEND_METER_READING,
            {
                "entry_id": "",  # Empty entry_id
                "device_id": "device-123",
                "source_entity_id": "sensor.energy_meter",
                "allow_rounding": True,
            },
        )

        # Act & Assert
        with pytest.raises(HomeAssistantError) as exc_info:
            await async_handle_send_meter_reading(hass, call)

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "no_api_token"

    async def test_deleted_entry_logs_debug(self, hass: HomeAssistant):
        """Test that deleted integration logs debug message."""
        # Arrange
        # Set up one entry, but try to use a different (deleted) one
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Account",
            data={"name": "Test Account", CONF_API_TOKEN: "test-token"},
            entry_id="existing-entry-id",
        )
        entry.add_to_hass(hass)
        await async_setup_entry(hass, entry)

        hass.states.async_set("sensor.energy_meter", "123.45")

        call = create_service_call(
            hass,
            DOMAIN,
            SERVICE_SEND_METER_READING,
            {
                "entry_id": "deleted-entry-id",  # Different entry that was deleted
                "device_id": "device-123",
                "source_entity_id": "sensor.energy_meter",
                "allow_rounding": True,
            },
        )

        # Act & Assert
        with pytest.raises(HomeAssistantError) as exc_info:
            await async_handle_send_meter_reading(hass, call)

        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "no_api_token"

    async def test_service_wrapper_function(self, hass: HomeAssistant):
        """Test that registered service wrapper calls handler correctly."""
        # Arrange
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Account",
            data={"name": "Test Account", CONF_API_TOKEN: "test-token"},
            entry_id="test-entry-id",
        )
        entry.add_to_hass(hass)
        await async_setup_entry(hass, entry)

        hass.states.async_set("sensor.energy_meter", "123.45")

        # Act
        with patch(
            "homeassistant.components.energy_tracker.EnergyTrackerApi.send_meter_reading",
            new_callable=AsyncMock,
        ) as mock_send:
            # Call via the registered service (which uses the wrapper)
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SEND_METER_READING,
                {
                    "entry_id": "test-entry-id",
                    "device_id": "device-123",
                    "source_entity_id": "sensor.energy_meter",
                    "allow_rounding": True,
                },
                blocking=True,
            )

        # Assert
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["device_id"] == "device-123"
        assert call_kwargs["value"] == 123.45
