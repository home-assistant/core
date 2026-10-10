"""Test Hydrawise switch."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from pydrawise import APIError
from pydrawise.schema import Zone
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hydrawise.const import DEFAULT_WATERING_TIME
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
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_switches(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that all switches are working."""
    with patch(
        "homeassistant.components.hydrawise.PLATFORMS",
        [Platform.SWITCH],
    ):
        config_entry = await mock_add_config_entry()
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_manual_watering_services(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
    zones: list[Zone],
) -> None:
    """Test Manual Watering services."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "switch.zone_one_manual_watering"},
        blocking=True,
    )
    mock_pydrawise.start_zone.assert_called_once_with(
        zones[0], custom_run_duration=DEFAULT_WATERING_TIME.total_seconds()
    )
    state = hass.states.get("switch.zone_one_manual_watering")
    assert state is not None
    assert state.state == "on"
    mock_pydrawise.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        service_data={ATTR_ENTITY_ID: "switch.zone_one_manual_watering"},
        blocking=True,
    )
    mock_pydrawise.stop_zone.assert_called_once_with(zones[0])
    state = hass.states.get("switch.zone_one_manual_watering")
    assert state is not None
    assert state.state == "off"


@pytest.mark.freeze_time("2023-10-01 00:00:00+00:00")
async def test_auto_watering_services(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
    zones: list[Zone],
) -> None:
    """Test Automatic Watering services."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        service_data={ATTR_ENTITY_ID: "switch.zone_one_automatic_watering"},
        blocking=True,
    )
    mock_pydrawise.suspend_zone.assert_called_once_with(
        zones[0], dt_util.now() + timedelta(days=365)
    )
    state = hass.states.get("switch.zone_one_automatic_watering")
    assert state is not None
    assert state.state == "off"
    mock_pydrawise.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "switch.zone_one_automatic_watering"},
        blocking=True,
    )
    mock_pydrawise.resume_zone.assert_called_once_with(zones[0])
    state = hass.states.get("switch.zone_one_automatic_watering")
    assert state is not None
    assert state.state == "on"


@pytest.mark.parametrize(
    ("entity_id", "service", "api_method"),
    [
        ("switch.zone_one_manual_watering", SERVICE_TURN_ON, "start_zone"),
        ("switch.zone_one_manual_watering", SERVICE_TURN_OFF, "stop_zone"),
        ("switch.zone_one_automatic_watering", SERVICE_TURN_ON, "resume_zone"),
        ("switch.zone_one_automatic_watering", SERVICE_TURN_OFF, "suspend_zone"),
    ],
)
@pytest.mark.usefixtures("mock_added_config_entry")
async def test_switch_api_error(
    hass: HomeAssistant,
    mock_pydrawise: AsyncMock,
    entity_id: str,
    service: str,
    api_method: str,
) -> None:
    """Test that API errors raise a translated error."""
    getattr(mock_pydrawise, api_method).side_effect = APIError("Boom")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            service_data={ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert exc_info.value.translation_key == "command_error"
