"""Tests for the Profalux Neosol cover platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyneosol import Action, TransportError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.neosol.coordinator import SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import CHANNELS

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "cover.shutter_0"
OTHER_ENTITY_ID = "cover.shutter_1"


@pytest.mark.usefixtures("mock_dongle")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test one cover entity is created per paired channel."""
    with patch("homeassistant.components.neosol.PLATFORMS", [Platform.COVER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "action"),
    [
        pytest.param(SERVICE_OPEN_COVER, Action.OPEN, id="open"),
        pytest.param(SERVICE_CLOSE_COVER, Action.CLOSE, id="close"),
        pytest.param(SERVICE_STOP_COVER, Action.STOP, id="stop"),
    ],
)
async def test_commands(
    hass: HomeAssistant,
    mock_dongle: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    action: Action,
) -> None:
    """Test each command transmits on the right channel and reports no state."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_dongle.send.assert_awaited_once_with(0, action)
    # The motors never answer, so no command may be turned into a state.
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN


async def test_command_failure(
    hass: HomeAssistant, mock_dongle: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test a transmission failure surfaces as a translated error."""
    await setup_integration(hass, mock_config_entry)
    mock_dongle.send.side_effect = TransportError("link died")

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )

    assert err.value.translation_key == "send_failed"


async def test_dropped_channel_becomes_unavailable(
    hass: HomeAssistant,
    mock_dongle: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a channel the dongle stops exposing is reported as unavailable."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(OTHER_ENTITY_ID).state != STATE_UNAVAILABLE

    mock_dongle.used_channels.return_value = CHANNELS[:1]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(OTHER_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE
