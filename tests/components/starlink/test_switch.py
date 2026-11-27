"""Tests Starlink switches."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from starlink_grpc import GrpcError

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SwitchService,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    TargetKey,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import JsonArrayType

from . import STATUS_DATA_FIXTURE

ENTITY_ID = "switch.starlink_use_starlink_positioning_exclusively"
SET_GPS_CONFIG_TARGET = "homeassistant.components.starlink.coordinator.set_gps_config"


def _status_with_gps_enabled(gps_enabled: bool | None) -> JsonArrayType:
    """Return status data with the given GPS state."""
    status_data = deepcopy(STATUS_DATA_FIXTURE)
    status_data[0]["gps_enabled"] = gps_enabled
    return status_data


def _status_without_gps_enabled() -> JsonArrayType:
    """Return status data where the dish omits the GPS state."""
    status_data = deepcopy(STATUS_DATA_FIXTURE)
    del status_data[0]["gps_enabled"]
    return status_data


@pytest.mark.parametrize(
    ("status_data", "expected_state"),
    [
        pytest.param(_status_with_gps_enabled(True), STATE_OFF, id="gps_enabled"),
        pytest.param(_status_with_gps_enabled(False), STATE_ON, id="gps_disabled"),
        pytest.param(_status_with_gps_enabled(None), STATE_UNKNOWN, id="gps_unknown"),
    ],
    indirect=["status_data"],
)
@pytest.mark.usefixtures("init_integration")
async def test_starlink_positioning_exclusive_state(
    hass: HomeAssistant, expected_state: str
) -> None:
    """Test the switch is on when the dish does not use GPS."""
    assert hass.states.get(ENTITY_ID).state == expected_state


@pytest.mark.parametrize(
    "status_data",
    [pytest.param(_status_without_gps_enabled(), id="gps_not_reported")],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_starlink_positioning_exclusive_not_reported(hass: HomeAssistant) -> None:
    """Test the switch is unknown when the dish omits the GPS state."""
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("service", "gps_enabled"),
    [
        (SERVICE_TURN_ON, False),
        (SERVICE_TURN_OFF, True),
    ],
)
async def test_starlink_positioning_exclusive_set(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    service: str,
    gps_enabled: bool,
) -> None:
    """Test turning the switch on disables GPS and turning it off enables it."""
    with patch(SET_GPS_CONFIG_TARGET) as mock_set_gps_config:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mock_set_gps_config.assert_called_once_with(
        gps_enabled, init_integration.runtime_data.channel_context
    )


@pytest.mark.usefixtures("init_integration")
async def test_starlink_positioning_exclusive_error(hass: HomeAssistant) -> None:
    """Test a communication error is raised as HomeAssistantError."""
    with (
        patch(SET_GPS_CONFIG_TARGET, side_effect=GrpcError("error")),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_ON,
            {TargetKey.ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
