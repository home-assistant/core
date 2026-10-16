"""Test the Vitesy select platform."""

from unittest.mock import AsyncMock, patch

from aiovitesy.api import VitesyDevice, VitesyModeStatus
from aiovitesy.exceptions import VitesyError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.vitesy.coordinator import UPDATE_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DEVICE_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

MODE = "select.kitchen_shelfy_mode"
AIR_QUALITY_SCORE = "sensor.kitchen_shelfy_air_quality_score"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.vitesy.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("mode_status", "state"),
    [
        pytest.param(
            VitesyModeStatus(desired_mode="boost", current_mode="eco", pending=True),
            "boost",
            id="pending_shows_desired",
        ),
        pytest.param(
            VitesyModeStatus(desired_mode=None, current_mode="shelf", pending=False),
            "shelf",
            id="no_desired_falls_back_to_reported",
        ),
    ],
)
async def test_current_option(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mode_status: VitesyModeStatus,
    state: str,
) -> None:
    """Test the select shows the requested mode, falling back to the reported one."""
    mock_vitesy_client.get_mode_status.return_value = mode_status

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(MODE).state == state


async def test_select_option(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting a mode sets it on the device and refreshes the data."""
    await setup_integration(hass, mock_config_entry)
    mock_vitesy_client.get_mode_status.return_value = VitesyModeStatus(
        desired_mode="boost", current_mode="eco", pending=True
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: MODE, ATTR_OPTION: "boost"},
        blocking=True,
    )

    mock_vitesy_client.set_mode.assert_awaited_once_with(DEVICE_ID, "boost")
    assert hass.states.get(MODE).state == "boost"


async def test_select_option_error(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a failed mode change surfaces a translated error."""
    await setup_integration(hass, mock_config_entry)
    mock_vitesy_client.set_mode.side_effect = VitesyError("boom")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: MODE, ATTR_OPTION: "boost"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "set_mode_failed"


async def test_mode_read_failure_only_affects_select(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed mode read makes only the select unavailable, then recovers."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(MODE).state == "eco"

    mock_vitesy_client.get_mode_status.side_effect = VitesyError("boom")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(MODE).state == STATE_UNAVAILABLE
    assert hass.states.get(AIR_QUALITY_SCORE).state != STATE_UNAVAILABLE

    mock_vitesy_client.get_mode_status.side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(MODE).state == "eco"


async def test_select_not_created_for_other_devices(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_devices: dict[str, VitesyDevice],
) -> None:
    """Test devices without a settable mode get no select and no shadow reads."""
    mock_devices[DEVICE_ID].device_type = "NATEDE"

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(MODE) is None
    mock_vitesy_client.get_mode_status.assert_not_called()
