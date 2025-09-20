"""Tests for the ness_alarm component."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from nessclient import ArmingMode, ArmingState
import pytest
import voluptuous as vol

from homeassistant.components import alarm_control_panel
from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.ness_alarm import (
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONFIG_SCHEMA,
    async_setup_services,
    config_flow,
    update_listener,
)
from homeassistant.components.ness_alarm.const import (
    ATTR_OUTPUT_ID,
    CONF_DEVICE_PORT,
    CONF_INFER_ARMING_STATE,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONES,
    DOMAIN,
    SERVICE_AUX,
    SERVICE_PANIC,
)
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    CONF_HOST,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

VALID_CONFIG = {
    DOMAIN: {
        CONF_HOST: "alarm.local",
        CONF_DEVICE_PORT: 1234,
        CONF_ZONES: [
            {CONF_ZONE_NAME: "Zone 1", CONF_ZONE_ID: 1},
            {CONF_ZONE_NAME: "Zone 2", CONF_ZONE_ID: 2},
        ],
    }
}


@pytest.fixture(autouse=True)
def mock_validate_input(monkeypatch: pytest.MonkeyPatch):
    """Patch validate_input to avoid real network calls."""

    async def _mock_validate_input(hass: HomeAssistant | None, data: dict) -> dict:
        return {
            "model": "D8X",
            "version": "8.7",
            "title": "Ness Alarm (mock)",
            "address": "01",
        }

    monkeypatch.setattr(config_flow, "validate_input", _mock_validate_input)


async def test_setup_platform(hass: HomeAssistant, mock_nessclient) -> None:
    """Test platform setup."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    assert hass.services.has_service(DOMAIN, "panic")
    assert hass.services.has_service(DOMAIN, "aux")

    await hass.async_block_till_done()
    assert hass.states.get("alarm_control_panel.alarm_panel") is not None
    assert hass.states.get("binary_sensor.zone_1") is not None
    assert hass.states.get("binary_sensor.zone_2") is not None

    assert mock_nessclient.keepalive.call_count == 1
    assert mock_nessclient.update.call_count == 1


async def test_panic_service(hass: HomeAssistant, mock_nessclient) -> None:
    """Test calling panic service."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.services.async_call(
        DOMAIN, SERVICE_PANIC, blocking=True, service_data={ATTR_CODE: "1234"}
    )
    mock_nessclient.panic.assert_awaited_once_with("1234")


async def test_aux_service(hass: HomeAssistant, mock_nessclient) -> None:
    """Test calling aux service."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.services.async_call(
        DOMAIN, SERVICE_AUX, blocking=True, service_data={ATTR_OUTPUT_ID: 1}
    )
    mock_nessclient.aux.assert_awaited_once_with(1, True)


async def test_dispatch_state_change(hass: HomeAssistant, mock_nessclient) -> None:
    """Test state change callback dispatch."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    on_state_change = mock_nessclient.on_state_change.call_args[0][0]
    on_state_change(ArmingState.ARMING, None)

    await hass.async_block_till_done()
    assert hass.states.is_state(
        "alarm_control_panel.alarm_panel", AlarmControlPanelState.ARMING
    )


async def test_alarm_disarm(hass: HomeAssistant, mock_nessclient) -> None:
    """Test disarm service call."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    await hass.services.async_call(
        alarm_control_panel.DOMAIN,
        SERVICE_ALARM_DISARM,
        blocking=True,
        service_data={
            ATTR_ENTITY_ID: "alarm_control_panel.alarm_panel",
            ATTR_CODE: "1234",
        },
    )
    mock_nessclient.disarm.assert_called_once_with("1234")


async def test_alarm_arm_away(hass: HomeAssistant, mock_nessclient) -> None:
    """Test arm_away service call."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    await hass.services.async_call(
        alarm_control_panel.DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        blocking=True,
        service_data={
            ATTR_ENTITY_ID: "alarm_control_panel.alarm_panel",
            ATTR_CODE: "1234",
        },
    )
    mock_nessclient.arm_away.assert_called_once_with("1234")


async def test_alarm_arm_home(hass: HomeAssistant, mock_nessclient) -> None:
    """Test arm_home service call."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    await hass.services.async_call(
        alarm_control_panel.DOMAIN,
        SERVICE_ALARM_ARM_HOME,
        blocking=True,
        service_data={
            ATTR_ENTITY_ID: "alarm_control_panel.alarm_panel",
            ATTR_CODE: "1234",
        },
    )
    mock_nessclient.arm_home.assert_called_once_with("1234")


