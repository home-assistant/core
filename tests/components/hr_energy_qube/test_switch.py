"""Tests for the Qube Heat Pump switch platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "switch.qube_heat_pump_heating_demand"


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all switch entities via snapshot."""
    with patch(
        "homeassistant.components.hr_energy_qube.PLATFORMS",
        [Platform.SWITCH],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "expected_value"),
    [
        (SERVICE_TURN_ON, True),
        (SERVICE_TURN_OFF, False),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    expected_value: bool,
) -> None:
    """Test turning a switch on and off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_qube_client.write_switch.assert_awaited_once_with(
        "modbus_demand", expected_value
    )


@pytest.mark.parametrize(
    ("side_effect", "return_value"),
    [
        (ConnectionError, None),
        (None, False),
    ],
)
async def test_turn_on_error(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception] | None,
    return_value: bool | None,
) -> None:
    """Test switch raises HomeAssistantError on write failure."""
    await setup_integration(hass, mock_config_entry)

    mock_qube_client.write_switch = AsyncMock(
        side_effect=side_effect, return_value=return_value
    )
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
