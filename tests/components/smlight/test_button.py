"""Tests for SMLIGHT SLZB-06 button entities."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pysmlight import Info
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.smlight.const import SCAN_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.BUTTON]


MOCK_ROUTER = Info(MAC="AA:BB:CC:DD:EE:FF", zb_type=1)


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        ("core_restart", "reboot"),
        ("zigbee_flash_mode", "zb_bootloader"),
        ("zigbee_restart", "zb_restart"),
        ("reconnect_zigbee_router", "zb_router"),
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
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ROUTER
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


@pytest.mark.parametrize("entity_id", ["zigbee_flash_mode", "reconnect_zigbee_router"])
async def test_disabled_by_default_buttons(
    hass: HomeAssistant,
    entity_id: str,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test the disabled by default buttons."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ROUTER
    await setup_integration(hass, mock_config_entry)

    assert not hass.states.get(f"button.mock_{entity_id}")

    assert (entry := entity_registry.async_get(f"button.mock_title_{entity_id}"))
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_remove_router_reconnect(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test removal of orphaned router reconnect button."""
    save_mock = mock_smlight_client.get_info.side_effect
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = MOCK_ROUTER
    mock_config_entry = await setup_integration(hass, mock_config_entry)

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) == 4
    assert entities[3].unique_id == "aa:bb:cc:dd:ee:ff-reconnect_zigbee_router"

    mock_smlight_client.get_info.side_effect = save_mock

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)

    await hass.async_block_till_done()

    entity = entity_registry.async_get("button.mock_title_reconnect_zigbee_router")
    assert entity is None
