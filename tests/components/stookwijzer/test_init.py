"""Test the Stookwijzer init."""
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.stookwijzer.binary_sensor import (
    STOOKWIJZER_BINARY_SENSORS,
)
from homeassistant.components.stookwijzer.const import DOMAIN
from homeassistant.components.stookwijzer.sensor import STOOKWIJZER_SENSORS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_load_unload_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Stookwijzer configuration entry loading and unloading."""
    entry = await setup_integration(hass, aioclient_mock, True)

    assert entry.entry_id in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id is not None

    for description in STOOKWIJZER_SENSORS + STOOKWIJZER_BINARY_SENSORS:
        name = description.key.replace(" ", "_")
        if description.device_class in BinarySensorDeviceClass:
            state = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.{name}")
            assert state.state in {"off"}
        else:
            state = hass.states.get(f"{SENSOR_DOMAIN}.{name}")
            assert state.state in {"0", "2", "2.5", "code_yellow"}

        if description.attr_fn:
            assert len(state.attributes["forecast"]) == 12

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_load_unload_config_entry_when_device_unavailable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Stookwijzer configuration entry loading and unloading when the website is unavailable."""
    entry = await setup_integration(hass, aioclient_mock, False)

    assert entry.entry_id in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id is not None

    state = hass.states.get(f"{SENSOR_DOMAIN}.{DOMAIN.lower()}")
    assert state.state == "unavailable"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.NOT_LOADED
