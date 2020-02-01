"""Test init of Sensibo component."""
import json

from asynctest import patch as asynctest_patch

from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_ID
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from tests.common import load_fixture

MOCK_DEVICE_ID = "sensibo-device-id-1"
MOCK_DEVICE_ENTITY_ID = "climate.fake_sensibo_device"
UNWANTED_MOCK_DEVICE_ID = "sensibo-device-id-1"
UNWANTED_MOCK_DEVICE_ENTITY_ID = "climate.unwanted_fake_sensibo_device"
MOCK_CONFIG_BASIC = {DOMAIN: [{CONF_API_KEY: "config-fake-api-key"}]}
MOCK_CONFIG_WITH_DEVICE_IDS = {
    DOMAIN: [
        {
            CONF_API_KEY: "config-fake-api-key-with-device-ids",
            CONF_ID: [MOCK_DEVICE_ID],
        }
    ]
}
DEVICES_FIXTURE = json.loads(load_fixture("sensibo/devices_response.json"))
SINGLE_DEVICE_FIXTURE_1 = json.loads(
    load_fixture("sensibo/single_device_response_1.json")
)
SINGLE_DEVICE_FIXTURE_2 = json.loads(
    load_fixture("sensibo/single_device_response_2.json")
)


async def _mock_async_get_device(device_id):
    if device_id == MOCK_DEVICE_ID:
        return SINGLE_DEVICE_FIXTURE_1

    return SINGLE_DEVICE_FIXTURE_2


async def test_setup_basic(hass):
    """Test that a YAML configuration works together with the config flow."""
    with asynctest_patch(
        "pysensibo.SensiboClient.async_get_devices", return_value=DEVICES_FIXTURE,
    ), asynctest_patch(
        "pysensibo.SensiboClient.async_get_device", new=_mock_async_get_device,
    ):
        await async_setup_component(hass, DOMAIN, MOCK_CONFIG_BASIC)
        await hass.async_block_till_done()

    state = hass.states.get(MOCK_DEVICE_ENTITY_ID)
    unwanted_state_when_wanted = hass.states.get(UNWANTED_MOCK_DEVICE_ENTITY_ID)

    assert state
    assert state.name == "Fake Sensibo Device"

    assert unwanted_state_when_wanted
    assert unwanted_state_when_wanted.name == "Unwanted Fake Sensibo Device"


async def test_setup_multiple_filtered(hass):
    """Test that setup of multiple devices filters out the ones not listed in the config."""
    with asynctest_patch(
        "pysensibo.SensiboClient.async_get_devices", return_value=DEVICES_FIXTURE,
    ), asynctest_patch(
        "pysensibo.SensiboClient.async_get_device", new=_mock_async_get_device,
    ):
        await async_setup_component(hass, DOMAIN, MOCK_CONFIG_WITH_DEVICE_IDS)
        await hass.async_block_till_done()

    state = hass.states.get(MOCK_DEVICE_ENTITY_ID)
    unwanted_state = hass.states.get(UNWANTED_MOCK_DEVICE_ENTITY_ID)

    assert state
    assert state.name == "Fake Sensibo Device"
    assert not unwanted_state


async def test_unload(hass: HomeAssistantType):
    """Test that setup of multiple devices filters out the ones not listed in the config."""
    with asynctest_patch(
        "pysensibo.SensiboClient.async_get_devices", return_value=DEVICES_FIXTURE,
    ), asynctest_patch(
        "pysensibo.SensiboClient.async_get_device", new=_mock_async_get_device,
    ):
        await async_setup_component(hass, DOMAIN, MOCK_CONFIG_BASIC)
        await hass.async_block_till_done()

        state = hass.states.get(MOCK_DEVICE_ENTITY_ID)
        unwanted_state_when_wanted = hass.states.get(UNWANTED_MOCK_DEVICE_ENTITY_ID)

        assert state
        assert unwanted_state_when_wanted

        config_entries = hass.config_entries.async_entries(DOMAIN)
        assert len(config_entries) == 1

        existing_entry_id = config_entries[0].entry_id
        await hass.config_entries.async_unload(existing_entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(MOCK_DEVICE_ENTITY_ID)
        unwanted_state_when_wanted = hass.states.get(UNWANTED_MOCK_DEVICE_ENTITY_ID)
        assert not state
        assert not unwanted_state_when_wanted
