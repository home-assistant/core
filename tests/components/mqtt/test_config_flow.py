"""Test config flow."""
from unittest.mock import patch

import pytest
import voluptuous as vol
import yaml

from homeassistant import config as hass_config, config_entries, data_entry_flow
from homeassistant.components import mqtt
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_finish_setup():
    """Mock out the finish setup method."""
    with patch(
        "homeassistant.components.mqtt.MQTT.async_connect", return_value=True
    ) as mock_finish:
        yield mock_finish


@pytest.fixture
def mock_try_connection():
    """Mock the try connection method."""
    with patch("homeassistant.components.mqtt.config_flow.try_connection") as mock_try:
        yield mock_try


@pytest.fixture
def mock_try_connection_success():
    """Mock the try connection method with success."""

    _mid = 1

    def get_mid():
        nonlocal _mid
        _mid += 1
        return _mid

    def loop_start():
        """Simulate connect on loop start."""
        mock_client().on_connect(mock_client, None, None, 0)

    def _subscribe(topic, qos=0):
        mid = get_mid()
        mock_client().on_subscribe(mock_client, 0, mid)
        return (0, mid)

    def _unsubscribe(topic):
        mid = get_mid()
        mock_client().on_unsubscribe(mock_client, 0, mid)
        return (0, mid)

    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client().loop_start = loop_start
        mock_client().subscribe = _subscribe
        mock_client().unsubscribe = _unsubscribe

        yield mock_client()


@pytest.fixture
def mock_try_connection_time_out():
    """Mock the try connection method with a time out."""

    # Patch prevent waiting 5 sec for a timeout
    with patch("paho.mqtt.client.Client") as mock_client, patch(
        "homeassistant.components.mqtt.config_flow.MQTT_TIMEOUT", 0
    ):
        mock_client().loop_start = lambda *args: 1
        yield mock_client()


async def test_user_connection_works(
    hass, mock_try_connection, mock_finish_setup, mqtt_client_mock
):
    """Test we can finish a config flow."""
    mock_try_connection.return_value = True

    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"broker": "127.0.0.1"}
    )

    assert result["type"] == "create_entry"
    assert result["result"].data == {
        "broker": "127.0.0.1",
        "port": 1883,
        "discovery": True,
    }
    # Check we tried the connection
    assert len(mock_try_connection.mock_calls) == 1
    # Check config entry got setup
    assert len(mock_finish_setup.mock_calls) == 1


async def test_user_connection_fails(
    hass, mock_try_connection_time_out, mock_finish_setup
):
    """Test if connection cannot be made."""
    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"broker": "127.0.0.1"}
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"

    # Check we tried the connection
    assert len(mock_try_connection_time_out.mock_calls)
    # Check config entry did not setup
    assert len(mock_finish_setup.mock_calls) == 0


async def test_manual_config_starts_discovery_flow(
    hass, mock_try_connection, mock_finish_setup, mqtt_client_mock
):
    """Test manual config initiates a discovery flow."""
    # No flows in progress
    assert hass.config_entries.flow.async_progress() == []

    # MQTT config present in yaml config
    assert await async_setup_component(hass, "mqtt", {"mqtt": {}})
    await hass.async_block_till_done()
    assert len(mock_finish_setup.mock_calls) == 0

    # There should now be a discovery flow
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "integration_discovery"
    assert flows[0]["handler"] == "mqtt"
    assert flows[0]["step_id"] == "broker"


async def test_manual_config_set(
    hass,
    mock_try_connection,
    mock_finish_setup,
    mqtt_client_mock,
):
    """Test manual config does not create an entry, and entry can be setup late."""
    # MQTT config present in yaml config
    assert await async_setup_component(hass, "mqtt", {"mqtt": {"broker": "bla"}})
    await hass.async_block_till_done()
    # do not try to reload
    del hass.data["mqtt_reload_needed"]
    assert len(mock_finish_setup.mock_calls) == 0

    mock_try_connection.return_value = True

    # Start config flow
    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"broker": "127.0.0.1"}
    )

    assert result["type"] == "create_entry"
    assert result["result"].data == {
        "broker": "127.0.0.1",
        "port": 1883,
        "discovery": True,
    }
    # Check we tried the connection, with precedence for config entry settings
    mock_try_connection.assert_called_once_with(hass, "127.0.0.1", 1883, None, None)
    # Check config entry got setup
    assert len(mock_finish_setup.mock_calls) == 1


