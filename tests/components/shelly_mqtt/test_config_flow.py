"""Test the Shelly MQTT config flow."""

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.shelly_mqtt.config_flow import (
    CONF_DEVICE_ID,
    CONF_MODEL,
    CONF_TOPIC,
    async_discovery,
    validate_input,
)
from homeassistant.components.shelly_mqtt.const import DOMAIN

from .common import send_msg

from tests.async_mock import AsyncMock, MagicMock, patch
from tests.common import MockConfigEntry

DISCOVERY = [
    {
        "id": "shelly1-A929CC",
        "mac": "A929CC",
        "ip": "192.168.1.1",
        "new_fw": True,
        "fw_ver": "20200320-123430/v1.6.2@514044b4",
    },
    {
        "id": "shellyswitch-B929CC",
        "mac": "B929CC",
        "ip": "192.168.1.1",
        "new_fw": False,
        "fw_ver": "20200601-122823/v1.7.0@d7961837",
    },
    {
        "id": "unsupported-C929CC",
        "mac": "C929CC",
        "ip": "192.168.1.1",
        "new_fw": False,
        "fw_ver": "20200601-122823/v1.7.0@d7961837",
    },
]


SUPPORTED_COUNT = 2


MOCK_TOPIC = "shellies/shelly1-A929CC"


async def _setup_shelly_integration(hass):

    device_id = DISCOVERY[0]["id"]

    config = {
        CONF_DEVICE_ID: device_id,
        CONF_MODEL: "shelly1",
        CONF_TOPIC: MOCK_TOPIC,
    }

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source="user",
        data={**config},
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        options={},
        entry_id=1,
        unique_id=device_id,
    )
    config_entry.add_to_hass(hass)


async def test_mqtt_not_setup(hass):
    """Test that mqtt is required."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "mqtt_required"


async def test_no_devices(hass):
    """Test we abort when there are no devices."""
    hass.config.components.add("mqtt")
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.shelly_mqtt.config_flow.async_discovery",
        return_value={},
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] == "abort"
        assert result["reason"] == "no_devices_found"


async def test_ignore_existing_and_abort(hass):
    """Test that config flow discovery ignores setup devices."""

    hass.config.components.add("mqtt")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    with patch(
        "homeassistant.components.shelly_mqtt.config_flow.async_discovery",
        return_value=DISCOVERY,
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    await _setup_shelly_integration(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE_ID: DISCOVERY[0]["id"]}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_flow(hass):
    """Test the full flow."""
    hass.config.components.add("mqtt")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.shelly_mqtt.config_flow.async_discovery",
        return_value=DISCOVERY,
    ), patch(
        "homeassistant.components.shelly_mqtt.config_flow.validate_input",
        return_value=True,
    ), patch(
        "homeassistant.components.shelly_mqtt.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.shelly_mqtt.async_setup_entry", return_value=True,
    ) as mock_setup_entry:

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "device"
        assert (
            len(result["data_schema"].schema[CONF_DEVICE_ID].container)
            == SUPPORTED_COUNT
        )

        device_id = DISCOVERY[0]["id"]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_DEVICE_ID: device_id}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "topic"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TOPIC: MOCK_TOPIC},
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == f"Shelly 1 ({device_id})"
        assert result["data"] == {
            CONF_DEVICE_ID: device_id,
            CONF_TOPIC: MOCK_TOPIC,
            CONF_MODEL: "shelly1",
        }

        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_with_failed_validation(hass):
    """Test failed validation during the flow."""
    hass.config.components.add("mqtt")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.shelly_mqtt.config_flow.async_discovery",
        return_value=DISCOVERY,
    ), patch(
        "homeassistant.components.shelly_mqtt.config_flow.validate_input",
        return_value=False,
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "device"
        assert (
            len(result["data_schema"].schema[CONF_DEVICE_ID].container)
            == SUPPORTED_COUNT
        )

        device_id = DISCOVERY[0]["id"]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_DEVICE_ID: device_id}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "topic"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TOPIC: MOCK_TOPIC},
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "topic"
        assert result["errors"]["base"] == "cannot_connect"


async def test_form_with_invalid_topic(hass):
    """Test invalid mqtt topic."""
    hass.config.components.add("mqtt")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.shelly_mqtt.config_flow.async_discovery",
        return_value=DISCOVERY,
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "device"
        assert (
            len(result["data_schema"].schema[CONF_DEVICE_ID].container)
            == SUPPORTED_COUNT
        )

        device_id = DISCOVERY[0]["id"]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_DEVICE_ID: device_id}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "topic"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TOPIC: MOCK_TOPIC + "/#"},
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "topic"
        assert result["errors"]["base"] == "invalid_topic"


async def test_discovery(hass):
    """Test device discovery."""

    unsubscribed = MagicMock()

    async def subscribed(topic, callback):
        assert topic == "shellies/announce"
        send_msg(callback, DISCOVERY[0])
        send_msg(callback, DISCOVERY[1])
        send_msg(callback, DISCOVERY[2])
        return unsubscribed

    def published(topic, payload):
        assert topic == "shellies/command"
        assert payload == "announce"

    with patch.object(
        hass.components.mqtt, "async_subscribe", AsyncMock(side_effect=subscribed)
    ), patch.object(
        hass.components.mqtt, "async_publish", side_effect=published
    ) as mock_publish:

        devices = await async_discovery(hass, 0)
        assert devices == DISCOVERY
        assert len(mock_publish.mock_calls) == 1

    unsubscribed.called_once()


async def test_validate(hass):
    """Test input validation."""

    unsubscribed = MagicMock()

    topic_prefix = f"shellies/{DISCOVERY[0]['id']}/"

    async def subscribed(topic, callback):
        assert topic == topic_prefix + "online"
        send_msg(callback, True)
        return unsubscribed

    def published(topic, payload):
        assert topic == topic_prefix + "command"
        assert payload == "update"

    with patch.object(
        hass.components.mqtt, "async_subscribe", AsyncMock(side_effect=subscribed)
    ), patch.object(
        hass.components.mqtt, "async_publish", side_effect=published
    ) as mock_publish:

        success = await validate_input(hass, {"topic": topic_prefix}, 0)
        assert success
        assert len(mock_publish.mock_calls) == 1

    unsubscribed.called_once()


async def test_failed_validate(hass):
    """Test a failed input validation."""

    unsubscribed = MagicMock()

    topic_prefix = f"shellies/{DISCOVERY[0]['id']}/"

    async def subscribed(topic, callback):
        assert topic == topic_prefix + "online"
        return unsubscribed

    def published(topic, msg):
        assert topic == topic_prefix + "command"
        assert msg == "update"

    with patch.object(
        hass.components.mqtt, "async_subscribe", AsyncMock(side_effect=subscribed)
    ), patch.object(
        hass.components.mqtt, "async_publish", side_effect=published
    ) as mock_publish:

        success = await validate_input(hass, {"topic": topic_prefix}, 0)
        assert not success
        assert len(mock_publish.mock_calls) == 1

    unsubscribed.called_once()
