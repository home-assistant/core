"""Tests for Fritz!Tools button platform."""
import copy
from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.fritz.const import DOMAIN, MeshRoles
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import MOCK_MESH_DATA, MOCK_USER_DATA

from tests.common import MockConfigEntry


async def test_button_setup(hass: HomeAssistant, fc_class_mock, fh_class_mock) -> None:
    """Test setup of Fritz!Tools buttons."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED

    buttons = hass.states.async_all(BUTTON_DOMAIN)
    assert len(buttons) == 4

    for button in buttons:
        assert button.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("entity_id", "wrapper_method"),
    [
        ("button.mock_title_firmware_update", "async_trigger_firmware_update"),
        ("button.mock_title_restart", "async_trigger_reboot"),
        ("button.mock_title_reconnect", "async_trigger_reconnect"),
        ("button.mock_title_cleanup", "async_trigger_cleanup"),
    ],
)
async def test_buttons(
    hass: HomeAssistant,
    entity_id: str,
    wrapper_method: str,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test Fritz!Tools buttons."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED

    button = hass.states.get(entity_id)
    assert button
    assert button.state == STATE_UNKNOWN
    with patch(
        f"homeassistant.components.fritz.common.AvmWrapper.{wrapper_method}"
    ) as mock_press_action:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_press_action.assert_called_once()

        button = hass.states.get(entity_id)
        assert button.state != STATE_UNKNOWN


async def test_wol_button(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test Fritz!Tools wake on LAN button."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        PropertyMock(return_value=True),
    ):
        assert await async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED

    button = hass.states.get("button.printer_wake_on_lan")
    assert button
    assert button.state == STATE_UNKNOWN
    with patch(
        "homeassistant.components.fritz.common.AvmWrapper.async_wake_on_lan"
    ) as mock_press_action:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.printer_wake_on_lan"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_press_action.assert_called_once_with("AA:BB:CC:00:11:22")

        button = hass.states.get("button.printer_wake_on_lan")
        assert button.state != STATE_UNKNOWN


async def test_wol_button_absent_for_mesh_slave(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test WoL button not created if interviewed box is in slave mode."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    slave_mesh_data = copy.deepcopy(MOCK_MESH_DATA)
    slave_mesh_data["nodes"][0]["mesh_role"] = MeshRoles.SLAVE
    with patch(
        "tests.components.fritz.conftest.FritzHostMock.get_mesh_topology",
        return_value=slave_mesh_data,
    ), patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        PropertyMock(return_value=True),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert entry.state == ConfigEntryState.LOADED

        button = hass.states.get("button.printer_wake_on_lan")
        assert button is None


async def test_wol_button_absent_for_non_lan_device(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test WoL button not created if interviewed device is not connected via LAN."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    printer_wifi_data = copy.deepcopy(MOCK_MESH_DATA)
    # initialization logic uses the connection type of the `node_interface_1_uid` pair of the printer
    printer_wifi_data["nodes"][0]["node_interfaces"][3]["type"] = "WLAN"
    with patch(
        "tests.components.fritz.conftest.FritzHostMock.get_mesh_topology",
        return_value=printer_wifi_data,
    ), patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        PropertyMock(return_value=True),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert entry.state == ConfigEntryState.LOADED

        button = hass.states.get("button.printer_wake_on_lan")
        assert button is None
