"""Test the rtl_433 coordinator."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyrtl_433.normalizer import NormalizedEvent

from homeassistant.components.rtl_433.const import DEFAULT_AVAILABILITY_TIMEOUT
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import emit_event, setup_integration

from tests.common import MockConfigEntry

TEMPERATURE_ENTITY_ID = "sensor.acurite_606tx_temperature_c"


async def test_client_receives_ha_configured_time_zone(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rtl433_client: MagicMock,
) -> None:
    """Test the coordinator hands the client Home Assistant's configured zone.

    An offset-less rtl_433 timestamp has to be read in the zone Home Assistant is
    configured for. Without this the host process zone is used instead, and a live
    event is misclassified as a stale replay whenever the two differ.
    """
    await hass.config.async_set_time_zone("America/New_York")

    await setup_integration(hass, mock_config_entry)

    event_tz = mock_rtl433_client.call_args.kwargs["event_tz"]
    assert event_tz == dt_util.get_default_time_zone()
    assert event_tz.key == "America/New_York"


async def test_replay_seeds_value_without_liveness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rtl433_client: MagicMock,
    mock_event: NormalizedEvent,
) -> None:
    """Test a replayed frame seeds the reading but does not mark the device live."""
    await setup_integration(hass, mock_config_entry)

    await emit_event(hass, mock_rtl433_client, replace(mock_event, is_replay=True))

    # The value seeds so the entity restores on reconnect, but a device heard only
    # through the server's backlog has not actually transmitted.
    state = hass.states.get(TEMPERATURE_ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


async def test_offline_device_not_resurrected_by_replay(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rtl433_client: MagicMock,
    mock_event: NormalizedEvent,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a replay cannot bring a device back after it has gone offline."""
    await setup_integration(hass, mock_config_entry)
    await emit_event(hass, mock_rtl433_client, mock_event)

    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "21.5"

    freezer.tick(timedelta(seconds=DEFAULT_AVAILABILITY_TIMEOUT + 1))
    await emit_event(hass, mock_rtl433_client, replace(mock_event, is_replay=True))

    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == STATE_UNAVAILABLE

    await emit_event(hass, mock_rtl433_client, mock_event)

    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "21.5"
