"""Test Flukso config flow."""
from homeassistant import config_entries, data_entry_flow
from homeassistant.components.flukso.const import CONF_DEVICE_HASH, DOMAIN

from tests.common import MockConfigEntry

DEVICE_HASH = "0123456789abcdef0123456789abcdef"


async def test_mqtt_create_entry(hass, mqtt_mock):
    """Test we can finish a config flow through MQTT."""
    discovery_info = {
        "topic": f"/device/{DEVICE_HASH}/config/flx",
        "payload": "don't care",
        "qos": 0,
        "retain": True,
        "subscribed_topic": "/device/+/config/+",
        "timestamp": None,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=discovery_info
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == f"Flukso {DEVICE_HASH}"
    assert result["result"].data == {CONF_DEVICE_HASH: DEVICE_HASH}


async def test_mqtt_duplicate_error(hass, mqtt_mock):
    """Test if the config flow triggered through MQTT aborts when the device already exists."""
    conf = {CONF_DEVICE_HASH: DEVICE_HASH}

    MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN + "_" + DEVICE_HASH, data=conf
    ).add_to_hass(hass)

    discovery_info = {
        "topic": f"/device/{DEVICE_HASH}/config/flx",
        "payload": "don't care",
        "qos": 0,
        "retain": True,
        "subscribed_topic": "/device/+/config/+",
        "timestamp": None,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=discovery_info
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_user_create_entry(hass, mqtt_mock):
    """Test that the user can add a Flukso device manually."""
    conf = {CONF_DEVICE_HASH: DEVICE_HASH}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == f"Flukso {DEVICE_HASH}"
    assert result["data"][CONF_DEVICE_HASH] == DEVICE_HASH


async def test_user_duplicate_error(hass, mqtt_mock):
    """Test that an error is shown when a user adds a duplicate."""
    conf = {CONF_DEVICE_HASH: DEVICE_HASH}

    MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN + "_" + DEVICE_HASH, data=conf
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
