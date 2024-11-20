"""Tests for select platform."""

from unittest.mock import patch

from flux_led.const import (
    COLOR_MODE_CCT as FLUX_COLOR_MODE_CCT,
    COLOR_MODE_RGBW as FLUX_COLOR_MODE_RGBW,
    WhiteChannelType,
)
from flux_led.protocol import PowerRestoreState, RemoteConfig
import pytest

from homeassistant.components import flux_led
from homeassistant.components.flux_led.const import CONF_WHITE_CHANNEL_TYPE, DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import (
    DEFAULT_ENTRY_TITLE,
    FLUX_DISCOVERY,
    IP_ADDRESS,
    MAC_ADDRESS,
    _mock_config_entry_for_bulb,
    _mocked_bulb,
    _mocked_switch,
    _patch_discovery,
    _patch_wifibulb,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def no_wait_on_state_change():
    """Disable waiting for state change in tests."""
    with patch("homeassistant.components.flux_led.select.STATE_CHANGE_LATENCY", 0):
        yield


async def test_switch_power_restore_state(hass: HomeAssistant) -> None:
    """Test a smart plug power restore state."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    switch = _mocked_switch()
    with _patch_discovery(), _patch_wifibulb(device=switch):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "select.bulb_rgbcw_ddeeff_power_restored"

    state = hass.states.get(entity_id)
    assert state.state == "Last State"

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "Always On"},
        blocking=True,
    )
    switch.async_set_power_restore.assert_called_once_with(
        channel1=PowerRestoreState.ALWAYS_ON
    )


async def test_power_restored_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a select unique id."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    switch = _mocked_switch()
    with _patch_discovery(), _patch_wifibulb(device=switch):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "select.bulb_rgbcw_ddeeff_power_restored"
    assert (
        entity_registry.async_get(entity_id).unique_id
        == f"{MAC_ADDRESS}_power_restored"
    )


async def test_power_restored_unique_id_no_discovery(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a select unique id."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
    )
    config_entry.add_to_hass(hass)
    switch = _mocked_switch()
    with _patch_discovery(no_device=True), _patch_wifibulb(device=switch):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "select.bulb_rgbcw_ddeeff_power_restored"
    assert (
        entity_registry.async_get(entity_id).unique_id
        == f"{config_entry.entry_id}_power_restored"
    )


async def test_select_addressable_strip_config(hass: HomeAssistant) -> None:
    """Test selecting addressable strip configs."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.raw_state = bulb.raw_state._replace(model_num=0xA2)  # addressable model
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    wiring_entity_id = "select.bulb_rgbcw_ddeeff_wiring"
    state = hass.states.get(wiring_entity_id)
    assert state.state == "BGRW"

    ic_type_entity_id = "select.bulb_rgbcw_ddeeff_ic_type"
    state = hass.states.get(ic_type_entity_id)
    assert state.state == "WS2812B"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            "select_option",
            {ATTR_ENTITY_ID: wiring_entity_id, ATTR_OPTION: "INVALID"},
            blocking=True,
        )
    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: wiring_entity_id, ATTR_OPTION: "GRBW"},
        blocking=True,
    )
    bulb.async_set_device_config.assert_called_once_with(wiring="GRBW")
    bulb.async_set_device_config.reset_mock()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            "select_option",
            {ATTR_ENTITY_ID: ic_type_entity_id, ATTR_OPTION: "INVALID"},
            blocking=True,
        )

    with patch(
        "homeassistant.components.flux_led.async_setup_entry"
    ) as mock_setup_entry:
        await hass.services.async_call(
            SELECT_DOMAIN,
            "select_option",
            {ATTR_ENTITY_ID: ic_type_entity_id, ATTR_OPTION: "UCS1618"},
            blocking=True,
        )
        await hass.async_block_till_done()
    bulb.async_set_device_config.assert_called_once_with(ic_type="UCS1618")
    assert len(mock_setup_entry.mock_calls) == 1