async def test_alarm_trigger(hass: HomeAssistant, mock_nessclient) -> None:
    """Test alarm_trigger service call (maps to panic)."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    await hass.services.async_call(
        alarm_control_panel.DOMAIN,
        SERVICE_ALARM_TRIGGER,
        blocking=True,
        service_data={
            ATTR_ENTITY_ID: "alarm_control_panel.alarm_panel",
            ATTR_CODE: "1234",
        },
    )
    mock_nessclient.panic.assert_called_once_with("1234")


async def test_dispatch_zone_change(hass: HomeAssistant, mock_nessclient) -> None:
    """Test zone change callback dispatch."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    on_zone_change = mock_nessclient.on_zone_change.call_args[0][0]
    on_zone_change(1, True)

    await hass.async_block_till_done()
    assert hass.states.is_state("binary_sensor.zone_1", "on")
    assert hass.states.is_state("binary_sensor.zone_2", "off")


async def test_arming_state_change(hass: HomeAssistant, mock_nessclient) -> None:
    """Test arming state change handling."""
    states = [
        (ArmingState.UNKNOWN, None, STATE_UNKNOWN),
        (ArmingState.DISARMED, None, AlarmControlPanelState.DISARMED),
        (ArmingState.ARMING, None, AlarmControlPanelState.ARMING),
        (ArmingState.EXIT_DELAY, None, AlarmControlPanelState.ARMING),
        (ArmingState.ARMED, None, AlarmControlPanelState.ARMED_AWAY),
        (
            ArmingState.ARMED,
            ArmingMode.ARMED_AWAY,
            AlarmControlPanelState.ARMED_AWAY,
        ),
        (
            ArmingState.ARMED,
            ArmingMode.ARMED_HOME,
            AlarmControlPanelState.ARMED_HOME,
        ),
        (
            ArmingState.ARMED,
            ArmingMode.ARMED_NIGHT,
            AlarmControlPanelState.ARMED_NIGHT,
        ),
        (ArmingState.ENTRY_DELAY, None, AlarmControlPanelState.PENDING),
        (ArmingState.TRIGGERED, None, AlarmControlPanelState.TRIGGERED),
    ]

    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()
    assert hass.states.is_state("alarm_control_panel.alarm_panel", STATE_UNKNOWN)
    on_state_change = mock_nessclient.on_state_change.call_args[0][0]

    for arming_state, arming_mode, expected_state in states:
        on_state_change(arming_state, arming_mode)
        await hass.async_block_till_done()
        assert hass.states.is_state("alarm_control_panel.alarm_panel", expected_state)


class MockClient:
    """Mock nessclient.Client stub."""

    async def panic(self, code):
        """Handle panic."""

    async def disarm(self, code):
        """Handle disarm."""

    async def arm_away(self, code):
        """Handle arm_away."""

    async def arm_home(self, code):
        """Handle arm_home."""

    async def aux(self, output_id, state):
        """Handle auxiliary control."""

    async def keepalive(self):
        """Handle keepalive."""

    async def update(self):
        """Handle update."""

    def on_zone_change(self):
        """Handle on_zone_change."""

    def on_state_change(self):
        """Handle on_state_change."""

    async def close(self):
        """Handle close."""


@pytest.fixture
def mock_nessclient():
    """Mock the nessclient Client constructor.

    Replaces nessclient.Client with a Mock which always returns the same
    MagicMock() instance.
    """
    _mock_instance = MagicMock(MockClient())
    _mock_factory = MagicMock()
    _mock_factory.return_value = _mock_instance

    with patch(
        "homeassistant.components.ness_alarm.Client", new=_mock_factory, create=True
    ):
        yield _mock_instance


async def test_invalid_yaml_config(hass: HomeAssistant) -> None:
    """Test setup fails with invalid YAML configuration."""
    # Missing required host
    invalid_config = {
        DOMAIN: {
            CONF_DEVICE_PORT: 1234,
            CONF_ZONES: [
                {CONF_ZONE_NAME: "Zone 1", CONF_ZONE_ID: 1},
            ],
        }
    }

    with patch(
        "homeassistant.components.ness_alarm.config_flow.NessConfigFlow.async_step_import",
        side_effect=Exception("Invalid config"),
    ):
        result = await async_setup_component(hass, DOMAIN, invalid_config)
        assert result is False  # Component setup returns True but import will fail

        # Verify that no entities were created
        await hass.async_block_till_done()
        assert hass.states.get("alarm_control_panel.alarm_panel") is None
        assert hass.states.get("binary_sensor.zone_1") is None