async def test_user_single_instance(hass):
    """Test we only allow a single config flow."""
    MockConfigEntry(domain="mqtt").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_hassio_already_configured(hass):
    """Test we only allow a single config flow."""
    MockConfigEntry(domain="mqtt").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_HASSIO}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_hassio_ignored(hass: HomeAssistant) -> None:
    """Test we supervisor discovered instance can be ignored."""
    MockConfigEntry(
        domain=mqtt.DOMAIN, source=config_entries.SOURCE_IGNORE
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        mqtt.DOMAIN,
        data=HassioServiceInfo(
            config={
                "addon": "Mosquitto",
                "host": "mock-mosquitto",
                "port": "1883",
                "protocol": "3.1.1",
            }
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result
    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_hassio_confirm(hass, mock_try_connection_success, mock_finish_setup):
    """Test we can finish a config flow."""
    mock_try_connection.return_value = True

    result = await hass.config_entries.flow.async_init(
        "mqtt",
        data=HassioServiceInfo(
            config={
                "addon": "Mock Addon",
                "host": "mock-broker",
                "port": 1883,
                "username": "mock-user",
                "password": "mock-pass",
                "protocol": "3.1.1",  # Set by the addon's discovery, ignored by HA
                "ssl": False,  # Set by the addon's discovery, ignored by HA
            }
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "hassio_confirm"
    assert result["description_placeholders"] == {"addon": "Mock Addon"}

    mock_try_connection_success.reset_mock()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"discovery": True}
    )

    assert result["type"] == "create_entry"
    assert result["result"].data == {
        "broker": "mock-broker",
        "port": 1883,
        "username": "mock-user",
        "password": "mock-pass",
        "discovery": True,
    }
    # Check we tried the connection
    assert len(mock_try_connection_success.mock_calls)
    # Check config entry got setup
    assert len(mock_finish_setup.mock_calls) == 1


async def test_option_flow(hass, mqtt_mock_entry_no_yaml_config, mock_try_connection):
    """Test config flow options."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    mock_try_connection.return_value = True
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    config_entry.data = {
        mqtt.CONF_BROKER: "test-broker",
        mqtt.CONF_PORT: 1234,
    }

    mqtt_mock.async_connect.reset_mock()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "broker"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "another-broker",
            mqtt.CONF_PORT: 2345,
            mqtt.CONF_USERNAME: "user",
            mqtt.CONF_PASSWORD: "pass",
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "options"

    await hass.async_block_till_done()
    assert mqtt_mock.async_connect.call_count == 0

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_DISCOVERY: True,
            "birth_enable": True,
            "birth_topic": "ha_state/online",
            "birth_payload": "online",
            "birth_qos": 1,
            "birth_retain": True,
            "will_enable": True,
            "will_topic": "ha_state/offline",
            "will_payload": "offline",
            "will_qos": 2,
            "will_retain": True,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert config_entry.data == {
        mqtt.CONF_BROKER: "another-broker",
        mqtt.CONF_PORT: 2345,
        mqtt.CONF_USERNAME: "user",
        mqtt.CONF_PASSWORD: "pass",
        mqtt.CONF_DISCOVERY: True,
        mqtt.CONF_BIRTH_MESSAGE: {
            mqtt.ATTR_TOPIC: "ha_state/online",
            mqtt.ATTR_PAYLOAD: "online",
            mqtt.ATTR_QOS: 1,
            mqtt.ATTR_RETAIN: True,
        },
        mqtt.CONF_WILL_MESSAGE: {
            mqtt.ATTR_TOPIC: "ha_state/offline",
            mqtt.ATTR_PAYLOAD: "offline",
            mqtt.ATTR_QOS: 2,
            mqtt.ATTR_RETAIN: True,
        },
    }

    await hass.async_block_till_done()
    assert mqtt_mock.async_connect.call_count == 1


async def test_disable_birth_will(
    hass, mqtt_mock_entry_no_yaml_config, mock_try_connection
):
    """Test disabling birth and will."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    mock_try_connection.return_value = True
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    config_entry.data = {
        mqtt.CONF_BROKER: "test-broker",
        mqtt.CONF_PORT: 1234,
    }

    mqtt_mock.async_connect.reset_mock()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "broker"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "another-broker",
            mqtt.CONF_PORT: 2345,
            mqtt.CONF_USERNAME: "user",
            mqtt.CONF_PASSWORD: "pass",
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "options"

    await hass.async_block_till_done()
    assert mqtt_mock.async_connect.call_count == 0

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_DISCOVERY: True,
            "birth_enable": False,
            "birth_topic": "ha_state/online",
            "birth_payload": "online",
            "birth_qos": 1,
            "birth_retain": True,
            "will_enable": False,
            "will_topic": "ha_state/offline",
            "will_payload": "offline",
            "will_qos": 2,
            "will_retain": True,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert config_entry.data == {
        mqtt.CONF_BROKER: "another-broker",
        mqtt.CONF_PORT: 2345,
        mqtt.CONF_USERNAME: "user",
        mqtt.CONF_PASSWORD: "pass",
        mqtt.CONF_DISCOVERY: True,
        mqtt.CONF_BIRTH_MESSAGE: {},
        mqtt.CONF_WILL_MESSAGE: {},
    }

    await hass.async_block_till_done()
    assert mqtt_mock.async_connect.call_count == 1


def get_default(schema, key):
    """Get default value for key in voluptuous schema."""
    for k in schema.keys():
        if k == key:
            if k.default == vol.UNDEFINED:
                return None
            return k.default()


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema.keys():
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]


async def test_option_flow_default_suggested_values(
    hass, mqtt_mock_entry_no_yaml_config, mock_try_connection_success
):
    """Test config flow options has default/suggested values."""
    await mqtt_mock_entry_no_yaml_config()
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    config_entry.data = {
        mqtt.CONF_BROKER: "test-broker",
        mqtt.CONF_PORT: 1234,
        mqtt.CONF_USERNAME: "user",
        mqtt.CONF_PASSWORD: "pass",
        mqtt.CONF_DISCOVERY: True,
        mqtt.CONF_BIRTH_MESSAGE: {
            mqtt.ATTR_TOPIC: "ha_state/online",
            mqtt.ATTR_PAYLOAD: "online",
            mqtt.ATTR_QOS: 1,
            mqtt.ATTR_RETAIN: True,
        },
        mqtt.CONF_WILL_MESSAGE: {
            mqtt.ATTR_TOPIC: "ha_state/offline",
            mqtt.ATTR_PAYLOAD: "offline",
            mqtt.ATTR_QOS: 2,
            mqtt.ATTR_RETAIN: False,
        },
    }

    # Test default/suggested values from config
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "broker"
    defaults = {
        mqtt.CONF_BROKER: "test-broker",
        mqtt.CONF_PORT: 1234,
    }
    suggested = {
        mqtt.CONF_USERNAME: "user",
        mqtt.CONF_PASSWORD: "pass",
    }
    for k, v in defaults.items():
        assert get_default(result["data_schema"].schema, k) == v
    for k, v in suggested.items():
        assert get_suggested(result["data_schema"].schema, k) == v

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "another-broker",
            mqtt.CONF_PORT: 2345,
            mqtt.CONF_USERNAME: "us3r",
            mqtt.CONF_PASSWORD: "p4ss",
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "options"
    defaults = {
        mqtt.CONF_DISCOVERY: True,
        "birth_qos": 1,
        "birth_retain": True,
        "will_qos": 2,
        "will_retain": False,
    }
    suggested = {
        "birth_topic": "ha_state/online",
        "birth_payload": "online",
        "will_topic": "ha_state/offline",
        "will_payload": "offline",
    }
    for k, v in defaults.items():
        assert get_default(result["data_schema"].schema, k) == v
    for k, v in suggested.items():
        assert get_suggested(result["data_schema"].schema, k) == v

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_DISCOVERY: False,
            "birth_topic": "ha_state/onl1ne",
            "birth_payload": "onl1ne",
            "birth_qos": 2,
            "birth_retain": False,
            "will_topic": "ha_state/offl1ne",
            "will_payload": "offl1ne",
            "will_qos": 1,
            "will_retain": True,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    # Test updated default/suggested values from config
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "broker"
    defaults = {
        mqtt.CONF_BROKER: "another-broker",
        mqtt.CONF_PORT: 2345,
    }
    suggested = {
        mqtt.CONF_USERNAME: "us3r",
        mqtt.CONF_PASSWORD: "p4ss",
    }
    for k, v in defaults.items():
        assert get_default(result["data_schema"].schema, k) == v
    for k, v in suggested.items():
        assert get_suggested(result["data_schema"].schema, k) == v

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={mqtt.CONF_BROKER: "another-broker", mqtt.CONF_PORT: 2345},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "options"
    defaults = {
        mqtt.CONF_DISCOVERY: False,
        "birth_qos": 2,
        "birth_retain": False,
        "will_qos": 1,
        "will_retain": True,
    }
    suggested = {
        "birth_topic": "ha_state/onl1ne",
        "birth_payload": "onl1ne",
        "will_topic": "ha_state/offl1ne",
        "will_payload": "offl1ne",
    }
    for k, v in defaults.items():
        assert get_default(result["data_schema"].schema, k) == v
    for k, v in suggested.items():
        assert get_suggested(result["data_schema"].schema, k) == v

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_DISCOVERY: True,
            "birth_topic": "ha_state/onl1ne",
            "birth_payload": "onl1ne",
            "birth_qos": 2,
            "birth_retain": False,
            "will_topic": "ha_state/offl1ne",
            "will_payload": "offl1ne",
            "will_qos": 1,
            "will_retain": True,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    # Make sure all MQTT related jobs are done before ending the test
    await hass.async_block_till_done()


async def test_options_user_connection_fails(hass, mock_try_connection_time_out):
    """Test if connection cannot be made."""
    config_entry = MockConfigEntry(domain=mqtt.DOMAIN)
    config_entry.add_to_hass(hass)
    config_entry.data = {
        mqtt.CONF_BROKER: "test-broker",
        mqtt.CONF_PORT: 1234,
    }
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == "form"

    mock_try_connection_time_out.reset_mock()
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={mqtt.CONF_BROKER: "bad-broker", mqtt.CONF_PORT: 2345},
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"

    # Check we tried the connection
    assert len(mock_try_connection_time_out.mock_calls)
    # Check config entry did not update
    assert config_entry.data == {
        mqtt.CONF_BROKER: "test-broker",
        mqtt.CONF_PORT: 1234,
    }


async def test_options_bad_birth_message_fails(hass, mock_try_connection):
    """Test bad birth message."""
    config_entry = MockConfigEntry(domain=mqtt.DOMAIN)
    config_entry.add_to_hass(hass)
    config_entry.data = {
        mqtt.CONF_BROKER: "test-broker",
        mqtt.CONF_PORT: 1234,
    }

    mock_try_connection.return_value = True

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == "form"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={mqtt.CONF_BROKER: "another-broker", mqtt.CONF_PORT: 2345},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"birth_topic": "ha_state/online/#"},
    )
    assert result["type"] == "form"
    assert result["errors"]["base"] == "bad_birth"

    # Check config entry did not update
    assert config_entry.data == {
        mqtt.CONF_BROKER: "test-broker",
        mqtt.CONF_PORT: 1234,
    }


