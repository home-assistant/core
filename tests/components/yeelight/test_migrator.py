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
from homeassistant.helpers import device_registry, entity_registry

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
        == f"v2-{config_entry.entry_id}"
    )
    assert er.async_get(f"light.{NAME}").unique_id == f"v2-{config_entry.entry_id}"
    assert (
        er.async_get(f"light.{NAME}_nightlight").unique_id
        == f"v2-{config_entry.entry_id}-nightlight"
    )
    assert (
        er.async_get(f"light.{NAME}_ambilight").unique_id
        == f"v2-{config_entry.entry_id}-ambilight"
    )


async def test_unique_id_migration(hass: HomeAssistant):
    """Test migration to new unique IDs."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **CONFIG_ENTRY_DATA,
            CONF_NIGHTLIGHT_SWITCH: True,
        },
    )
    config_entry.add_to_hass(hass)

    # Set up with old unique IDs
    mocked_bulb = _mocked_bulb()
    mocked_bulb.bulb_type = BulbType.WhiteTempMood
    with _patch_discovery(MODULE), patch(
        f"{MODULE}.Bulb", return_value=mocked_bulb
    ), patch(
        f"{MODULE}.binary_sensor.YeelightNightlightModeSensor.unique_id",
        f"{ID}-nightlight_sensor",
    ), patch(
        f"{MODULE}.light.YeelightGenericLight.unique_id", ID
    ), patch(
        f"{MODULE}.light.YeelightNightLightMode.unique_id", f"{ID}-nightlight"
    ), patch(
        f"{MODULE}.light.YeelightAmbientLight.unique_id", f"{ID}-ambilight"
    ), patch(
        f"{MODULE}.YeelightEntity.device_info", {"identifiers": {(DOMAIN, ID)}}
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Test old unique IDs
    er = await entity_registry.async_get_registry(hass)
    dr = await device_registry.async_get_registry(hass)
    assert (
        er.async_get(f"binary_sensor.{NAME}_nightlight").unique_id
        == f"{ID}-nightlight_sensor"
    )
    assert er.async_get(f"light.{NAME}").unique_id == ID
    assert er.async_get(f"light.{NAME}_nightlight").unique_id == f"{ID}-nightlight"
    assert er.async_get(f"light.{NAME}_ambilight").unique_id == f"{ID}-ambilight"
    devices = device_registry.async_entries_for_config_entry(dr, config_entry.entry_id)
    assert len(devices) == 1
    assert devices[0].identifiers == {(DOMAIN, ID)}

    # Reload to trigger migration
    with _patch_discovery(MODULE), patch(f"{MODULE}.Bulb", return_value=mocked_bulb):
        assert await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

    # Test new IDs
    assert (
        len(entity_registry.async_entries_for_config_entry(er, config_entry.entry_id))
        == 4
    )
    assert (
        er.async_get(f"binary_sensor.{NAME}_nightlight").unique_id
        == f"v2-{config_entry.entry_id}"
    )
    assert er.async_get(f"light.{NAME}").unique_id == f"v2-{config_entry.entry_id}"
    assert (
        er.async_get(f"light.{NAME}_nightlight").unique_id
        == f"v2-{config_entry.entry_id}-nightlight"
    )
    assert (
        er.async_get(f"light.{NAME}_ambilight").unique_id
        == f"v2-{config_entry.entry_id}-ambilight"
    )
    devices = device_registry.async_entries_for_config_entry(dr, config_entry.entry_id)
    assert len(devices) == 1
    assert devices[0].identifiers == {(DOMAIN, f"v2-{config_entry.entry_id}")}


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