async def test_invalid_zone_config(hass: HomeAssistant) -> None:
    """Test setup with invalid zone configuration."""
    # Zone with invalid ID (negative)
    invalid_config = {
        DOMAIN: {
            CONF_HOST: "alarm.local",
            CONF_DEVICE_PORT: 1234,
            CONF_ZONES: [
                {CONF_ZONE_NAME: "Invalid Zone", CONF_ZONE_ID: -1},
                {CONF_ZONE_NAME: "Valid Zone", CONF_ZONE_ID: 1},
            ],
        }
    }

    with pytest.raises(vol.Invalid):
        CONFIG_SCHEMA(invalid_config)  # Only this line inside

    # Zone with duplicate IDs
    duplicate_config = {
        DOMAIN: {
            CONF_HOST: "alarm.local",
            CONF_DEVICE_PORT: 1234,
            CONF_ZONES: [
                {CONF_ZONE_NAME: "Zone 1", CONF_ZONE_ID: 1},
                {CONF_ZONE_NAME: "Zone 1 Duplicate", CONF_ZONE_ID: 1},
            ],
        }
    }

    # This should be allowed by schema but handled during setup
    validated = CONFIG_SCHEMA(duplicate_config)
    assert len(validated[DOMAIN][CONF_ZONES]) == 2


async def test_invalid_port_in_yaml(hass: HomeAssistant) -> None:
    """Test YAML config with invalid port values."""
    # Port too high
    invalid_config = {
        DOMAIN: {
            CONF_HOST: "alarm.local",
            CONF_DEVICE_PORT: 70000,  # > 65535
            CONF_ZONES: [],
        }
    }

    with pytest.raises(vol.Invalid):
        CONFIG_SCHEMA(invalid_config)

    # Negative port
    negative_port_config = {
        DOMAIN: {
            CONF_HOST: "alarm.local",
            CONF_DEVICE_PORT: -1,
            CONF_ZONES: [],
        }
    }

    with pytest.raises(vol.Invalid):
        CONFIG_SCHEMA(negative_port_config)

    # Port as string (invalid type)
    string_port_config = {
        DOMAIN: {
            CONF_HOST: "alarm.local",
            CONF_DEVICE_PORT: "not_a_port",
            CONF_ZONES: [],
        }
    }

    with pytest.raises(vol.Invalid):
        CONFIG_SCHEMA(string_port_config)


async def test_invalid_infer_arming_state(hass: HomeAssistant) -> None:
    """Test YAML config with invalid infer_arming_state value."""
    invalid_config = {
        DOMAIN: {
            CONF_HOST: "alarm.local",
            CONF_DEVICE_PORT: 1234,
            CONF_INFER_ARMING_STATE: "not_a_boolean",
            CONF_ZONES: [],
        }
    }

    with pytest.raises(vol.Invalid):
        CONFIG_SCHEMA(invalid_config)

    # Test with numeric value (should be converted to boolean)
    numeric_config = {
        DOMAIN: {
            CONF_HOST: "alarm.local",
            CONF_DEVICE_PORT: 1234,
            CONF_INFER_ARMING_STATE: 1,
            CONF_ZONES: [],
        }
    }

    validated = CONFIG_SCHEMA(numeric_config)
    assert validated[DOMAIN][CONF_INFER_ARMING_STATE] is True


async def test_zone_missing_required_fields(hass: HomeAssistant) -> None:
    """Test zone configuration with missing required fields."""
    # Zone missing ID
    missing_id_config = {
        DOMAIN: {
            CONF_HOST: "alarm.local",
            CONF_DEVICE_PORT: 1234,
            CONF_ZONES: [
                {CONF_ZONE_NAME: "Zone without ID"},
            ],
        }
    }

    with pytest.raises(vol.Invalid):
        CONFIG_SCHEMA(missing_id_config)

    # Zone missing name
    missing_name_config = {
        DOMAIN: {
            CONF_HOST: "alarm.local",
            CONF_DEVICE_PORT: 1234,
            CONF_ZONES: [
                {CONF_ZONE_ID: 1},
            ],
        }
    }

    with pytest.raises(vol.Invalid):
        CONFIG_SCHEMA(missing_name_config)


