"""Test config flow."""
from unittest.mock import patch

from inelsmqtt import InelsMqtt
from inelsmqtt.const import MQTT_TRANSPORT
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import inels
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.components.inels.config_flow import (
    connect_val_to_error,
    try_connection,
)
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
        "inelsmqtt.InelsMqtt.test_connection", return_value=None
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


@pytest.fixture
def mock_mqtt_client_test_connection():
    """Mock mqtt client."""

    def test_connection(self) -> None:
        """Mock test_connection the method."""
        return 6  # leads to unknown error

    with patch.object(InelsMqtt, "test_connection", test_connection) as mock_try:
        yield mock_try


async def test_user_config_flow_finished_successfully(
    hass: HomeAssistant, mock_try_connection
) -> None:
    """Test if we can finish config flow."""
    mock_try_connection.return_value = None

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


async def test_use_config_flow_finished_failed(
    hass: HomeAssistant, mock_try_connection
) -> None:
    """Test if connection failed."""
    mock_try_connection.return_value = 6

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
    assert result["errors"]["base"] == "unknown"

    assert len(mock_try_connection.mock_calls) == 1


async def test_config_setup(
    hass: HomeAssistant, mock_try_connection, mock_is_available
) -> None:
    """Test configuration."""
    mock_try_connection.return_value = None

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
            },
            name="Mosquitto",
            slug="mosquitto",
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
) -> None:
    """Test we can finish a config flow."""
    mock_try_connection.return_value = None

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
            },
            name="Mock addon",
            slug="mock-slug",
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


async def test_hassio_fail(hass: HomeAssistant, mock_try_connection) -> None:
    """Test we can get the error when the connection can not be made."""
    mock_try_connection.return_value = 6

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
            },
            name="Mock addon",
            slug="mock-slug",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )

    assert result[CONF_TYPE] == "form"
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"addon": "Mock Addon"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"discovery": True}
    )

    assert result["errors"]["base"] == "unknown"


async def test_try_connection(mock_mqtt_client_test_connection) -> None:
    """Test the try_connection function."""

    config = {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 1883,
        CONF_USERNAME: "test",
        CONF_PASSWORD: "pwd",
        MQTT_TRANSPORT: "tcp",
    }

    assert (
        try_connection(
            None,
            config[CONF_HOST],
            config[CONF_PORT],
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            config[MQTT_TRANSPORT],
        )
        == 6
    )  # checks that the correct value is propagated


async def test_test_connect_to_error() -> None:
    """Test the test_connect function."""
    assert connect_val_to_error(1) == "mqtt_version"

    assert connect_val_to_error(None) == "unknown"
