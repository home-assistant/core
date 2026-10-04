"""Test the Vitesy button platform."""

from unittest.mock import AsyncMock, patch

from aiovitesy.api import VitesyDevice
from aiovitesy.exceptions import VitesyError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DEVICE_ID

from tests.common import MockConfigEntry, snapshot_platform

FILTER_CHANGED = "button.kitchen_shelfy_mark_filter_as_changed"
FRIDGE_CLEANED = "button.kitchen_shelfy_mark_fridge_as_cleaned"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.vitesy.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "component"),
    [
        pytest.param(FILTER_CHANGED, "filter", id="filter"),
        pytest.param(FRIDGE_CLEANED, "fridge", id="fridge"),
    ],
)
async def test_press_resets_maintenance(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    component: str,
) -> None:
    """Test pressing a button resets its component and refreshes the data."""
    await setup_integration(hass, mock_config_entry)
    mock_vitesy_client.get_all_devices.reset_mock()

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    mock_vitesy_client.reset_maintenance.assert_awaited_once_with(DEVICE_ID, component)
    mock_vitesy_client.get_all_devices.assert_awaited_once()


async def test_press_error(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a failed reset surfaces a translated error."""
    await setup_integration(hass, mock_config_entry)
    mock_vitesy_client.reset_maintenance.side_effect = VitesyError("boom")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: FILTER_CHANGED},
            blocking=True,
        )

    assert exc_info.value.translation_key == "reset_maintenance_failed"


async def test_buttons_absent_without_maintenance(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_devices: dict[str, VitesyDevice],
) -> None:
    """Test no buttons are created for components the device doesn't track."""
    mock_devices[DEVICE_ID].maintenance = {}

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(FILTER_CHANGED) is None
    assert hass.states.get(FRIDGE_CLEANED) is None
