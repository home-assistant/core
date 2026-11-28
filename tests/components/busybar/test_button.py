"""Test BUSY Bar key press buttons."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from busylib.exceptions import BusyBarRequestError
from busylib.types import InputKey
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonService
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er


@pytest.fixture(autouse=True)
def button_platform_only() -> Generator[None]:
    """Set up only the button platform."""
    with patch("homeassistant.components.busybar.PLATFORMS", [Platform.BUTTON]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the key press buttons."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    ("entity_id", "key"),
    [
        ("button.busy_bar_busy", InputKey.BUSY),
        ("button.busy_bar_custom", InputKey.CUSTOM),
        ("button.busy_bar_start_pause", InputKey.START),
        ("button.busy_bar_off", InputKey.OFF),
        ("button.busy_bar_up", InputKey.UP),
        ("button.busy_bar_down", InputKey.DOWN),
        ("button.busy_bar_ok", InputKey.OK),
        ("button.busy_bar_back", InputKey.BACK),
        ("button.busy_bar_apps", InputKey.APPS),
        ("button.busy_bar_settings", InputKey.SETTINGS),
    ],
)
async def test_press(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    entity_id: str,
    key: InputKey,
) -> None:
    """Send the matching key press."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        ButtonService.PRESS,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_client.input.assert_awaited_once_with(key)


@pytest.mark.usefixtures("init_integration")
async def test_press_failure(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Raise a translated error when the bar cannot be reached."""
    mock_client.input.side_effect = BusyBarRequestError("offline")
    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            ButtonService.PRESS,
            {TargetKey.ENTITY_ID: "button.busy_bar_busy"},
            blocking=True,
        )
    assert excinfo.value.translation_key == "input_failed"
