"""Tests Starlink switches."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from starlink_grpc import GrpcError

from homeassistant.components.starlink.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_IP_ADDRESS,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import JsonArrayType

from .patchers import (
    HISTORY_STATS_SUCCESS_PATCHER,
    LOCATION_DATA_SUCCESS_PATCHER,
    SLEEP_DATA_SUCCESS_PATCHER,
    STATUS_DATA_FIXTURE,
    STATUS_DATA_TARGET,
)

from tests.common import MockConfigEntry

ENTITY_ID = "switch.starlink_use_starlink_positioning_exclusively"
SET_GPS_CONFIG_TARGET = "homeassistant.components.starlink.coordinator.set_gps_config"


async def setup_integration(
    hass: HomeAssistant, status_data: JsonArrayType
) -> MockConfigEntry:
    """Set up the Starlink integration with the given status data."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP_ADDRESS: "1.2.3.4:0000"})

    with (
        LOCATION_DATA_SUCCESS_PATCHER,
        SLEEP_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
        patch(STATUS_DATA_TARGET, return_value=status_data),
    ):
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


@pytest.mark.parametrize(
    ("gps_enabled", "expected_state"),
    [
        (True, STATE_OFF),
        (False, STATE_ON),
        (None, STATE_UNKNOWN),
    ],
)
async def test_starlink_positioning_exclusive_state(
    hass: HomeAssistant, gps_enabled: bool | None, expected_state: str
) -> None:
    """Test the switch is on when the dish does not use GPS."""
    status_data = deepcopy(STATUS_DATA_FIXTURE)
    status_data[0]["gps_enabled"] = gps_enabled

    await setup_integration(hass, status_data)

    assert hass.states.get(ENTITY_ID).state == expected_state


async def test_starlink_positioning_exclusive_not_reported(
    hass: HomeAssistant,
) -> None:
    """Test the switch is unknown when the dish omits the GPS state."""
    status_data = deepcopy(STATUS_DATA_FIXTURE)
    del status_data[0]["gps_enabled"]

    await setup_integration(hass, status_data)

    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("service", "gps_enabled"),
    [
        (SERVICE_TURN_ON, False),
        (SERVICE_TURN_OFF, True),
    ],
)
async def test_starlink_positioning_exclusive_set(
    hass: HomeAssistant, service: str, gps_enabled: bool
) -> None:
    """Test turning the switch on disables GPS and turning it off enables it."""
    entry = await setup_integration(hass, deepcopy(STATUS_DATA_FIXTURE))

    with patch(SET_GPS_CONFIG_TARGET) as mock_set_gps_config:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mock_set_gps_config.assert_called_once_with(
        gps_enabled, entry.runtime_data.channel_context
    )


async def test_starlink_positioning_exclusive_error(hass: HomeAssistant) -> None:
    """Test a communication error is raised as HomeAssistantError."""
    await setup_integration(hass, deepcopy(STATUS_DATA_FIXTURE))

    with (
        patch(SET_GPS_CONFIG_TARGET, side_effect=GrpcError("error")),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
