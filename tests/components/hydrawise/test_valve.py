"""Test Hydrawise valve."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, patch

from pydrawise import APIError
from pydrawise.schema import Zone
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_valves(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that all valves are working."""
    with patch(
        "homeassistant.components.hydrawise.PLATFORMS",
        [Platform.VALVE],
    ):
        config_entry = await mock_add_config_entry()
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_services(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
    zones: list[Zone],
) -> None:
    """Test valve services."""
    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_OPEN_VALVE,
        service_data={ATTR_ENTITY_ID: "valve.zone_one"},
        blocking=True,
    )
    mock_pydrawise.start_zone.assert_called_once_with(zones[0])
    mock_pydrawise.reset_mock()

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_CLOSE_VALVE,
        service_data={ATTR_ENTITY_ID: "valve.zone_one"},
        blocking=True,
    )
    mock_pydrawise.stop_zone.assert_called_once_with(zones[0])


@pytest.mark.parametrize(
    ("service", "api_method"),
    [
        (SERVICE_OPEN_VALVE, "start_zone"),
        (SERVICE_CLOSE_VALVE, "stop_zone"),
    ],
)
@pytest.mark.usefixtures("mock_added_config_entry")
async def test_valve_api_error(
    hass: HomeAssistant,
    mock_pydrawise: AsyncMock,
    service: str,
    api_method: str,
) -> None:
    """Test that API errors raise a translated error."""
    getattr(mock_pydrawise, api_method).side_effect = APIError("Boom")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            VALVE_DOMAIN,
            service,
            service_data={ATTR_ENTITY_ID: "valve.zone_one"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "command_error"
