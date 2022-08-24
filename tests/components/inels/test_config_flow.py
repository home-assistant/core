"""Test config flow."""
from unittest.mock import patch

from inelsmqtt.const import MQTT_TRANSPORT
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import inels
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.const import (
    CONF_DISCOVERY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_SSL,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_is_available():
    """Mock test_connection inside InelsMqtt."""
    with patch(
        "inelsmqtt.InelsMqtt.test_connection", return_value=True
    ) as mock_available:
        yield mock_available


@pytest.fixture
def mock_try_connection():
    """Mock the try connection method."""
    with patch("homeassistant.components.inels.config_flow.try_connection") as mock_try:
        yield mock_try


@pytest.fixture
def mock_mqtt_client():
    """Mock mqtt client."""

    def enable_logger():
        """Enable looger."""

    def username_pw_set():
        """Define user name and pwd."""
        mqtt().username_pw_set(None, None)

    with patch("paho.mqtt.client.Client") as mqtt:
        mqtt().username_pw_set = username_pw_set
        mqtt().enable_logger = enable_logger

        yield mqtt()


async def test_user_config_flow_finised_successfully(
    hass: HomeAssistant, mock_try_connection
) -> None:
    """Test if we can finish config flow."""
    mock_try_connection.return_value = True

    result = await hass.config_entries.flow.async_init(
        inels.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result[CONF_TYPE] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "setup"

    config = {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 1883,
        CONF_USERNAME: "test",
        CONF_PASSWORD: "pwd",
        MQTT_TRANSPORT: "tcp",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        config,
    )

    config[CONF_DISCOVERY] = True

    assert result[CONF_TYPE] == "create_entry"
    assert result["result"].data == config

    assert len(mock_try_connection.mock_calls) == 1


async def test_use_config_flow_finised_failed(
    hass: HomeAssistant, mock_try_connection
) -> None:
    """Test if connection failed."""
    mock_try_connection.return_value = False

    result = await hass.config_entries.flow.async_init(
        inels.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result[CONF_TYPE] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "setup"

    config = {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 1883,
        CONF_USERNAME: "test",
        CONF_PASSWORD: "pwd",
        MQTT_TRANSPORT: "tcp",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        config,
    )

    config[CONF_DISCOVERY] = True

    assert result[CONF_TYPE] == "form"
    assert result["errors"]["base"] == "cannot_connect"

    assert len(mock_try_connection.mock_calls) == 1


async def test_config_setup(
    hass: HomeAssistant, mock_try_connection, mock_is_available
):
    """Test configuration."""
    mock_try_connection.return_value = True

    result = await hass.config_entries.flow.async_init(
        inels.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result[CONF_TYPE] == data_entry_flow.RESULT_TYPE_FORM

    config = {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 1883,
        CONF_USERNAME: "test",
        CONF_PASSWORD: "pwd",
        MQTT_TRANSPORT: "tcp",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        config,
    )

    config[CONF_DISCOVERY] = True

    assert result[CONF_TYPE] == "create_entry"
    assert result["result"].data == config

    mock_try_connection.assert_called_once_with(
        hass, "127.0.0.1", 1883, "test", "pwd", "tcp"
    )

    assert len(mock_is_available.mock_calls) == 1


async def test_single_instance(hass: HomeAssistant) -> None:
    """Test only on single instance of inels integration."""
    MockConfigEntry(domain=inels.DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        inels.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result[CONF_TYPE] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_hassio_ignored(hass: HomeAssistant) -> None:
    """Test instance can be ignored."""
    MockConfigEntry(
        domain=inels.DOMAIN, source=config_entries.SOURCE_IGNORE
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        inels.DOMAIN,
        data=HassioServiceInfo(
            config={
                "addon": "Mosquitto",
                CONF_HOST: "mock-mosquitto",
                CONF_PORT: "1883",
                CONF_PROTOCOL: "3.1.1",
            }
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )

    assert result
    assert result.get(CONF_TYPE) == data_entry_flow.RESULT_TYPE_ABORT
    assert result.get("reason") == "already_configured"


async def test_hassio_already_configured(hass: HomeAssistant) -> None:
    """Only one config flow can be set up."""
    MockConfigEntry(domain=inels.DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        inels.DOMAIN, context={"source": config_entries.SOURCE_HASSIO}
    )
    assert result[CONF_TYPE] == "abort"
    assert result["reason"] == "already_configured"


async def test_hassio_confirm(
    hass: HomeAssistant, mock_try_connection, mock_is_available
):
    """Test we can finish a config flow."""
    mock_try_connection.return_value = True

    result = await hass.config_entries.flow.async_init(
        inels.DOMAIN,
        data=HassioServiceInfo(
            config={
                "addon": "Mock Addon",
                CONF_HOST: "mock-mqtt",
                CONF_PORT: 1883,
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
                CONF_PROTOCOL: "3.1.1",  # Set by the addon's discovery, ignored by HA
                MQTT_TRANSPORT: "tcp",
                CONF_SSL: False,  # Set by the addon's discovery, ignored by HA
            }
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result[CONF_TYPE] == "form"
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"addon": "Mock Addon"}

    mock_try_connection.reset_mock()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"discovery": True}
    )

    assert result[CONF_TYPE] == "create_entry"
    assert result["result"].data == {
        CONF_HOST: "mock-mqtt",
        CONF_PORT: 1883,
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
        MQTT_TRANSPORT: "tcp",
        CONF_DISCOVERY: True,
    }
    assert len(mock_try_connection.mock_calls) == 1
    assert len(mock_is_available.mock_calls) == 1


async def test_inels_option_flow(hass: HomeAssistant, mock_try_connection) -> None:
    """Test config flow options of inels."""
    MockConfigEntry(domain=inels.DOMAIN, data={}).add_to_hass(hass)

    mock_try_connection.return_value = True
    config_entry = hass.config_entries.async_entries(inels.DOMAIN)[0]
    config_entry.data = {
        CONF_HOST: "test-mqtt",
        CONF_PORT: 1883,
        MQTT_TRANSPORT: "tcp",
    }
    # setup option form
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result[CONF_TYPE] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "setup"
    assert result["handler"] == config_entry.entry_id

    mock_try_connection.return_value = False
    # init entry with connection failed
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "another-mqtt-broker",
            CONF_PORT: 2883,
            MQTT_TRANSPORT: "tcp",
        },
    )
    assert result[CONF_TYPE] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "setup"

    mock_try_connection.return_value = True

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "another-mqtt-broker-with-auth",
            CONF_PORT: 2883,
            CONF_USERNAME: "user-new",
            CONF_PASSWORD: "pass-new",
            MQTT_TRANSPORT: "tcp",
        },
    )
    assert result[CONF_TYPE] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert "step_id" not in result

    await hass.async_block_till_done()
    assert mock_try_connection.call_count == 2
