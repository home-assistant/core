"""Test Volvo buttons."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.models import VolvoApiException

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import configure_mock

from tests.common import MockConfigEntry, snapshot_platform


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


@pytest.mark.usefixtures("full_model")
@pytest.mark.parametrize(
    "command",
    ["start_climatization", "stop_climatization", "flash", "honk", "honk_flash"],
)
async def test_button_press(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
    command: str,
) -> None:
    """Test button press."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.BUTTON]):
        assert await setup_integration()

    entity_id = f"button.volvo_xc40_{command}"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(mock_api.async_execute_command.mock_calls) == 1


@pytest.mark.usefixtures("full_model")
@pytest.mark.parametrize(
    "command",
    ["start_climatization", "stop_climatization", "flash", "honk", "honk_flash"],
)
async def test_button_press_error(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
    command: str,
) -> None:
    """Test button press with error response."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.BUTTON]):
        assert await setup_integration()

    entity_id = f"button.volvo_xc40_{command}"
    configure_mock(mock_api.async_execute_command, side_effect=VolvoApiException)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
