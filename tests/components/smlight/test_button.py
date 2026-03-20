"""Tests for SMLIGHT SLZB-06 button entities."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pysmlight import Info, Radio
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.smlight.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
)


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.BUTTON]


MOCK_ROUTER = Info(MAC="AA:BB:CC:DD:EE:FF", radios=[Radio(zb_type=1)])


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
    mock_method.assert_called()


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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_zigbee2_router_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test creation of second radio router button (if available)."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info.from_dict(
        await async_load_json_object_fixture(hass, "info-MR1.json", DOMAIN)
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("button.mock_title_reconnect_zigbee_router")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    entry = entity_registry.async_get("button.mock_title_reconnect_zigbee_router")
    assert entry is not None
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-reconnect_zigbee_router_1"


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


@pytest.mark.parametrize(
    ("key", "idx"),
    [
        ("zigbee_restart", 0),
        ("zigbee_flash_mode", 0),
        ("zigbee_restart", 1),
        ("zigbee_flash_mode", 1),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_multi_radio_buttons_u_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    key: str,
    idx: int,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test per-radio restart and flash mode buttons on a u-device."""
    mock_smlight_client.get_info.side_effect = None
    info = Info.from_dict(
        await async_load_json_object_fixture(hass, "info-MR1.json", DOMAIN)
    )
    info.u_device = True
    mock_smlight_client.get_info.return_value = info

    await setup_integration(hass, mock_config_entry)

    unique_id_suffix = f"_{idx}" if idx else ""
    unique_id = f"aa:bb:cc:dd:ee:ff-{key}{unique_id_suffix}"
    assert (
        entity_registry.async_get_entity_id(BUTTON_DOMAIN, DOMAIN, unique_id)
        is not None
    )


@pytest.mark.parametrize(
    ("key", "method", "idx"),
    [
        ("zigbee_restart", "zb_restart", 0),
        ("zigbee_restart", "zb_restart", 1),
        ("zigbee_flash_mode", "zb_bootloader", 0),
        ("zigbee_flash_mode", "zb_bootloader", 1),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_multi_radio_press_calls_idx(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    key: str,
    method: str,
    idx: int,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test pressing per-radio buttons passes the correct idx to the command."""
    mock_smlight_client.get_info.side_effect = None
    info = Info.from_dict(
        await async_load_json_object_fixture(hass, "info-MR1.json", DOMAIN)
    )
    info.u_device = True
    mock_smlight_client.get_info.return_value = info

    await setup_integration(hass, mock_config_entry)

    unique_id_suffix = f"_{idx}" if idx else ""
    unique_id = f"aa:bb:cc:dd:ee:ff-{key}{unique_id_suffix}"
    entity_id = entity_registry.async_get_entity_id(BUTTON_DOMAIN, DOMAIN, unique_id)
    assert entity_id is not None

    mock_method = getattr(mock_smlight_client.cmds, method)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_method.assert_called_once_with(idx=idx)


@pytest.mark.parametrize("key", ["zigbee_restart", "zigbee_flash_mode"])
async def test_multi_radio_buttons_shared_non_u_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    key: str,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test that idx>0 radio buttons are not created for non-u-devices."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info.from_dict(
        await async_load_json_object_fixture(hass, "info-MR1.json", DOMAIN)
    )
    await setup_integration(hass, mock_config_entry)

    assert not entity_registry.async_get_entity_id(
        BUTTON_DOMAIN, DOMAIN, f"aa:bb:cc:dd:ee:ff-{key}_1"
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_router_button_with_3_radios(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test creation of router buttons for device with 3 radios."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info(
        MAC="AA:BB:CC:DD:EE:FF",
        radios=[
            Radio(zb_type=0, chip_index=0),
            Radio(zb_type=1, chip_index=1),
            Radio(zb_type=0, chip_index=2),
        ],
    )
    await setup_integration(hass, mock_config_entry)

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) == 4

    entity = entity_registry.async_get("button.mock_title_reconnect_zigbee_router")
    assert entity is not None
