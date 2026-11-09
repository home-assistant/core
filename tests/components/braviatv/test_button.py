"""Test the Bravia TV buttons."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pybravia import BraviaError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import init_integration


@pytest.mark.usefixtures("mock_braviatv_client")
async def test_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the buttons."""
    with patch("homeassistant.components.braviatv.PLATFORMS", [Platform.BUTTON]):
        await init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        ("button.bravia_tv_model_restart", "reboot"),
        ("button.bravia_tv_model_terminate_apps", "terminate_apps"),
    ],
)
async def test_button_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
    method: str,
) -> None:
    """Test button press."""
    await init_integration(hass, mock_config_entry)
    power_status_calls = mock_braviatv_client.get_power_status.call_count

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    getattr(mock_braviatv_client, method).assert_called_once()

    # The press requests a debounced coordinator refresh
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_braviatv_client.get_power_status.call_count == power_status_calls + 1


async def test_button_press_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
) -> None:
    """Test button press error."""
    await init_integration(hass, mock_config_entry)

    mock_braviatv_client.reboot.side_effect = BraviaError

    with pytest.raises(
        HomeAssistantError, match="Error sending command to BRAVIA TV-Model"
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.bravia_tv_model_restart"},
            blocking=True,
        )
