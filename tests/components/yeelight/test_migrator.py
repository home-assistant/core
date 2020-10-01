"""Test the Yeelight migrators."""
from yeelight import BulbType

from homeassistant.components.yeelight import (
    CONF_MODE_MUSIC,
    CONF_MODEL,
    CONF_NIGHTLIGHT_SWITCH,
    CONF_SAVE_ON_CHANGE,
    CONF_TRANSITION,
    DEFAULT_MODE_MUSIC,
    DEFAULT_NIGHTLIGHT_SWITCH,
    DEFAULT_SAVE_ON_CHANGE,
    DEFAULT_TRANSITION,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

from . import (
    CONFIG_ENTRY_DATA,
    ID,
    IP_ADDRESS,
    MODEL,
    MODULE,
    NAME,
    _mocked_bulb,
    _patch_discovery,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_unique_ids(hass: HomeAssistant):
    """Test Yeelight new unique IDs."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **CONFIG_ENTRY_DATA,
            CONF_NIGHTLIGHT_SWITCH: True,
        },
    )
    config_entry.add_to_hass(hass)

    mocked_bulb = _mocked_bulb()
    mocked_bulb.bulb_type = BulbType.WhiteTempMood
    with _patch_discovery(MODULE), patch(f"{MODULE}.Bulb", return_value=mocked_bulb):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    er = await entity_registry.async_get_registry(hass)
    assert (
        er.async_get(f"binary_sensor.{NAME}_nightlight").unique_id
        == config_entry.entry_id
    )
    assert er.async_get(f"light.{NAME}").unique_id == config_entry.entry_id
    assert (
        er.async_get(f"light.{NAME}_nightlight").unique_id
        == f"{config_entry.entry_id}-nightlight"
    )
    assert (
        er.async_get(f"light.{NAME}_ambilight").unique_id
        == f"{config_entry.entry_id}-ambilight"
    )


async def test_name_migrator(hass: HomeAssistant):
    """Test name migration from old name."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS},
        options={
            CONF_NAME: NAME,
            CONF_MODEL: "",
            CONF_TRANSITION: DEFAULT_TRANSITION,
            CONF_MODE_MUSIC: DEFAULT_MODE_MUSIC,
            CONF_SAVE_ON_CHANGE: DEFAULT_SAVE_ON_CHANGE,
            CONF_NIGHTLIGHT_SWITCH: DEFAULT_NIGHTLIGHT_SWITCH,
        },
    )
    config_entry.add_to_hass(hass)

    mocked_bulb = _mocked_bulb()
    mocked_bulb.bulb_type = BulbType.WhiteTempMood
    with _patch_discovery(MODULE), patch(f"{MODULE}.Bulb", return_value=mocked_bulb):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.data == {
        CONF_HOST: IP_ADDRESS,
        CONF_NAME: NAME,
    }


async def test_name_migrator_generate(hass: HomeAssistant):
    """Test name migration from capabilities."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ID: ID},
        options={
            CONF_NAME: "",
            CONF_MODEL: "",
            CONF_TRANSITION: DEFAULT_TRANSITION,
            CONF_MODE_MUSIC: DEFAULT_MODE_MUSIC,
            CONF_SAVE_ON_CHANGE: DEFAULT_SAVE_ON_CHANGE,
            CONF_NIGHTLIGHT_SWITCH: DEFAULT_NIGHTLIGHT_SWITCH,
        },
    )
    config_entry.add_to_hass(hass)

    mocked_bulb = _mocked_bulb()
    mocked_bulb.bulb_type = BulbType.WhiteTempMood
    with _patch_discovery(MODULE), patch(f"{MODULE}.Bulb", return_value=mocked_bulb):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.data == {
        CONF_ID: ID,
        CONF_NAME: f"yeelight_{MODEL}_{ID}",
    }
