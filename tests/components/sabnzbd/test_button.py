"""Button tests for the SABnzbd component."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pysabnzbd import SabnzbdApiException
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@patch("homeassistant.components.sabnzbd.PLATFORMS", [Platform.BUTTON])
async def test_button_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test button setup."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("button", "called_function"),
    [("resume", "resume_queue"), ("pause", "pause_queue")],
)
@pytest.mark.usefixtures("setup_integration")
async def test_button_presses(
    hass: HomeAssistant,
    sabnzbd: AsyncMock,
    button: str,
    called_function: str,
) -> None:
    """Test the sabnzbd button presses."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: f"button.sabnzbd_{button}",
        },
        blocking=True,
    )

    function = getattr(sabnzbd, called_function)
    function.assert_called_once()


@pytest.mark.parametrize(
    ("button", "called_function"),
    [("resume", "resume_queue"), ("pause", "pause_queue")],
)
@pytest.mark.usefixtures("setup_integration")
async def test_buttons_exception(
    hass: HomeAssistant,
    sabnzbd: AsyncMock,
    button: str,
    called_function: str,
) -> None:
    """Test the button handles errors."""
    function = getattr(sabnzbd, called_function)
    function.side_effect = SabnzbdApiException("Boom")

    with pytest.raises(
        HomeAssistantError,
        match="Unable to send command to SABnzbd due to a connection error, try again later",
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: f"button.sabnzbd_{button}",
            },
            blocking=True,
        )

    function.assert_called_once()


@pytest.mark.parametrize(
    "button",
    ["resume", "pause"],
)
@pytest.mark.usefixtures("setup_integration")
async def test_buttons_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    sabnzbd: AsyncMock,
    button: str,
) -> None:
    """Test the button is unavailable when coordinator can't update data."""
    state = hass.states.get(f"button.sabnzbd_{button}")
    assert state
    assert state.state == STATE_UNKNOWN

    sabnzbd.refresh_data.side_effect = Exception("Boom")
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(f"button.sabnzbd_{button}")
    assert state
    assert state.state == STATE_UNAVAILABLE
