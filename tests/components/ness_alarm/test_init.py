"""Tests for the ness_alarm component."""

from types import MappingProxyType
from unittest.mock import AsyncMock, patch

from nessclient import ArmingMode, ArmingState

from homeassistant.components import alarm_control_panel
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.ness_alarm.const import (
    ATTR_OUTPUT_ID,
    CONF_SHOW_HOME_MODE,
    CONF_ZONE_NUMBER,
    DOMAIN,
    SERVICE_AUX,
    SERVICE_PANIC,
    SUBENTRY_TYPE_ZONE,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    ATTR_STATE,
    CONF_HOST,
    CONF_PORT,
    CONF_TYPE,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_config_entry_setup(hass: HomeAssistant, mock_nessclient) -> None:
    """Test config entry setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Services should be registered
    assert hass.services.has_service(DOMAIN, SERVICE_PANIC)
    assert hass.services.has_service(DOMAIN, SERVICE_AUX)

    # Alarm panel should be created
    assert hass.states.get("alarm_control_panel.alarm_panel")

    # Client keepalive and update should be called after startup
    assert mock_nessclient.keepalive.call_count == 1
    # update is called once during setup (connection test) and once after startup
    assert mock_nessclient.update.call_count == 2


async def test_config_entry_unload(hass: HomeAssistant, mock_nessclient) -> None:
    """Test config entry unload."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Client should be closed
    mock_nessclient.close.assert_called_once()


async def test_config_entry_not_ready(hass: HomeAssistant, mock_nessclient) -> None:
    """Test config entry raises ConfigEntryNotReady on connection failure."""
    mock_nessclient.update.side_effect = OSError("Connection refused")

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_nessclient.close.assert_called_once()


async def test_config_entry_with_zones(hass: HomeAssistant, mock_nessclient) -> None:
    """Test config entry setup with zones as subentries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)

    # Add zone subentries
    entry.subentries = {
        "zone_1_id": ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_ZONE,
            subentry_id="zone_1_id",
            unique_id="zone_1",
            title="Zone 1",
            data={
                CONF_ZONE_NUMBER: 1,
                CONF_TYPE: BinarySensorDeviceClass.MOTION,
            },
        ),
        "zone_2_id": ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_ZONE,
            subentry_id="zone_2_id",
            unique_id="zone_2",
            title="Zone 2",
            data={
                CONF_ZONE_NUMBER: 2,
                CONF_TYPE: BinarySensorDeviceClass.DOOR,
            },
        ),
    }

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Binary sensors should be created for each zone
    assert hass.states.get("binary_sensor.zone_1")
    assert hass.states.get("binary_sensor.zone_2")


async def test_config_entry_reload_on_subentry_add(
    hass: HomeAssistant, mock_nessclient
) -> None:
    """Test config entry with subentries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)

    # Add a zone subentry
    entry.subentries = {
        "zone_1_id": ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_ZONE,
            subentry_id="zone_1_id",
            unique_id="zone_1",
            title="Zone 1",
            data={
                CONF_ZONE_NUMBER: 1,
                CONF_TYPE: BinarySensorDeviceClass.MOTION,
            },
        ),
    }

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Zone entity should be created
    assert hass.states.get("binary_sensor.zone_1")


async def test_panic_service_with_config_entry(
    hass: HomeAssistant, mock_nessclient
) -> None:
    """Test calling panic service with config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN, SERVICE_PANIC, blocking=True, service_data={ATTR_CODE: "1234"}
    )
    mock_nessclient.panic.assert_awaited_once_with("1234")


async def test_aux_service_with_config_entry(
    hass: HomeAssistant, mock_nessclient
) -> None:
    """Test calling aux service with config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN, SERVICE_AUX, blocking=True, service_data={ATTR_OUTPUT_ID: 1}
    )
    mock_nessclient.aux.assert_awaited_once_with(1, True)


async def test_aux_service_with_state_false(
    hass: HomeAssistant, mock_nessclient
) -> None:
    """Test calling aux service with state=False."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_AUX,
        blocking=True,
        service_data={ATTR_OUTPUT_ID: 2, ATTR_STATE: False},
    )
    mock_nessclient.aux.assert_awaited_once_with(2, False)


async def test_alarm_panel_disarm(hass: HomeAssistant, mock_nessclient) -> None:
    """Test alarm panel disarm."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
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


async def test_alarm_panel_arm_away(hass: HomeAssistant, mock_nessclient) -> None:
    """Test alarm panel arm away."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
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


async def test_alarm_panel_arm_home(hass: HomeAssistant, mock_nessclient) -> None:
    """Test alarm panel arm home."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
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


