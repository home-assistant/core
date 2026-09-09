"""Tests for OpenGarage opener lights."""

from unittest.mock import MagicMock

from aiohttp import ClientError
import pytest

from homeassistant.components import light
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

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
    ("service", "requested", "reported", "expected"),
    [
        (light.SERVICE_TURN_ON, True, 1, STATE_ON),
        (light.SERVICE_TURN_OFF, False, 0, STATE_OFF),
        (light.SERVICE_TURN_ON, True, 0, STATE_OFF),
    ],
)
async def test_light_controls_refresh_device_state(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    requested: bool,
    reported: int,
    expected: str,
) -> None:
    """A successful command refreshes all device data without assuming state."""
    mock_opengarage.set_light.return_value = 1
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
    assert mock_config_entry.runtime_data.data["door"] == 1
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == expected


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
        (None, "device is unavailable or does not support light control"),
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
@pytest.mark.parametrize("error", [ClientError, TimeoutError])
async def test_light_network_error(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    error: type[Exception],
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

    assert isinstance(exc_info.value.__cause__, error)
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF
    mock_opengarage.update_state.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_light_state_missing_after_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opengarage: MagicMock,
) -> None:
    """A missing light state on later polls is unknown rather than off."""
    mock_opengarage.update_state.return_value.pop("light")

    await mock_config_entry.runtime_data.async_request_refresh()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN
