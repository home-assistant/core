"""Tests for SMLIGHT SLZB-06 button entities."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.BUTTON]


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        ("core_restart", "reboot"),
        ("zigbee_flash_mode", "zb_bootloader"),
        ("zigbee_restart", "zb_restart"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_buttons(
    hass: HomeAssistant,
    entity_id: str,
    entity_registry: er.EntityRegistry,
    method: str,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test creation of button entities."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(f"button.mock_title_{entity_id}")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    entry = entity_registry.async_get(f"button.mock_title_{entity_id}")
    assert entry is not None
    assert entry.unique_id == f"aa:bb:cc:dd:ee:ff-{entity_id}"

    mock_method = getattr(mock_smlight_client.cmds, method)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: f"button.mock_title_{entity_id}"},
        blocking=True,
    )

    assert len(mock_method.mock_calls) == 1
    mock_method.assert_called_with()


@pytest.mark.usefixtures("mock_smlight_client")
async def test_disabled_by_default_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the disabled by default flash mode button."""
    await setup_integration(hass, mock_config_entry)

    assert not hass.states.get("button.mock_title_zigbee_flash_mode")

    assert (entry := entity_registry.async_get("button.mock_title_zigbee_flash_mode"))
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
