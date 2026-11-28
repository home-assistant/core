"""Tests for the Moulinex sensor platform."""

from dataclasses import replace
from unittest.mock import MagicMock

from aiomoulinex import (
    PROGRAMS,
    ApplianceState,
    ConnectionLost,
    ConnectionRestored,
    CookingState,
    MoulinexConnectionError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.moulinex.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations

from . import push_event, push_state, setup_integration
from .conftest import COOKEO_ID, load_shadow, load_status

STATE_ENTITY_ID = "sensor.cookeo_touch_wifi"
PROGRESS_ENTITY_ID = "sensor.cookeo_touch_wifi_progress"


@pytest.mark.usefixtures("mock_moulinex_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot every Moulinex sensor entity."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_library_values_are_translated(hass: HomeAssistant) -> None:
    """Every state and program the library can return has a translation."""
    translations = await async_get_translations(hass, "en", "entity", {DOMAIN})
    prefix = f"component.{DOMAIN}.entity.sensor"

    assert {f"{prefix}.state.state.{state}" for state in CookingState} | {
        f"{prefix}.program.state.{program}"
        for programs in PROGRAMS.values()
        for program in programs.values()
    } <= translations.keys()


async def test_push_update(
    hass: HomeAssistant,
    mock_moulinex_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A status pushed by the appliance replaces the previous one."""
    await setup_integration(hass, mock_config_entry)
    state = mock_moulinex_client.states[COOKEO_ID]

    push_state(
        mock_moulinex_client,
        COOKEO_ID,
        replace(state, status=load_status("status_cooking.json")),
    )

    assert hass.states.get(STATE_ENTITY_ID).state == "cooking"
    assert hass.states.get(PROGRESS_ENTITY_ID).state == STATE_UNKNOWN


async def test_unavailable_while_connection_is_lost(
    hass: HomeAssistant,
    mock_moulinex_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Sensors are unavailable while the connection to the cloud is lost."""
    await setup_integration(hass, mock_config_entry)

    mock_moulinex_client.connected = False
    push_event(mock_moulinex_client, ConnectionLost(MoulinexConnectionError("timeout")))

    assert hass.states.get(STATE_ENTITY_ID).state == STATE_UNAVAILABLE

    mock_moulinex_client.connected = True
    push_event(mock_moulinex_client, ConnectionRestored())

    assert hass.states.get(STATE_ENTITY_ID).state == "warming"


async def test_unavailable_while_appliance_is_offline(
    hass: HomeAssistant,
    mock_moulinex_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Sensors are unavailable while the cloud does not reach the appliance."""
    await setup_integration(hass, mock_config_entry)
    online = mock_moulinex_client.states[COOKEO_ID]
    offline = ApplianceState(shadow=load_shadow("shadow_get_accepted.json"))

    push_state(mock_moulinex_client, COOKEO_ID, offline)

    assert hass.states.get(STATE_ENTITY_ID).state == STATE_UNAVAILABLE

    # The appliance is back, and has not answered the status request yet
    push_state(mock_moulinex_client, COOKEO_ID, replace(offline, shadow=online.shadow))

    assert hass.states.get(STATE_ENTITY_ID).state == STATE_UNKNOWN

    push_state(
        mock_moulinex_client,
        COOKEO_ID,
        replace(online, status=load_status("status_idle.json")),
    )

    assert hass.states.get(STATE_ENTITY_ID).state == "idle"