async def test_options_bad_will_message_fails(hass, mock_try_connection):
    """Test bad will message."""
    config_entry = MockConfigEntry(domain=mqtt.DOMAIN)
    config_entry.add_to_hass(hass)
    config_entry.data = {
        mqtt.CONF_BROKER: "test-broker",
        mqtt.CONF_PORT: 1234,
    }

    mock_try_connection.return_value = True

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == "form"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={mqtt.CONF_BROKER: "another-broker", mqtt.CONF_PORT: 2345},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"will_topic": "ha_state/offline/#"},
    )
    assert result["type"] == "form"
    assert result["errors"]["base"] == "bad_will"

    # Check config entry did not update
    assert config_entry.data == {
        mqtt.CONF_BROKER: "test-broker",
        mqtt.CONF_PORT: 1234,
    }


async def test_try_connection_with_advanced_parameters(
    hass, mock_try_connection_success, tmp_path
):
    """Test config flow with advanced parameters from config."""
    # Mock certificate files
    certfile = tmp_path / "cert.pem"
    certfile.write_text("## mock certificate file ##")
    keyfile = tmp_path / "key.pem"
    keyfile.write_text("## mock key file ##")
    config = {
        "certificate": "auto",
        "tls_insecure": True,
        "client_cert": certfile,
        "client_key": keyfile,
    }
    new_yaml_config_file = tmp_path / "configuration.yaml"
    new_yaml_config = yaml.dump({mqtt.DOMAIN: config})
    new_yaml_config_file.write_text(new_yaml_config)
    assert new_yaml_config_file.read_text() == new_yaml_config

    with patch.object(hass_config, "YAML_CONFIG_FILE", new_yaml_config_file):
        await async_setup_component(hass, mqtt.DOMAIN, {mqtt.DOMAIN: config})
        await hass.async_block_till_done()
        config_entry = MockConfigEntry(domain=mqtt.DOMAIN)
        config_entry.add_to_hass(hass)
        config_entry.data = {
            mqtt.CONF_BROKER: "test-broker",
            mqtt.CONF_PORT: 1234,
            mqtt.CONF_USERNAME: "user",
            mqtt.CONF_PASSWORD: "pass",
            mqtt.CONF_DISCOVERY: True,
            mqtt.CONF_BIRTH_MESSAGE: {
                mqtt.ATTR_TOPIC: "ha_state/online",
                mqtt.ATTR_PAYLOAD: "online",
                mqtt.ATTR_QOS: 1,
                mqtt.ATTR_RETAIN: True,
            },
            mqtt.CONF_WILL_MESSAGE: {
                mqtt.ATTR_TOPIC: "ha_state/offline",
                mqtt.ATTR_PAYLOAD: "offline",
                mqtt.ATTR_QOS: 2,
                mqtt.ATTR_RETAIN: False,
            },
        }

        # Test default/suggested values from config
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "broker"
        defaults = {
            mqtt.CONF_BROKER: "test-broker",
            mqtt.CONF_PORT: 1234,
        }
        suggested = {
            mqtt.CONF_USERNAME: "user",
            mqtt.CONF_PASSWORD: "pass",
        }
        for k, v in defaults.items():
            assert get_default(result["data_schema"].schema, k) == v
        for k, v in suggested.items():
            assert get_suggested(result["data_schema"].schema, k) == v

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                mqtt.CONF_BROKER: "another-broker",
                mqtt.CONF_PORT: 2345,
                mqtt.CONF_USERNAME: "us3r",
                mqtt.CONF_PASSWORD: "p4ss",
            },
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "options"

        # check if the username and password was set from config flow and not from configuration.yaml
        assert mock_try_connection_success.username_pw_set.mock_calls[0][1] == (
            "us3r",
            "p4ss",
        )

        # check if tls_insecure_set is called
        assert mock_try_connection_success.tls_insecure_set.mock_calls[0][1] == (True,)

        # check if the certificate settings were set from configuration.yaml
        assert mock_try_connection_success.tls_set.mock_calls[0].kwargs[
            "certfile"
        ] == str(certfile)
        assert mock_try_connection_success.tls_set.mock_calls[0].kwargs[
            "keyfile"
        ] == str(keyfile)