async def test_select_mutable_0x25_strip_config(hass: HomeAssistant) -> None:
    """Test selecting mutable 0x25 strip configs."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.operating_mode = "RGBWW"
    bulb.operating_modes = ["DIM", "CCT", "RGB", "RGBW", "RGBWW"]
    bulb.raw_state = bulb.raw_state._replace(model_num=0x25)  # addressable model
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    operating_mode_entity_id = "select.bulb_rgbcw_ddeeff_operating_mode"
    state = hass.states.get(operating_mode_entity_id)
    assert state.state == "RGBWW"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            "select_option",
            {ATTR_ENTITY_ID: operating_mode_entity_id, ATTR_OPTION: "INVALID"},
            blocking=True,
        )

    with patch(
        "homeassistant.components.flux_led.async_setup_entry"
    ) as mock_setup_entry:
        await hass.services.async_call(
            SELECT_DOMAIN,
            "select_option",
            {ATTR_ENTITY_ID: operating_mode_entity_id, ATTR_OPTION: "CCT"},
            blocking=True,
        )
        await hass.async_block_till_done()
    bulb.async_set_device_config.assert_called_once_with(operating_mode="CCT")
    assert len(mock_setup_entry.mock_calls) == 1


async def test_select_24ghz_remote_config(hass: HomeAssistant) -> None:
    """Test selecting 2.4ghz remote config."""
    _mock_config_entry_for_bulb(hass)
    bulb = _mocked_bulb()
    bulb.discovery = FLUX_DISCOVERY
    with _patch_discovery(device=FLUX_DISCOVERY), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    remote_config_entity_id = "select.bulb_rgbcw_ddeeff_remote_config"
    state = hass.states.get(remote_config_entity_id)
    assert state.state == "Open"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            "select_option",
            {ATTR_ENTITY_ID: remote_config_entity_id, ATTR_OPTION: "INVALID"},
            blocking=True,
        )

    bulb.remote_config = RemoteConfig.DISABLED
    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: remote_config_entity_id, ATTR_OPTION: "Disabled"},
        blocking=True,
    )
    bulb.async_config_remotes.assert_called_once_with(RemoteConfig.DISABLED)
    bulb.async_config_remotes.reset_mock()

    bulb.remote_config = RemoteConfig.PAIRED_ONLY
    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: remote_config_entity_id, ATTR_OPTION: "Paired Only"},
        blocking=True,
    )
    bulb.async_config_remotes.assert_called_once_with(RemoteConfig.PAIRED_ONLY)
    bulb.async_config_remotes.reset_mock()


async def test_select_white_channel_type(hass: HomeAssistant) -> None:
    """Test selecting the white channel type."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.color_modes = {FLUX_COLOR_MODE_RGBW, FLUX_COLOR_MODE_CCT}
    bulb.color_mode = FLUX_COLOR_MODE_RGBW
    bulb.raw_state = bulb.raw_state._replace(model_num=0x06)  # rgbw
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    operating_mode_entity_id = "select.bulb_rgbcw_ddeeff_white_channel"
    state = hass.states.get(operating_mode_entity_id)
    assert state.state == WhiteChannelType.WARM.name.title()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            "select_option",
            {ATTR_ENTITY_ID: operating_mode_entity_id, ATTR_OPTION: "INVALID"},
            blocking=True,
        )

    with patch(
        "homeassistant.components.flux_led.async_setup_entry"
    ) as mock_setup_entry:
        await hass.services.async_call(
            SELECT_DOMAIN,
            "select_option",
            {
                ATTR_ENTITY_ID: operating_mode_entity_id,
                ATTR_OPTION: WhiteChannelType.NATURAL.name.title(),
            },
            blocking=True,
        )
        await hass.async_block_till_done()
    assert (
        config_entry.data[CONF_WHITE_CHANNEL_TYPE]
        == WhiteChannelType.NATURAL.name.lower()
    )
    assert len(mock_setup_entry.mock_calls) == 1


async def test_select_device_no_wiring(hass: HomeAssistant) -> None:
    """Test select is not created if the device does not support wiring."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_NAME: DEFAULT_ENTRY_TITLE},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.wiring = None
    bulb.wirings = ["RGB", "GRB"]
    bulb.raw_state = bulb.raw_state._replace(model_num=0x25)
    with _patch_discovery(), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    wiring_entity_id = "select.bulb_rgbcw_ddeeff_wiring"
    assert hass.states.get(wiring_entity_id) is None
