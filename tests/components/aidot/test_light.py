"""Test the aidot device."""

from syrupy import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGBW_COLOR,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_LIGHT = "light.test_light"
LIGHT_DOMAIN = "light"


async def test_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_turn_on(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_device_client
) -> None:
    """Test turn on."""
    # assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT},
        blocking=True,
    )
    mocked_device_client.async_turn_on.assert_called_once()


async def test_turn_off(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_device_client
) -> None:
    """Test turn off."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_LIGHT},
        blocking=True,
    )
    mocked_device_client.async_turn_off.assert_called_once()


async def test_trun_on_brightness(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_device_client
) -> None:
    """Test turn on brightness."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    mocked_device_client.async_set_brightness.assert_called_once()


async def test_turn_on_with_color_temp(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_device_client
) -> None:
    """Test turn on with color temp."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_COLOR_TEMP_KELVIN: 3000},
        blocking=True,
    )
    mocked_device_client.async_set_cct.assert_called_once()


async def test_turn_on_with_rgbw(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_device_client
) -> None:
    """Test turn on with rgbw."""
    assert await async_setup_component(hass, "homeassistant", {})
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_RGBW_COLOR: (255, 255, 255, 255)},
        blocking=True,
    )
    mocked_device_client.async_set_rgbw.assert_called_once()
