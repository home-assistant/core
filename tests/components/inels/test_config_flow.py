"""Test config flow."""
from collections.abc import Callable
from typing import Any, TypeVar
from unittest.mock import patch

from inelsmqtt import InelsMqtt
from inelsmqtt.const import MQTT_TRANSPORT
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import inels
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.components.inels.config_flow import (
    FlowHandler,
    InelsOptionsFlowHandler,
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

_T = TypeVar("_T")


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


async def fake_async_step_setup(self):
    """Mock the async_step_setup method."""
    return data_entry_flow.FlowResult


@pytest.fixture
def mock_async_step_setup():
    """Mock the async_step_setup method."""
    with patch.object(
        InelsOptionsFlowHandler,
        "async_step_setup",
        fake_async_step_setup,
    ) as mock_try:
        yield mock_try


@pytest.fixture
def mock_mqtt_client():
    """Mock mqtt client."""

    def enable_logger():
        """Enable logger."""

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

    def test_connection(self):
        """Mock test_connection the method."""
        return False

    with patch.object(InelsMqtt, "test_connection", test_connection) as mock_try:
        yield mock_try


@pytest.fixture
def mock_inels_options_flow_handler():
    """Mock the InelsOptionFlowHandler class."""

    with patch(
        "homeassistant.components.inels.config_flow.InelsOptionsFlowHandler",
        autospec=True,
    ) as mock_try:
        yield mock_try


@pytest.fixture
def mock_hass_success():
    """Mock a failure of the try_connect function by mocking the HomeAssistant class."""

    async def fake_async_executor_job(self, target: Callable[..., _T], *args: Any):
        """Mock the async_executor_job method of HomeAssistant."""
        return True

    with patch.object(
        HomeAssistant, "async_add_executor_job", fake_async_executor_job
    ) as mock_home_assistant:
        yield mock_home_assistant


@pytest.fixture
def mock_hass_fail():
    """Mock a failure of the try_connect function by mocking the HomeAssistant class."""

    async def fake_async_executor_job(self, target: Callable[..., _T], *args: Any):
        return False

    with patch.object(
        HomeAssistant, "async_add_executor_job", fake_async_executor_job
    ) as mock_home_assistant:
        yield mock_home_assistant


@pytest.fixture
def mock_hass():
    """Mock HomeAssistant class method."""  # TODO finish

    async def fake_async_executor_job(self, target: Callable[..., _T], *args: Any):
        return False

    with patch("paho.mqtt.client.Client") as mqtt:
        mqtt().async_executor_job = fake_async_executor_job
        yield mqtt()


@pytest.fixture
def mock_config_entries():
    """Mock config entries."""

    async def fake_async_update_entry(
        self, entry: config_entries.ConfigEntry, *args: Any
    ):
        return False

    with patch.object(
        config_entries.ConfigEntries, "async_update_entry", fake_async_update_entry
    ) as update_entry:
        yield update_entry()


async def test_user_config_flow_finished_successfully(
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


async def test_use_config_flow_finished_failed(
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


async def test_options_flow_handler_init():
    """Test the InelsOptionsFlowHandler init constructor."""
    mock = MockConfigEntry(domain=inels.DOMAIN)
    flow_handler = InelsOptionsFlowHandler(mock)
    assert flow_handler.config_entry == mock
    assert not flow_handler.broker_config
    assert flow_handler.options == dict(flow_handler.config_entry.options)


async def test_async_step_init(mock_async_step_setup):
    """Test the async_step_init method of the InelsOptionsFlowHandler."""
    mock = MockConfigEntry(domain=inels.DOMAIN)
    flow_handler = InelsOptionsFlowHandler(mock)

    flow_result = data_entry_flow.FlowResult

    res = await flow_handler.async_step_init()
    assert res == flow_result


async def test_inels_flow_handler_async_step_setup_success(mock_hass):
    """Test the async_step_setup method of InelsOptionsFlowHandler when the connection is a success."""
    # mock_hass returns a success to the connection attempt, leading to the cannot_connect error
    mock = MockConfigEntry(domain=inels.DOMAIN)
    flow_handler = InelsOptionsFlowHandler(mock)
    flow_handler.hass = HomeAssistant()
    flow_handler.hass.config_entries = config_entries.ConfigEntries(
        flow_handler.hass, None
    )
    res = await flow_handler.async_step_setup(
        user_input=dict(
            {
                CONF_HOST: "127.0.0.1",
                CONF_PORT: 1883,
                CONF_USERNAME: "test",
                CONF_PASSWORD: "pwd",
                MQTT_TRANSPORT: "tcp",
            }
        )
    )

    assert res["data"] == dict(
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 1883,
            CONF_USERNAME: "test",
            CONF_PASSWORD: "pwd",
            MQTT_TRANSPORT: "tcp",
            CONF_DISCOVERY: True,
        }
    )


async def test_inels_flow_handler_async_step_setup_fail(mock_hass_fail):
    """Test the async_step_setup method of InelsOptionsFlowHandler when the connection is a failure."""
    # mock_hass returns a failure to the connection attempt, leading to the cannot_connect error

    mock = MockConfigEntry(domain=inels.DOMAIN)
    flow_handler = InelsOptionsFlowHandler(mock)
    flow_handler.hass = HomeAssistant()
    res = await flow_handler.async_step_setup(
        user_input=dict(
            {
                CONF_HOST: "127.0.0.1",
                CONF_PORT: 1883,
                CONF_USERNAME: "test",
                CONF_PASSWORD: "pwd",
                MQTT_TRANSPORT: "tcp",
            }
        )
    )

    assert res[CONF_TYPE] == "form"
    assert res["errors"]["base"] == "cannot_connect"


async def test_async_get_options_flow(mock_inels_options_flow_handler):
    """Test the async_get_options_flow method of the FlowHandler class."""

    mock = MockConfigEntry(domain=inels.DOMAIN)

    FlowHandler.async_get_options_flow(mock)
    mock_inels_options_flow_handler.assert_called_with(config_entry=mock)


async def test_try_connection(mock_mqtt_client_test_connection):
    """Test the try_connection function."""

    config = {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 1883,
        CONF_USERNAME: "test",
        CONF_PASSWORD: "pwd",
        MQTT_TRANSPORT: "tcp",
    }

    assert not try_connection(
        None,
        config[CONF_HOST],
        config[CONF_PORT],
        config[CONF_USERNAME],
        config[CONF_PASSWORD],
        config[MQTT_TRANSPORT],
    )


async def test_async_step_confirm_cannot_connect(
    hass: HomeAssistant, mock_try_connection, mock_hass_fail
):
    """Test the async_step_confirm method if it fails to connect."""

    mock_try_connection.return_value = False

    config: dict[str, Any] = {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 1883,
        CONF_USERNAME: "test",
        CONF_PASSWORD: "pwd",
        MQTT_TRANSPORT: "tcp",
        "addon": "addon placeholder",
    }

    flow_handler = FlowHandler()
    flow_handler.hass = HomeAssistant()
    flow_handler._hassio_discovery = config
    result = await flow_handler.async_step_confirm(config)

    assert result[CONF_TYPE] == "form"
    assert result["errors"]["base"] == "cannot_connect"
