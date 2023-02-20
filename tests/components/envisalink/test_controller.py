"""Test the Envisalink config flow."""

from functools import partial
from unittest.mock import patch

from homeassistant.components.envisalink.const import (
    CONF_PARTITION_SET,
    CONF_ZONE_SET,
    DOMAIN,
)
from homeassistant.components.envisalink.helpers import parse_range_string
from homeassistant.components.envisalink.pyenvisalink.alarm_panel import (
    EnvisalinkAlarmPanel,
)
from homeassistant.const import STATE_ALARM_DISARMED, STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant


def _validate_states(hass, controller, config_entry, should_be_available):
    zone_spec = config_entry.data.get(CONF_ZONE_SET)
    zone_set = parse_range_string(
        zone_spec, min_val=1, max_val=controller.controller.max_zones
    )

    partition_spec = config_entry.data.get(CONF_PARTITION_SET)
    partition_set = parse_range_string(
        partition_spec, min_val=1, max_val=controller.controller.max_partitions
    )

    if should_be_available:
        zone_state = STATE_OFF
        alarm_state = STATE_ALARM_DISARMED
        keypad_state = "N/A"
    else:
        zone_state = STATE_UNAVAILABLE
        alarm_state = STATE_UNAVAILABLE
        keypad_state = STATE_UNAVAILABLE

    for zone in zone_set:
        state = hass.states.get(f"binary_sensor.test_alarm_name_zone_{zone}")
        assert state
        assert state.state == zone_state

        state = hass.states.get(f"switch.test_alarm_name_zone_{zone}_bypass")
        assert state
        assert state.state == zone_state

    for partition in partition_set:
        state = hass.states.get(f"sensor.test_alarm_name_partition_{partition}_keypad")
        assert state
        assert state.state == keypad_state

        state = hass.states.get(
            f"alarm_control_panel.test_alarm_name_partition_{partition}"
        )
        assert state
        assert state.state == alarm_state


async def test_connection_errors(hass: HomeAssistant, init_integration) -> None:
    """Test connection failures to the Envisalink."""
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1

    config_entry = entries[0]
    controller = hass.data[DOMAIN][config_entry.entry_id]
    assert controller

    zone_spec = config_entry.data.get(CONF_ZONE_SET)
    parse_range_string(zone_spec, min_val=1, max_val=controller.controller.max_zones)

    _validate_states(hass, controller, config_entry, True)

    callbacks = [
        controller.async_login_fail_callback,
        controller.async_login_timeout_callback,
        partial(controller.async_connection_status_callback, False),
    ]

    for callback in callbacks:
        with patch.object(
            EnvisalinkAlarmPanel, "is_online", autospec=True, return_value=False
        ):
            # Simulate a lost connection
            callback()
            await hass.async_block_till_done()

        _validate_states(hass, controller, config_entry, False)

        with patch.object(
            EnvisalinkAlarmPanel, "is_online", autospec=True, return_value=True
        ):
            # Simulate connection restored
            controller.async_connection_status_callback(True)
            controller.async_login_success_callback()
            await hass.async_block_till_done()

        _validate_states(hass, controller, config_entry, True)
