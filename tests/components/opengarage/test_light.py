"""Tests for OpenGarage opener lights."""

from datetime import timedelta
from unittest.mock import MagicMock

from aiohttp import ClientError
from opengarage.errors import ResponseError, TransportError, UnsupportedFeatureError
import pytest

from homeassistant.components import light
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "light.garage_abcdef_light"


@pytest.mark.parametrize(("initial", "expected"), [(0, STATE_OFF), (1, STATE_ON)])
async def test_light_entity(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    initial: int,
    expected: str,
) -> None:
    """Test light creation, unique ID, and initial device-reported state."""
    mock_opengarage.update_state.return_value["light"] = initial
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry
    assert entry.unique_id == "12345_light"
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == expected


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "requested", "reported", "expected", "result"),
    [
        (light.SERVICE_TURN_ON, True, 1, STATE_ON, 1),
        (light.SERVICE_TURN_OFF, False, 0, STATE_OFF, 1),
        (light.SERVICE_TURN_ON, True, 0, STATE_OFF, 1),
        (light.SERVICE_TURN_ON, True, 1, STATE_ON, None),
        (light.SERVICE_TURN_OFF, False, 0, STATE_OFF, None),
    ],
)
async def test_light_controls_refresh_device_state(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    service: str,
    requested: bool,
    reported: int,
    expected: str,
    result: int | None,
) -> None:
    """A successful command refreshes all device data without assuming state."""
    mock_opengarage.set_light.return_value = result
    mock_opengarage.update_state.reset_mock()
    mock_opengarage.update_state.return_value = {
        **mock_opengarage.update_state.return_value,
        "light": reported,
        "door": 1,
    }

    await hass.services.async_call(
        light.DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_opengarage.set_light.assert_awaited_once_with(requested)
    mock_opengarage.update_state.assert_awaited_once()
    assert (cover_state := hass.states.get("cover.garage_abcdef"))
    assert cover_state.state == STATE_OPEN
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == expected


@pytest.mark.usefixtures("init_integration")
async def test_light_controls_refresh_during_cooldown(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
) -> None:
    """Test back-to-back light controls do not return stale entity state."""
    mock_opengarage.set_light.return_value = 1
    mock_opengarage.update_state.return_value = {
        **mock_opengarage.update_state.return_value,
        "light": 1,
    }

    await hass.services.async_call(
        light.DOMAIN,
        light.SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_ON

    mock_opengarage.set_light.reset_mock()
    mock_opengarage.update_state.reset_mock()
    mock_opengarage.update_state.return_value = {
        **mock_opengarage.update_state.return_value,
        "light": 0,
    }

    await hass.services.async_call(
        light.DOMAIN,
        light.SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_opengarage.set_light.assert_awaited_once_with(False)
    mock_opengarage.update_state.assert_awaited_once()
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF


async def test_light_not_created_without_capability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opengarage: MagicMock,
) -> None:
    """Test legacy OpenGarage devices do not get a light entity."""
    mock_opengarage.update_state.return_value.pop("light")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is None


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("result", "message"),
    [
        (2, "device key is incorrect"),
        (3, "OpenGarage returned error code 3"),
    ],
)
async def test_light_control_error_surfaces_to_user(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    result: int | None,
    message: str,
) -> None:
    """Test failed commands raise an error without changing entity state."""
    mock_opengarage.set_light.return_value = result
    mock_opengarage.update_state.reset_mock()

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            light.DOMAIN,
            light.SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF
    mock_opengarage.update_state.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "error",
    [
        ClientError(),
        TimeoutError(),
        TransportError(),
        ResponseError(503, "http://device"),
        UnsupportedFeatureError(),
    ],
)
async def test_light_network_error(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    error: Exception,
) -> None:
    """Translate exhausted network errors without assuming command success."""
    mock_opengarage.set_light.side_effect = error
    mock_opengarage.update_state.reset_mock()

    with pytest.raises(HomeAssistantError, match="device is unavailable") as exc_info:
        await hass.services.async_call(
            light.DOMAIN,
            light.SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.__cause__ is error
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF
    mock_opengarage.update_state.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_light_state_missing_after_refresh(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
) -> None:
    """A missing light state on later polls is unknown rather than off."""
    mock_opengarage.update_state.return_value.pop("light")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("reported", [0, None])
async def test_light_empty_result_requires_confirmed_state(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    reported: int | None,
) -> None:
    """A missing command result only succeeds when a fresh poll confirms state."""
    mock_opengarage.set_light.return_value = None
    mock_opengarage.update_state.reset_mock()
    mock_opengarage.update_state.return_value["light"] = reported

    with pytest.raises(HomeAssistantError, match="Unable to confirm the requested"):
        await hass.services.async_call(
            light.DOMAIN,
            light.SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mock_opengarage.update_state.assert_awaited_once()


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("response", [{"light": 0}, None])
async def test_light_noop_cannot_use_cached_confirmation(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    response: dict[str, int] | None,
) -> None:
    """Bypass refresh cooldown and reject a failed poll despite cached ON state."""
    mock_opengarage.set_light.return_value = 1
    mock_opengarage.update_state.return_value = {
        **mock_opengarage.update_state.return_value,
        "light": 1,
    }
    await hass.services.async_call(
        light.DOMAIN,
        light.SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_ON

    mock_opengarage.set_light.return_value = None
    mock_opengarage.update_state.reset_mock()
    mock_opengarage.update_state.return_value = response

    with pytest.raises(HomeAssistantError, match="Unable to confirm the requested"):
        await hass.services.async_call(
            light.DOMAIN,
            light.SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mock_opengarage.update_state.assert_awaited_once()
