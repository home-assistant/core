"""Test Volvo buttons."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.models import VolvoApiException

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import configure_mock

from tests.common import MockConfigEntry, snapshot_platform

_BUTTON_ID = "button.volvo_xc40_start_climatization"


@pytest.mark.usefixtures("mock_api", "full_model")
@pytest.mark.parametrize(
    "full_model",
    ["ex30_2024", "s90_diesel_2018", "xc40_electric_2024", "xc90_petrol_2019"],
)
async def test_button(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test button."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.BUTTON]):
        assert await setup_integration()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_api", "full_model")
async def test_button_press(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
) -> None:
    """Test button press."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.BUTTON]):
        assert await setup_integration()

    assert hass.states.get(_BUTTON_ID).state == STATE_UNKNOWN

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: _BUTTON_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(_BUTTON_ID).state != STATE_UNKNOWN


@pytest.mark.usefixtures("mock_api", "full_model")
async def test_button_press_error(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test button press with error response."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.BUTTON]):
        assert await setup_integration()

    assert hass.states.get(_BUTTON_ID).state == STATE_UNKNOWN

    configure_mock(mock_api.async_execute_command, side_effect=VolvoApiException)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: _BUTTON_ID},
            blocking=True,
        )