async def test_alarm_panel_trigger(hass: HomeAssistant, mock_nessclient) -> None:
    """Test alarm panel trigger."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
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


async def test_zone_state_change(hass: HomeAssistant, mock_nessclient) -> None:
    """Test zone state change events."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)

    # Add zone subentries
    entry.subentries = {
        "zone_1_id": ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_ZONE,
            subentry_id="zone_1_id",
            unique_id="zone_1",
            title="Zone 1",
            data={
                CONF_ZONE_NUMBER: 1,
                CONF_TYPE: BinarySensorDeviceClass.MOTION,
            },
        ),
        "zone_2_id": ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_ZONE,
            subentry_id="zone_2_id",
            unique_id="zone_2",
            title="Zone 2",
            data={
                CONF_ZONE_NUMBER: 2,
                CONF_TYPE: BinarySensorDeviceClass.DOOR,
            },
        ),
    }

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get the zone change callback
    on_zone_change = mock_nessclient.on_zone_change.call_args[0][0]

    # Trigger zone 1
    on_zone_change(1, True)
    await hass.async_block_till_done()
    assert hass.states.is_state("binary_sensor.zone_1", "on")

    # Trigger zone 2
    on_zone_change(2, True)
    await hass.async_block_till_done()
    assert hass.states.is_state("binary_sensor.zone_2", "on")

    # Clear zone 1
    on_zone_change(1, False)
    await hass.async_block_till_done()
    assert hass.states.is_state("binary_sensor.zone_1", "off")


async def test_arming_state_changes(hass: HomeAssistant, mock_nessclient) -> None:
    """Test all arming state changes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get the state change callback
    on_state_change = mock_nessclient.on_state_change.call_args[0][0]

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
        (
            ArmingState.ARMED,
            ArmingMode.ARMED_VACATION,
            AlarmControlPanelState.ARMED_VACATION,
        ),
        (
            ArmingState.ARMED,
            ArmingMode.ARMED_DAY,
            AlarmControlPanelState.ARMED_AWAY,
        ),
        (
            ArmingState.ARMED,
            ArmingMode.ARMED_HIGHEST,
            AlarmControlPanelState.ARMED_AWAY,
        ),
        (ArmingState.ENTRY_DELAY, None, AlarmControlPanelState.PENDING),
        (ArmingState.TRIGGERED, None, AlarmControlPanelState.TRIGGERED),
    ]

    for arming_state, arming_mode, expected_state in states:
        on_state_change(arming_state, arming_mode)
        await hass.async_block_till_done()
        assert hass.states.is_state("alarm_control_panel.alarm_panel", expected_state)


async def test_arming_state_unknown_mode(hass: HomeAssistant, mock_nessclient) -> None:
    """Test arming state with unknown arming mode (for coverage)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Get the state change callback
    on_state_change = mock_nessclient.on_state_change.call_args[0][0]

    # Test with unhandled arming state (for coverage of warning log)
    on_state_change(999, None)  # Invalid state
    await hass.async_block_till_done()


async def test_homeassistant_stop_event(hass: HomeAssistant, mock_nessclient) -> None:
    """Test client is closed on homeassistant_stop event."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Fire the homeassistant_stop event
    hass.bus.async_fire("homeassistant_stop")
    await hass.async_block_till_done()

    # Client should be closed
    mock_nessclient.close.assert_called()


async def test_entry_reload_on_update(hass: HomeAssistant, mock_nessclient) -> None:
    """Test config entry reload when update listener is triggered."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Add a zone subentry which should trigger the update listener and reload
    zone_subentry = ConfigSubentry(
        subentry_type=SUBENTRY_TYPE_ZONE,
        subentry_id="zone_1_id",
        unique_id="zone_1",
        title="Zone 1",
        data=MappingProxyType(
            {
                CONF_ZONE_NUMBER: 1,
                CONF_TYPE: BinarySensorDeviceClass.MOTION,
            }
        ),
    )
    hass.config_entries.async_add_subentry(entry, zone_subentry)
    await hass.async_block_till_done()

    # Entry should have the new zone subentry
    assert len(entry.subentries) == 1


async def test_alarm_panel_home_mode_disabled(
    hass: HomeAssistant, mock_nessclient
) -> None:
    """Test alarm panel with home mode disabled via options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
        options={CONF_SHOW_HOME_MODE: False},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state is not None

    # ARM_HOME should not be in supported features
    supported = state.attributes["supported_features"]
    assert not supported & AlarmControlPanelEntityFeature.ARM_HOME
    assert supported & AlarmControlPanelEntityFeature.ARM_AWAY
    assert supported & AlarmControlPanelEntityFeature.TRIGGER


async def test_alarm_panel_home_mode_enabled_by_default(
    hass: HomeAssistant, mock_nessclient
) -> None:
    """Test alarm panel has home mode enabled by default."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1992,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.alarm_panel")
    assert state is not None

    # ARM_HOME should be in supported features by default
    supported = state.attributes["supported_features"]
    assert supported & AlarmControlPanelEntityFeature.ARM_HOME
    assert supported & AlarmControlPanelEntityFeature.ARM_AWAY
    assert supported & AlarmControlPanelEntityFeature.TRIGGER


async def test_yaml_import_triggers_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, issue_registry: ir.IssueRegistry
) -> None:
    """Test that YAML configuration triggers import flow."""
    with patch(
        "homeassistant.components.ness_alarm.config_flow.Client",
        return_value=AsyncMock(),
    ):
        config = {
            DOMAIN: {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 1992,
            }
        }
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        # Check that a config entry was created from the import
        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
        assert entries[0].data[CONF_HOST] == "192.168.1.100"
        assert entries[0].data[CONF_PORT] == 1992

        # Check that a deprecation repair issue was created
        issue = issue_registry.async_get_issue(
            "homeassistant", f"deprecated_yaml_{DOMAIN}"
        )
        assert issue is not None
        assert issue.severity == "warning"