async def test_empty_host_string(hass: HomeAssistant) -> None:
    """Test YAML config with empty host string."""
    empty_host_config = {
        DOMAIN: {
            CONF_HOST: "",
            CONF_DEVICE_PORT: 1234,
            CONF_ZONES: [],
        }
    }

    # Empty string should pass schema validation but fail during connection
    validated = CONFIG_SCHEMA(empty_host_config)
    assert validated[DOMAIN][CONF_HOST] == ""


async def test_services_not_registered_without_setup(hass: HomeAssistant) -> None:
    """Test that services are not registered without proper setup."""
    # Verify services don't exist before setup
    assert not hass.services.has_service(DOMAIN, SERVICE_PANIC)
    assert not hass.services.has_service(DOMAIN, SERVICE_AUX)

    # After failed setup, services should still not exist
    invalid_config = {
        DOMAIN: {
            CONF_DEVICE_PORT: 1234,  # Missing host
        }
    }

    with patch(
        "homeassistant.components.ness_alarm.config_flow.NessConfigFlow.async_step_import",
        side_effect=Exception("Invalid config"),
    ):
        await async_setup_component(hass, DOMAIN, invalid_config)
        await hass.async_block_till_done()

        assert not hass.services.has_service(DOMAIN, SERVICE_PANIC)
        assert not hass.services.has_service(DOMAIN, SERVICE_AUX)


async def test_panic_service_without_code(hass: HomeAssistant, mock_nessclient) -> None:
    """Test calling panic service without providing a code."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)

    # Call panic without code parameter
    await hass.services.async_call(
        DOMAIN, SERVICE_PANIC, blocking=True, service_data={}
    )

    # Should be called with None as code
    mock_nessclient.panic.assert_awaited_once_with(None)


async def test_setup_with_timedelta_scan_interval(
    hass: HomeAssistant, mock_nessclient
) -> None:
    """Test setup with timedelta object for scan_interval."""

    config = {
        DOMAIN: {
            CONF_HOST: "alarm.local",
            CONF_DEVICE_PORT: 1234,
            CONF_SCAN_INTERVAL: timedelta(seconds=30),
            CONF_ZONES: [],
        }
    }

    # This should be properly handled by the schema
    validated = CONFIG_SCHEMA(config)
    assert isinstance(validated[DOMAIN][CONF_SCAN_INTERVAL], timedelta)
    assert validated[DOMAIN][CONF_SCAN_INTERVAL].total_seconds() == 30


async def test_services_already_registered(
    hass: HomeAssistant, mock_nessclient
) -> None:
    """Test that services are not re-registered if already present."""
    # First setup
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_PANIC)
    assert hass.services.has_service(DOMAIN, SERVICE_AUX)

    # Since services are already registered, calling setup again should return early
    # We'll verify this by checking that no exception is raised and services still exist
    await async_setup_services(hass)

    # Services should still exist and work
    assert hass.services.has_service(DOMAIN, SERVICE_PANIC)
    assert hass.services.has_service(DOMAIN, SERVICE_AUX)


async def test_update_listener_reloads_entry(
    hass: HomeAssistant,
) -> None:
    """Test that update listener reloads the config entry."""

    # Create a mock config entry
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
        },
    )
    mock_entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_reload") as mock_reload:
        await update_listener(hass, mock_entry)
        mock_reload.assert_called_once_with(mock_entry.entry_id)


async def test_shutdown_handler(
    hass: HomeAssistant,
    mock_nessclient,
) -> None:
    """Test that shutdown handler closes the client."""
    await async_setup_component(hass, DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    # Clear any previous calls
    mock_nessclient.close.reset_mock()

    # Simulate Home Assistant stopping
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    # Client should have been closed
    mock_nessclient.close.assert_called()


async def test_shutdown_handler_via_config_entry(
    hass: HomeAssistant,
) -> None:
    """Test shutdown handler via config entry setup."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 2401,
        },
    )
    mock_config_entry.add_to_hass(hass)

    mock_client = AsyncMock()
    mock_client.keepalive = AsyncMock()
    mock_client.update = AsyncMock()
    mock_client.close = AsyncMock()
    mock_client.on_zone_change = MagicMock()
    mock_client.on_state_change = MagicMock()

    with patch(
        "homeassistant.components.ness_alarm.Client",
        return_value=mock_client,
    ):
        # Setup the entry
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Clear any setup calls
        mock_client.close.reset_mock()

        # Fire the stop event
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

        # Client should be closed
        mock_client.close.assert_called_once()
