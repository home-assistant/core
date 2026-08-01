"""Test switch platform for IntelliDwell Sprinkler Controller."""

from unittest.mock import AsyncMock, patch

from pyintellidwell import IntelliDwellConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.intellidwell.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_switches(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test switch setup and operations."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1"},
        entry_id="mock_entry",
    )
    entry.add_to_hass(hass)

    status_data = {
        "relay_states": [0, 1, 0, 0, 0, 0, 0, 0, 0, 0],
        "timers": {},
        "queue": {},
    }

    with (
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_status",
            return_value=status_data,
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_rain_delay",
            return_value={"days_remaining": 0},
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_schedules",
            return_value=[{"enabled": True}, {"enabled": False}],
            new_callable=AsyncMock,
            create=True,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entity_registry.async_is_registered(
            "switch.intellidwell_sprinkler_controller_zone_1"
        )
        assert entity_registry.async_is_registered(
            "switch.intellidwell_sprinkler_controller_zone_2"
        )
        assert entity_registry.async_is_registered(
            "switch.intellidwell_sprinkler_controller_zone_1_schedule"
        )
        assert entity_registry.async_is_registered(
            "switch.intellidwell_sprinkler_controller_zone_2_schedule"
        )

        state1 = hass.states.get("switch.intellidwell_sprinkler_controller_zone_1")
        assert state1.state == "off"

        state2 = hass.states.get("switch.intellidwell_sprinkler_controller_zone_2")
        assert state2.state == "on"

        sched_state1 = hass.states.get(
            "switch.intellidwell_sprinkler_controller_zone_1_schedule"
        )
        assert sched_state1.state == "on"

        sched_state2 = hass.states.get(
            "switch.intellidwell_sprinkler_controller_zone_2_schedule"
        )
        assert sched_state2.state == "off"

        with patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.set_relay",
            new_callable=AsyncMock,
            create=True,
        ) as mock_set_relay:
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: "switch.intellidwell_sprinkler_controller_zone_1"},
                blocking=True,
            )
            mock_set_relay.assert_called_once_with(0, "on")

        with patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.set_relay",
            new_callable=AsyncMock,
            create=True,
        ) as mock_set_relay:
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: "switch.intellidwell_sprinkler_controller_zone_2"},
                blocking=True,
            )
            mock_set_relay.assert_called_once_with(1, "off")

        with patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.set_schedule_enabled",
            new_callable=AsyncMock,
            create=True,
        ) as mock_set_sched:
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_OFF,
                {
                    ATTR_ENTITY_ID: (
                        "switch.intellidwell_sprinkler_controller_zone_1_schedule"
                    )
                },
                blocking=True,
            )
            mock_set_sched.assert_called_once_with(0, False)

        with patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.set_schedule_enabled",
            new_callable=AsyncMock,
            create=True,
        ) as mock_set_sched:
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: (
                        "switch.intellidwell_sprinkler_controller_zone_2_schedule"
                    )
                },
                blocking=True,
            )
            mock_set_sched.assert_called_once_with(1, True)


async def test_switch_setup_failure(hass: HomeAssistant) -> None:
    """Test switch platform setup fails when the coordinator cannot connect initially."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1"},
        entry_id="mock_entry",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_status",
            side_effect=IntelliDwellConnectionError,
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_rain_delay",
            return_value={"days_remaining": 0},
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_schedules",
            return_value=[],
            new_callable=AsyncMock,
            create=True,
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state == config_entries.ConfigEntryState.SETUP_RETRY


async def _setup_entry(hass: HomeAssistant) -> None:
    """Helper: set up a working IntelliDwell config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1"},
        entry_id="mock_entry_cmd",
    )
    entry.add_to_hass(hass)

    status_data = {
        "relay_states": [0] * 10,
        "timers": {},
        "queue": {},
    }
    with (
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_status",
            return_value=status_data,
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_rain_delay",
            return_value={"days_remaining": 0},
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_schedules",
            return_value=[],
            new_callable=AsyncMock,
            create=True,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_turn_on_connection_error(hass: HomeAssistant) -> None:
    """Test that turn_on raises HomeAssistantError on IntelliDwellConnectionError."""
    await _setup_entry(hass)

    with (
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_status",
            return_value={"relay_states": [0] * 10},
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_rain_delay",
            return_value={"days_remaining": 0},
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_schedules",
            return_value=[],
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.set_relay",
            side_effect=IntelliDwellConnectionError("timeout"),
            new_callable=AsyncMock,
            create=True,
        ),
        pytest.raises(HomeAssistantError, match="Error turning on zone 1"),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.intellidwell_sprinkler_controller_zone_1"},
            blocking=True,
        )


async def test_turn_off_connection_error(hass: HomeAssistant) -> None:
    """Test that turn_off raises HomeAssistantError on IntelliDwellConnectionError."""
    await _setup_entry(hass)

    with (
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_status",
            return_value={"relay_states": [0] * 10},
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_rain_delay",
            return_value={"days_remaining": 0},
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_schedules",
            return_value=[],
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.set_relay",
            side_effect=IntelliDwellConnectionError("timeout"),
            new_callable=AsyncMock,
            create=True,
        ),
        pytest.raises(HomeAssistantError, match="Error turning off zone 1"),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.intellidwell_sprinkler_controller_zone_1"},
            blocking=True,
        )


async def test_schedule_switch_connection_errors(hass: HomeAssistant) -> None:
    """Test that schedule switch turn_on and turn_off raise HomeAssistantError on error."""
    await _setup_entry(hass)

    with (
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_status",
            return_value={"relay_states": [0] * 10},
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_rain_delay",
            return_value={"days_remaining": 0},
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_schedules",
            return_value=[],
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.set_schedule_enabled",
            side_effect=IntelliDwellConnectionError("timeout"),
            new_callable=AsyncMock,
            create=True,
        ),
        pytest.raises(HomeAssistantError, match="Error enabling schedule for zone 1"),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: (
                    "switch.intellidwell_sprinkler_controller_zone_1_schedule"
                )
            },
            blocking=True,
        )

    with (
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_status",
            return_value={"relay_states": [0] * 10},
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_rain_delay",
            return_value={"days_remaining": 0},
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_schedules",
            return_value=[],
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.set_schedule_enabled",
            side_effect=IntelliDwellConnectionError("timeout"),
            new_callable=AsyncMock,
            create=True,
        ),
        pytest.raises(HomeAssistantError, match="Error disabling schedule for zone 1"),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: (
                    "switch.intellidwell_sprinkler_controller_zone_1_schedule"
                )
            },
            blocking=True,
        )
