"""Test DoorBird init."""

from homeassistant.components.doorbird.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import mock_unauthorized_exception
from .conftest import DoorbirdMockerType


async def test_basic_setup(
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test basic setup."""
    doorbird_entry = await doorbird_mocker()
    entry = doorbird_entry.entry
    assert entry.state is ConfigEntryState.LOADED


async def test_auth_fails(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test basic setup with an auth failure."""
    doorbird_entry = await doorbird_mocker(
        info_side_effect=mock_unauthorized_exception()
    )
    entry = doorbird_entry.entry
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
