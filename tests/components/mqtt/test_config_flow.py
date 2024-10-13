"""Test config flow."""

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from ssl import SSLError
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from aiohasupervisor import SupervisorError
import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.components.hassio import (
    AddonError,
    HassioAPIError,
    HassioServiceInfo,
)
from homeassistant.components.mqtt.config_flow import PWD_NOT_CHANGED
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient

ADD_ON_DISCOVERY_INFO = {
    "addon": "Mosquitto Mqtt Broker",
    "host": "core-mosquitto",
    "port": 1883,
    "username": "mock-user",
    "password": "mock-pass",
    "protocol": "3.1.1",
    "ssl": False,
}
MOCK_CLIENT_CERT = b"## mock client certificate file ##"
MOCK_CLIENT_KEY = b"## mock key file ##"


@pytest.fixture(autouse=True)
def mock_finish_setup() -> Generator[MagicMock]:
    """Mock out the finish setup method."""
    with patch(
        "homeassistant.components.mqtt.MQTT.async_connect", return_value=True
    ) as mock_finish:
        yield mock_finish


@pytest.fixture
def mock_client_cert_check_fail() -> Generator[MagicMock]:
    """Mock the client certificate check."""
    with patch(
        "homeassistant.components.mqtt.config_flow.load_pem_x509_certificate",
        side_effect=ValueError,
    ) as mock_cert_check:
        yield mock_cert_check


@pytest.fixture
def mock_client_key_check_fail() -> Generator[MagicMock]:
    """Mock the client key file check."""
    with patch(
        "homeassistant.components.mqtt.config_flow.load_pem_private_key",
        side_effect=ValueError,
    ) as mock_key_check:
        yield mock_key_check


@pytest.fixture
def mock_ssl_context() -> Generator[dict[str, MagicMock]]:
    """Mock the SSL context used to load the cert chain and to load verify locations."""
    with (
        patch("homeassistant.components.mqtt.config_flow.SSLContext") as mock_context,
        patch(
            "homeassistant.components.mqtt.config_flow.load_pem_private_key"
        ) as mock_key_check,
        patch(
            "homeassistant.components.mqtt.config_flow.load_pem_x509_certificate"
        ) as mock_cert_check,
    ):
        yield {
            "context": mock_context,
            "load_pem_x509_certificate": mock_cert_check,
            "load_pem_private_key": mock_key_check,
        }


@pytest.fixture
def mock_reload_after_entry_update() -> Generator[MagicMock]:
    """Mock out the reload after updating the entry."""
    with patch(
        "homeassistant.components.mqtt._async_config_entry_updated"
    ) as mock_reload:
        yield mock_reload


@pytest.fixture
def mock_try_connection() -> Generator[MagicMock]:
    """Mock the try connection method."""
    with patch("homeassistant.components.mqtt.config_flow.try_connection") as mock_try:
        yield mock_try


@pytest.fixture
def mock_try_connection_success() -> Generator[MqttMockPahoClient]:
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

    with patch(
        "homeassistant.components.mqtt.async_client.AsyncMQTTClient"
    ) as mock_client:
        mock_client().loop_start = loop_start
        mock_client().subscribe = _subscribe
        mock_client().unsubscribe = _unsubscribe

        yield mock_client()


@pytest.fixture
def mock_try_connection_time_out() -> Generator[MagicMock]:
    """Mock the try connection method with a time out."""

    # Patch prevent waiting 5 sec for a timeout
    with (
        patch(
            "homeassistant.components.mqtt.async_client.AsyncMQTTClient"
        ) as mock_client,
        patch("homeassistant.components.mqtt.config_flow.MQTT_TIMEOUT", 0),
    ):
        mock_client().loop_start = lambda *args: 1
        yield mock_client()


@pytest.fixture
def mock_process_uploaded_file(
    tmp_path: Path, mock_temp_dir: str
) -> Generator[MagicMock]:
    """Mock upload certificate files."""
    file_id_ca = str(uuid4())
    file_id_cert = str(uuid4())
    file_id_key = str(uuid4())

    @contextmanager
    def _mock_process_uploaded_file(
        hass: HomeAssistant, file_id: str
    ) -> Iterator[Path | None]:
        if file_id == file_id_ca:
            with open(tmp_path / "ca.crt", "wb") as cafile:
                cafile.write(b"## mock CA certificate file ##")
            yield tmp_path / "ca.crt"
        elif file_id == file_id_cert:
            with open(tmp_path / "client.crt", "wb") as certfile:
                certfile.write(b"## mock client certificate file ##")
            yield tmp_path / "client.crt"
        elif file_id == file_id_key:
            with open(tmp_path / "client.key", "wb") as keyfile:
                keyfile.write(b"## mock key file ##")
            yield tmp_path / "client.key"
        else:
            pytest.fail(f"Unexpected file_id: {file_id}")

    with patch(
        "homeassistant.components.mqtt.config_flow.process_uploaded_file",
        side_effect=_mock_process_uploaded_file,
    ) as mock_upload:
        mock_upload.file_id = {
            mqtt.CONF_CERTIFICATE: file_id_ca,
            mqtt.CONF_CLIENT_CERT: file_id_cert,
            mqtt.CONF_CLIENT_KEY: file_id_key,
        }
        yield mock_upload


@pytest.fixture(name="supervisor")
def supervisor_fixture() -> Generator[MagicMock]:
    """Mock Supervisor."""
    with patch(
        "homeassistant.components.mqtt.config_flow.is_hassio", return_value=True
    ) as is_hassio:
        yield is_hassio


@pytest.fixture(name="addon_setup_time", autouse=True)
def addon_setup_time_fixture() -> Generator[int]:
    """Mock add-on setup sleep time."""
    with patch(
        "homeassistant.components.mqtt.config_flow.ADDON_SETUP_TIMEOUT", new=0
    ) as addon_setup_time:
        yield addon_setup_time


@pytest.fixture(autouse=True)
def mock_get_addon_discovery_info(get_addon_discovery_info: AsyncMock) -> None:
    """Mock get add-on discovery info."""


@pytest.mark.usefixtures("mqtt_client_mock")
async def test_user_connection_works(
    hass: HomeAssistant,
    mock_try_connection: MagicMock,
    mock_finish_setup: MagicMock,
) -> None:
    """Test we can finish a config flow."""
    mock_try_connection.return_value = True

    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"broker": "127.0.0.1"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        "broker": "127.0.0.1",
        "port": 1883,
        "discovery": True,
    }
    # Check we tried the connection
    assert len(mock_try_connection.mock_calls) == 1
    # Check config entry got setup
    assert len(mock_finish_setup.mock_calls) == 1


@pytest.mark.usefixtures("mqtt_client_mock", "supervisor")
async def test_user_connection_works_with_supervisor(
    hass: HomeAssistant,
    mock_try_connection: MagicMock,
    mock_finish_setup: MagicMock,
) -> None:
    """Test we can finish a config flow with a supervised install."""
    mock_try_connection.return_value = True

    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["addon", "broker"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "broker"},
    )

    # Assert a manual setup flow
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"broker": "127.0.0.1"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        "broker": "127.0.0.1",
        "port": 1883,
        "discovery": True,
    }
    # Check we tried the connection
    assert len(mock_try_connection.mock_calls) == 1
    # Check config entry got setup
    assert len(mock_finish_setup.mock_calls) == 1
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.usefixtures("mqtt_client_mock")
async def test_user_v5_connection_works(
    hass: HomeAssistant,
    mock_try_connection: MagicMock,
    mock_finish_setup: MagicMock,
) -> None:
    """Test we can finish a config flow."""
    mock_try_connection.return_value = True

    result = await hass.config_entries.flow.async_init(
        "mqtt",
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": True},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"broker": "127.0.0.1", "advanced_options": True}
    )

    assert result["step_id"] == "broker"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "another-broker",
            CONF_PORT: 2345,
            CONF_PROTOCOL: "5",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        "broker": "another-broker",
        "discovery": True,
        "port": 2345,
        "protocol": "5",
    }
    # Check we tried the connection
    assert len(mock_try_connection.mock_calls) == 1
    # Check config entry got setup
    assert len(mock_finish_setup.mock_calls) == 1


async def test_user_connection_fails(
    hass: HomeAssistant,
    mock_try_connection_time_out: MagicMock,
    mock_finish_setup: MagicMock,
) -> None:
    """Test if connection cannot be made."""
    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"broker": "127.0.0.1"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"

    # Check we tried the connection
    assert len(mock_try_connection_time_out.mock_calls)
    # Check config entry did not setup
    assert len(mock_finish_setup.mock_calls) == 0


@pytest.mark.parametrize("hass_config", [{"mqtt": {"sensor": {"state_topic": "test"}}}])
async def test_manual_config_set(
    hass: HomeAssistant,
    mock_try_connection: MqttMockPahoClient,
    mock_finish_setup: MagicMock,
) -> None:
    """Test manual config does not create an entry, and entry can be setup late."""
    assert len(mock_finish_setup.mock_calls) == 0

    mock_try_connection.return_value = True

    # Start config flow
    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"broker": "127.0.0.1", "port": "1883"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        "broker": "127.0.0.1",
        "port": 1883,
        "discovery": True,
    }
    # Check we tried the connection, with precedence for config entry settings
    mock_try_connection.assert_called_once_with(
        {
            "broker": "127.0.0.1",
            "port": 1883,
            "discovery": True,
        },
    )
    # Check config entry got setup
    assert len(mock_finish_setup.mock_calls) == 1
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    assert config_entry.title == "127.0.0.1"


async def test_user_single_instance(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(domain="mqtt").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_hassio_already_configured(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(domain="mqtt").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_HASSIO}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


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
            },
            name="Mosquitto",
            slug="mosquitto",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_hassio_confirm(
    hass: HomeAssistant,
    mock_try_connection_success: MqttMockPahoClient,
    mock_finish_setup: MagicMock,
) -> None:
    """Test we can finish a config flow."""
    mock_try_connection.return_value = True

    result = await hass.config_entries.flow.async_init(
        "mqtt",
        data=HassioServiceInfo(
            config=ADD_ON_DISCOVERY_INFO.copy(),
            name="Mosquitto Mqtt Broker",
            slug="mosquitto",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"
    assert result["description_placeholders"] == {"addon": "Mosquitto Mqtt Broker"}

    mock_try_connection_success.reset_mock()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"discovery": True}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        "broker": "core-mosquitto",
        "port": 1883,
        "username": "mock-user",
        "password": "mock-pass",
        "discovery": True,
    }
    # Check we tried the connection
    assert len(mock_try_connection_success.mock_calls)
    # Check config entry got setup
    assert len(mock_finish_setup.mock_calls) == 1


async def test_hassio_cannot_connect(
    hass: HomeAssistant,
    mock_try_connection_time_out: MagicMock,
    mock_finish_setup: MagicMock,
) -> None:
    """Test a config flow is aborted when a connection was not successful."""
    result = await hass.config_entries.flow.async_init(
        "mqtt",
        data=HassioServiceInfo(
            config={
                "addon": "Mock Addon",
                "host": "core-mosquitto",
                "port": 1883,
                "username": "mock-user",
                "password": "mock-pass",
                "protocol": "3.1.1",  # Set by the addon's discovery, ignored by HA
                "ssl": False,  # Set by the addon's discovery, ignored by HA
            },
            name="Mock Addon",
            slug="mosquitto",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"
    assert result["description_placeholders"] == {"addon": "Mock Addon"}

    mock_try_connection_time_out.reset_mock()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"discovery": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"
    # Check we tried the connection
    assert len(mock_try_connection_time_out.mock_calls)
    # Check config entry got setup
    assert len(mock_finish_setup.mock_calls) == 0


@pytest.mark.usefixtures(
    "mqtt_client_mock", "supervisor", "addon_info", "addon_running"
)
@pytest.mark.parametrize("discovery_info", [{"config": ADD_ON_DISCOVERY_INFO.copy()}])
async def test_addon_flow_with_supervisor_addon_running(
    hass: HomeAssistant,
    mock_try_connection_success: MagicMock,
    mock_finish_setup: MagicMock,
) -> None:
    """Test we perform an auto config flow with a supervised install.

    Case: The Mosquitto add-on is already installed, and running.
    """
    # show menu
    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["addon", "broker"]
    assert result["step_id"] == "user"

    # select install via add-on
    mock_try_connection_success.reset_mock()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "addon"},
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        "broker": "core-mosquitto",
        "port": 1883,
        "username": "mock-user",
        "password": "mock-pass",
        "discovery": True,
    }
    # Check we tried the connection
    assert len(mock_try_connection_success.mock_calls)
    # Check config entry got setup
    assert len(mock_finish_setup.mock_calls) == 1


@pytest.mark.usefixtures(
    "mqtt_client_mock", "supervisor", "addon_info", "addon_installed", "start_addon"
)
@pytest.mark.parametrize("discovery_info", [{"config": ADD_ON_DISCOVERY_INFO.copy()}])
async def test_addon_flow_with_supervisor_addon_installed(
    hass: HomeAssistant,
    mock_try_connection_success: MagicMock,
    mock_finish_setup: MagicMock,
) -> None:
    """Test we perform an auto config flow with a supervised install.

    Case: The Mosquitto add-on is installed, but not running.
    """
    # show menu
    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["addon", "broker"]
    assert result["step_id"] == "user"

    # select install via add-on
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "addon"},
    )

    # add-on installed but not started, so we wait for start-up
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "start_addon"
    assert result["step_id"] == "start_addon"
    await hass.async_block_till_done()
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_try_connection_success.reset_mock()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "start_addon"},
    )

    # add-on is running, so entry can be installed
    await hass.async_block_till_done(wait_background_tasks=True)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        "broker": "core-mosquitto",
        "port": 1883,
        "username": "mock-user",
        "password": "mock-pass",
        "discovery": True,
    }
    # Check we tried the connection
    assert len(mock_try_connection_success.mock_calls)
    # Check config entry got setup
    assert len(mock_finish_setup.mock_calls) == 1


@pytest.mark.usefixtures(
    "mqtt_client_mock", "supervisor", "addon_info", "addon_running"
)
@pytest.mark.parametrize("discovery_info", [{"config": ADD_ON_DISCOVERY_INFO.copy()}])
async def test_addon_flow_with_supervisor_addon_running_connection_fails(
    hass: HomeAssistant,
    mock_try_connection: MagicMock,
) -> None:
    """Test we perform an auto config flow with a supervised install.

    Case: The Mosquitto add-on is already installed, and running.
    """
    # show menu
    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["addon", "broker"]
    assert result["step_id"] == "user"

    # select install via add-on but the connection fails and the flow will be aborted.
    mock_try_connection.return_value = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "addon"},
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert result["type"] is FlowResultType.ABORT


@pytest.mark.usefixtures(
    "mqtt_client_mock",
    "supervisor",
    "addon_info",
    "addon_installed",
)
async def test_addon_not_running_api_error(
    hass: HomeAssistant,
    start_addon: AsyncMock,
) -> None:
    """Test we perform an auto config flow with a supervised install.

    Case: The Mosquitto add-on start fails on a API error.
    """
    start_addon.side_effect = SupervisorError()

    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["addon", "broker"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "addon"},
    )
    # add-on not installed, so we wait for install
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "start_addon"
    assert result["step_id"] == "start_addon"
    await hass.async_block_till_done()
    await hass.async_block_till_done(wait_background_tasks=True)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "install_addon"},
    )

    # add-on start-up failed
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_start_failed"


@pytest.mark.usefixtures(
    "mqtt_client_mock",
    "supervisor",
    "start_addon",
    "addon_installed",
)
async def test_addon_discovery_info_error(
    hass: HomeAssistant,
    addon_info: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test we perform an auto config flow with a supervised install.

    Case: The Mosquitto add-on start on a discovery error.
    """
    get_addon_discovery_info.side_effect = AddonError

    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["addon", "broker"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "addon"},
    )
    # Addon will retry
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "start_addon"
    assert result["step_id"] == "start_addon"
    await hass.async_block_till_done()
    await hass.async_block_till_done(wait_background_tasks=True)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "start_addon"},
    )

    # add-on start-up failed
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_start_failed"


@pytest.mark.usefixtures(
    "mqtt_client_mock",
    "supervisor",
    "start_addon",
    "addon_installed",
)
async def test_addon_info_error(
    hass: HomeAssistant,
    addon_info: AsyncMock,
) -> None:
    """Test we perform an auto config flow with a supervised install.

    Case: The Mosquitto add-on info could not be retrieved.
    """
    addon_info.side_effect = SupervisorError()

    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["addon", "broker"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "addon"},
    )

    # add-on info failed
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_info_failed"


@pytest.mark.usefixtures(
    "mqtt_client_mock",
    "supervisor",
    "addon_info",
    "addon_not_installed",
    "install_addon",
    "start_addon",
)
@pytest.mark.parametrize("discovery_info", [{"config": ADD_ON_DISCOVERY_INFO.copy()}])
async def test_addon_flow_with_supervisor_addon_not_installed(
    hass: HomeAssistant,
    mock_try_connection_success: MagicMock,
    mock_finish_setup: MagicMock,
) -> None:
    """Test we perform an auto config flow with a supervised install.

    Case: The Mosquitto add-on is not yet installed nor running.
    """
    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["addon", "broker"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "addon"},
    )
    # add-on not installed, so we wait for install
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "install_addon"
    assert result["step_id"] == "install_addon"
    await hass.async_block_till_done()
    await hass.async_block_till_done(wait_background_tasks=True)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "install_addon"},
    )

    # add-on installed but not started, so we wait for start-up
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "start_addon"
    assert result["step_id"] == "start_addon"
    await hass.async_block_till_done()
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_try_connection_success.reset_mock()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "start_addon"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        "broker": "core-mosquitto",
        "port": 1883,
        "username": "mock-user",
        "password": "mock-pass",
        "discovery": True,
    }
    # Check we tried the connection
    assert len(mock_try_connection_success.mock_calls)
    # Check config entry got setup
    assert len(mock_finish_setup.mock_calls) == 1


@pytest.mark.usefixtures(
    "mqtt_client_mock",
    "supervisor",
    "addon_info",
    "addon_not_installed",
    "start_addon",
)
async def test_addon_not_installed_failures(
    hass: HomeAssistant,
    install_addon: AsyncMock,
) -> None:
    """Test we perform an auto config flow with a supervised install.

    Case: The Mosquitto add-on install fails.
    """
    install_addon.side_effect = HassioAPIError()

    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["addon", "broker"]
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "addon"},
    )
    # add-on not installed, so we wait for install
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "install_addon"
    assert result["step_id"] == "install_addon"
    await hass.async_block_till_done()
    await hass.async_block_till_done(wait_background_tasks=True)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "install_addon"},
    )

    # add-on install failed
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_install_failed"


async def test_option_flow(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mock_try_connection: MagicMock,
) -> None:
    """Test config flow options."""
    with patch(
        "homeassistant.config.async_hass_config_yaml", AsyncMock(return_value={})
    ) as yaml_mock:
        mqtt_mock = await mqtt_mock_entry()
        mock_try_connection.return_value = True
        config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                mqtt.CONF_BROKER: "test-broker",
                CONF_PORT: 1234,
            },
        )

        mqtt_mock.async_connect.reset_mock()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "broker"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                mqtt.CONF_BROKER: "another-broker",
                CONF_PORT: 2345,
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "options"

        await hass.async_block_till_done()
        assert mqtt_mock.async_connect.call_count == 0

        yaml_mock.reset_mock()

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                mqtt.CONF_DISCOVERY: True,
                "discovery_prefix": "homeassistant",
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
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {}
        assert config_entry.data == {
            mqtt.CONF_BROKER: "another-broker",
            CONF_PORT: 2345,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            mqtt.CONF_DISCOVERY: True,
            mqtt.CONF_DISCOVERY_PREFIX: "homeassistant",
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
        assert config_entry.title == "another-broker"
    # assert that the entry was reloaded with the new config
    assert yaml_mock.await_count


@pytest.mark.parametrize(
    "test_error",
    [
        "bad_certificate",
        "bad_client_cert",
        "bad_client_key",
        "bad_client_cert_key",
        "invalid_inclusion",
        None,
    ],
)
async def test_bad_certificate(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mock_try_connection_success: MqttMockPahoClient,
    mock_ssl_context: dict[str, MagicMock],
    mock_process_uploaded_file: MagicMock,
    test_error: str | None,
) -> None:
    """Test bad certificate tests."""
    # Mock certificate files
    file_id = mock_process_uploaded_file.file_id
    test_input = {
        mqtt.CONF_BROKER: "another-broker",
        CONF_PORT: 2345,
        mqtt.CONF_CERTIFICATE: file_id[mqtt.CONF_CERTIFICATE],
        mqtt.CONF_CLIENT_CERT: file_id[mqtt.CONF_CLIENT_CERT],
        mqtt.CONF_CLIENT_KEY: file_id[mqtt.CONF_CLIENT_KEY],
        "set_ca_cert": True,
        "set_client_cert": True,
    }
    set_client_cert = True
    set_ca_cert = "custom"
    tls_insecure = False
    if test_error == "bad_certificate":
        # CA chain is not loading
        mock_ssl_context["context"]().load_verify_locations.side_effect = SSLError
    elif test_error == "bad_client_cert":
        # Client certificate is invalid
        mock_ssl_context["load_pem_x509_certificate"].side_effect = ValueError
    elif test_error == "bad_client_key":
        # Client key file is invalid
        mock_ssl_context["load_pem_private_key"].side_effect = ValueError
    elif test_error == "bad_client_cert_key":
        # Client key file file and certificate do not pair
        mock_ssl_context["context"]().load_cert_chain.side_effect = SSLError
    elif test_error == "invalid_inclusion":
        # Client key file without client cert, client cert without key file
        test_input.pop(mqtt.CONF_CLIENT_KEY)

    mqtt_mock = await mqtt_mock_entry()
    mock_try_connection.return_value = True
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    # Add at least one advanced option to get the full form
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
            CONF_CLIENT_ID: "custom1234",
            mqtt.CONF_KEEPALIVE: 60,
            mqtt.CONF_TLS_INSECURE: False,
            CONF_PROTOCOL: "3.1.1",
        },
    )
    await hass.async_block_till_done()

    mqtt_mock.async_connect.reset_mock()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "another-broker",
            CONF_PORT: 2345,
            mqtt.CONF_KEEPALIVE: 60,
            "set_client_cert": set_client_cert,
            "set_ca_cert": set_ca_cert,
            mqtt.CONF_TLS_INSECURE: tls_insecure,
            CONF_PROTOCOL: "3.1.1",
            CONF_CLIENT_ID: "custom1234",
        },
    )
    test_input["set_client_cert"] = set_client_cert
    test_input["set_ca_cert"] = set_ca_cert
    test_input["tls_insecure"] = tls_insecure

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=test_input,
    )
    if test_error is not None:
        assert result["errors"]["base"] == test_error
        return
    assert result["errors"] == {}


@pytest.mark.parametrize(
    ("input_value", "error"),
    [
        ("", True),
        ("-10", True),
        ("10", True),
        ("15", False),
        ("26", False),
        ("100", False),
    ],
)
@pytest.mark.usefixtures("mock_reload_after_entry_update")
async def test_keepalive_validation(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mock_try_connection: MagicMock,
    input_value: str,
    error: bool,
) -> None:
    """Test validation of the keep alive option."""

    test_input = {
        mqtt.CONF_BROKER: "another-broker",
        CONF_PORT: 2345,
        mqtt.CONF_KEEPALIVE: input_value,
    }

    mqtt_mock = await mqtt_mock_entry()
    mock_try_connection.return_value = True
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    # Add at least one advanced option to get the full form
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
            CONF_CLIENT_ID: "custom1234",
        },
    )

    mqtt_mock.async_connect.reset_mock()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"

    if error:
        with pytest.raises(vol.Invalid):
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                user_input=test_input,
            )
        return
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=test_input,
    )
    assert not result["errors"]


async def test_disable_birth_will(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mock_try_connection: MagicMock,
    mock_reload_after_entry_update: MagicMock,
) -> None:
    """Test disabling birth and will."""
    mqtt_mock = await mqtt_mock_entry()
    mock_try_connection.return_value = True
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
        },
    )
    await hass.async_block_till_done()
    mock_reload_after_entry_update.reset_mock()

    mqtt_mock.async_connect.reset_mock()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "another-broker",
            CONF_PORT: 2345,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "options"

    await hass.async_block_till_done()
    assert mqtt_mock.async_connect.call_count == 0

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_DISCOVERY: True,
            mqtt.CONF_DISCOVERY_PREFIX: "homeassistant",
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
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert config_entry.data == {
        mqtt.CONF_BROKER: "another-broker",
        CONF_PORT: 2345,
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
        mqtt.CONF_DISCOVERY: True,
        mqtt.CONF_DISCOVERY_PREFIX: "homeassistant",
        mqtt.CONF_BIRTH_MESSAGE: {},
        mqtt.CONF_WILL_MESSAGE: {},
    }

    await hass.async_block_till_done()
    # assert that the entry was reloaded with the new config
    assert mock_reload_after_entry_update.call_count == 1


async def test_invalid_discovery_prefix(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mock_try_connection: MagicMock,
    mock_reload_after_entry_update: MagicMock,
) -> None:
    """Test setting an invalid discovery prefix."""
    mqtt_mock = await mqtt_mock_entry()
    mock_try_connection.return_value = True
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
            mqtt.CONF_DISCOVERY: True,
            mqtt.CONF_DISCOVERY_PREFIX: "homeassistant",
        },
    )
    await hass.async_block_till_done()
    mock_reload_after_entry_update.reset_mock()
    mqtt_mock.async_connect.reset_mock()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "another-broker",
            CONF_PORT: 2345,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "options"

    await hass.async_block_till_done()
    assert mqtt_mock.async_connect.call_count == 0

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_DISCOVERY: True,
            mqtt.CONF_DISCOVERY_PREFIX: "homeassistant#invalid",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "options"
    assert result["errors"]["base"] == "bad_discovery_prefix"
    assert config_entry.data == {
        mqtt.CONF_BROKER: "test-broker",
        CONF_PORT: 1234,
        mqtt.CONF_DISCOVERY: True,
        mqtt.CONF_DISCOVERY_PREFIX: "homeassistant",
    }

    await hass.async_block_till_done()
    # assert that the entry was not reloaded with the new config
    assert mock_reload_after_entry_update.call_count == 0


def get_default(schema: vol.Schema, key: str) -> Any | None:
    """Get default value for key in voluptuous schema."""
    for schema_key in schema:
        if schema_key == key:
            if schema_key.default == vol.UNDEFINED:
                return None
            return schema_key.default()
    return None


def get_suggested(schema: vol.Schema, key: str) -> Any | None:
    """Get suggested value for key in voluptuous schema."""
    for schema_key in schema:
        if schema_key == key:
            if (
                schema_key.description is None
                or "suggested_value" not in schema_key.description
            ):
                return None
            return schema_key.description["suggested_value"]
    return None


@pytest.mark.usefixtures("mock_reload_after_entry_update")
async def test_option_flow_default_suggested_values(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mock_try_connection_success: MqttMockPahoClient,
) -> None:
    """Test config flow options has default/suggested values."""
    await mqtt_mock_entry()
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
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
        },
    )

    # Test default/suggested values from config
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"
    defaults = {
        mqtt.CONF_BROKER: "test-broker",
        CONF_PORT: 1234,
    }
    suggested = {
        CONF_USERNAME: "user",
        CONF_PASSWORD: PWD_NOT_CHANGED,
    }
    for key, value in defaults.items():
        assert get_default(result["data_schema"].schema, key) == value
    for key, value in suggested.items():
        assert get_suggested(result["data_schema"].schema, key) == value

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "another-broker",
            CONF_PORT: 2345,
            CONF_USERNAME: "us3r",
            CONF_PASSWORD: "p4ss",
        },
    )
    assert result["type"] is FlowResultType.FORM
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
    for key, value in defaults.items():
        assert get_default(result["data_schema"].schema, key) == value
    for key, value in suggested.items():
        assert get_suggested(result["data_schema"].schema, key) == value

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
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Test updated default/suggested values from config
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"
    defaults = {
        mqtt.CONF_BROKER: "another-broker",
        CONF_PORT: 2345,
    }
    suggested = {
        CONF_USERNAME: "us3r",
        CONF_PASSWORD: PWD_NOT_CHANGED,
    }
    for key, value in defaults.items():
        assert get_default(result["data_schema"].schema, key) == value
    for key, value in suggested.items():
        assert get_suggested(result["data_schema"].schema, key) == value

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={mqtt.CONF_BROKER: "another-broker", CONF_PORT: 2345},
    )
    assert result["type"] is FlowResultType.FORM
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
    for key, value in defaults.items():
        assert get_default(result["data_schema"].schema, key) == value
    for key, value in suggested.items():
        assert get_suggested(result["data_schema"].schema, key) == value

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
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Make sure all MQTT related jobs are done before ending the test
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("advanced_options", "step_id"), [(False, "options"), (True, "broker")]
)
@pytest.mark.usefixtures("mock_reload_after_entry_update")
async def test_skipping_advanced_options(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mock_try_connection: MagicMock,
    advanced_options: bool,
    step_id: str,
) -> None:
    """Test advanced options option."""

    test_input = {
        mqtt.CONF_BROKER: "another-broker",
        CONF_PORT: 2345,
        "advanced_options": advanced_options,
    }

    mqtt_mock = await mqtt_mock_entry()
    mock_try_connection.return_value = True
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    # Initiate with a basic setup
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
        },
    )

    mqtt_mock.async_connect.reset_mock()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": True}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=test_input,
    )
    assert result["step_id"] == step_id


@pytest.mark.parametrize(
    ("test_input", "user_input", "new_password"),
    [
        (
            {
                mqtt.CONF_BROKER: "test-broker",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "verysecret",
            },
            {
                CONF_USERNAME: "username",
                CONF_PASSWORD: "newpassword",
            },
            "newpassword",
        ),
        (
            {
                mqtt.CONF_BROKER: "test-broker",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "verysecret",
            },
            {
                CONF_USERNAME: "username",
                CONF_PASSWORD: PWD_NOT_CHANGED,
            },
            "verysecret",
        ),
    ],
)
@pytest.mark.usefixtures("mock_reload_after_entry_update")
async def test_step_reauth(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mock_try_connection: MagicMock,
    test_input: dict[str, Any],
    user_input: dict[str, Any],
    new_password: str,
) -> None:
    """Test that the reauth step works."""

    # Prepare the config entry
    config_entry = MockConfigEntry(domain=mqtt.DOMAIN, data=test_input)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    # Start reauth flow
    config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "reauth_confirm"
    assert result["context"]["source"] == "reauth"

    # Show the form
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Simulate re-auth fails
    mock_try_connection.return_value = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Simulate re-auth succeeds
    mock_try_connection.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
    assert config_entry.data.get(CONF_PASSWORD) == new_password
    await hass.async_block_till_done()


@pytest.mark.parametrize("discovery_info", [{"config": ADD_ON_DISCOVERY_INFO.copy()}])
@pytest.mark.usefixtures(
    "mqtt_client_mock", "mock_reload_after_entry_update", "supervisor", "addon_running"
)
async def test_step_hassio_reauth(
    hass: HomeAssistant, mock_try_connection: MagicMock, addon_info: AsyncMock
) -> None:
    """Test that the reauth step works in case the Mosquitto broker add-on was re-installed."""

    # Set up entry data based on the discovery data, but with a stale password
    entry_data = {
        mqtt.CONF_BROKER: "core-mosquitto",
        CONF_PORT: 1883,
        CONF_USERNAME: "mock-user",
        CONF_PASSWORD: "stale-secret",
    }

    addon_info["hostname"] = "core-mosquitto"

    # Prepare the config entry
    config_entry = MockConfigEntry(domain=mqtt.DOMAIN, data=entry_data)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.data.get(CONF_PASSWORD) == "stale-secret"

    # Start reauth flow
    mock_try_connection.reset_mock()
    mock_try_connection.return_value = True
    config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0

    # Assert the entry is updated automatically
    assert config_entry.data.get(CONF_PASSWORD) == "mock-pass"
    mock_try_connection.assert_called_once_with(
        {
            "broker": "core-mosquitto",
            "port": 1883,
            "username": "mock-user",
            "password": "mock-pass",
        }
    )


@pytest.mark.parametrize(
    ("discovery_info", "discovery_info_side_effect", "broker"),
    [
        ({"config": ADD_ON_DISCOVERY_INFO.copy()}, AddonError, "core-mosquitto"),
        ({"config": ADD_ON_DISCOVERY_INFO.copy()}, None, "broker-not-addon"),
    ],
)
@pytest.mark.usefixtures(
    "mqtt_client_mock", "mock_reload_after_entry_update", "supervisor", "addon_running"
)
async def test_step_hassio_reauth_no_discovery_info(
    hass: HomeAssistant,
    mock_try_connection: MagicMock,
    addon_info: AsyncMock,
    broker: str,
) -> None:
    """Test hassio reauth flow defaults to manual flow.

    Test that the reauth step defaults to
    normal reauth flow if fetching add-on discovery info failed,
    or the broker is not the add-on.
    """

    # Set up entry data based on the discovery data, but with a stale password
    entry_data = {
        mqtt.CONF_BROKER: broker,
        CONF_PORT: 1883,
        CONF_USERNAME: "mock-user",
        CONF_PASSWORD: "wrong-pass",
    }

    addon_info["hostname"] = "core-mosquitto"

    # Prepare the config entry
    config_entry = MockConfigEntry(domain=mqtt.DOMAIN, data=entry_data)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.data.get(CONF_PASSWORD) == "wrong-pass"

    # Start reauth flow
    mock_try_connection.reset_mock()
    mock_try_connection.return_value = True
    config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "reauth_confirm"
    assert result["context"]["source"] == "reauth"

    # Assert the entry is not updated
    assert config_entry.data.get(CONF_PASSWORD) == "wrong-pass"
    mock_try_connection.assert_not_called()


async def test_options_user_connection_fails(
    hass: HomeAssistant, mock_try_connection_time_out: MagicMock
) -> None:
    """Test if connection cannot be made."""
    config_entry = MockConfigEntry(domain=mqtt.DOMAIN)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
        },
    )
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    mock_try_connection_time_out.reset_mock()
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={mqtt.CONF_BROKER: "bad-broker", CONF_PORT: 2345},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"

    # Check we tried the connection
    assert len(mock_try_connection_time_out.mock_calls)
    # Check config entry did not update
    assert config_entry.data == {
        mqtt.CONF_BROKER: "test-broker",
        CONF_PORT: 1234,
    }


async def test_options_bad_birth_message_fails(
    hass: HomeAssistant, mock_try_connection: MqttMockPahoClient
) -> None:
    """Test bad birth message."""
    config_entry = MockConfigEntry(domain=mqtt.DOMAIN)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
        },
    )

    mock_try_connection.return_value = True

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={mqtt.CONF_BROKER: "another-broker", CONF_PORT: 2345},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"birth_topic": "ha_state/online/#"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "bad_birth"

    # Check config entry did not update
    assert config_entry.data == {
        mqtt.CONF_BROKER: "test-broker",
        CONF_PORT: 1234,
    }


async def test_options_bad_will_message_fails(
    hass: HomeAssistant, mock_try_connection: MagicMock
) -> None:
    """Test bad will message."""
    config_entry = MockConfigEntry(domain=mqtt.DOMAIN)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
        },
    )

    mock_try_connection.return_value = True

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={mqtt.CONF_BROKER: "another-broker", CONF_PORT: 2345},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"will_topic": "ha_state/offline/#"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "bad_will"

    # Check config entry did not update
    assert config_entry.data == {
        mqtt.CONF_BROKER: "test-broker",
        CONF_PORT: 1234,
    }


@pytest.mark.parametrize(
    "hass_config", [{"mqtt": {"sensor": [{"state_topic": "some-topic"}]}}]
)
@pytest.mark.usefixtures("mock_ssl_context", "mock_process_uploaded_file")
async def test_try_connection_with_advanced_parameters(
    hass: HomeAssistant, mock_try_connection_success: MqttMockPahoClient
) -> None:
    """Test config flow with advanced parameters from config."""
    config_entry = MockConfigEntry(domain=mqtt.DOMAIN)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            mqtt.CONF_TRANSPORT: "websockets",
            mqtt.CONF_CERTIFICATE: "auto",
            mqtt.CONF_TLS_INSECURE: True,
            mqtt.CONF_CLIENT_CERT: MOCK_CLIENT_CERT.decode(encoding="utf-8)"),
            mqtt.CONF_CLIENT_KEY: MOCK_CLIENT_KEY.decode(encoding="utf-8"),
            mqtt.CONF_WS_PATH: "/path/",
            mqtt.CONF_WS_HEADERS: {"h1": "v1", "h2": "v2"},
            mqtt.CONF_KEEPALIVE: 30,
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
        },
    )

    # Test default/suggested values from config
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"
    defaults = {
        mqtt.CONF_BROKER: "test-broker",
        CONF_PORT: 1234,
        "set_client_cert": True,
        "set_ca_cert": "auto",
    }
    suggested = {
        CONF_USERNAME: "user",
        CONF_PASSWORD: PWD_NOT_CHANGED,
        mqtt.CONF_TLS_INSECURE: True,
        CONF_PROTOCOL: "3.1.1",
        mqtt.CONF_TRANSPORT: "websockets",
        mqtt.CONF_WS_PATH: "/path/",
        mqtt.CONF_WS_HEADERS: '{"h1":"v1","h2":"v2"}',
    }
    for k, v in defaults.items():
        assert get_default(result["data_schema"].schema, k) == v
    for k, v in suggested.items():
        assert get_suggested(result["data_schema"].schema, k) == v

    # test we can change username and password
    # as it was configured as auto in configuration.yaml is is migrated now
    mock_try_connection_success.reset_mock()
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "another-broker",
            CONF_PORT: 2345,
            CONF_USERNAME: "us3r",
            CONF_PASSWORD: "p4ss",
            "set_ca_cert": "auto",
            "set_client_cert": True,
            mqtt.CONF_TLS_INSECURE: True,
            mqtt.CONF_TRANSPORT: "websockets",
            mqtt.CONF_WS_PATH: "/new/path",
            mqtt.CONF_WS_HEADERS: '{"h3": "v3"}',
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "options"
    await hass.async_block_till_done()

    # check if the username and password was set from config flow and not from configuration.yaml
    assert mock_try_connection_success.username_pw_set.mock_calls[0][1] == (
        "us3r",
        "p4ss",
    )
    # check if tls_insecure_set is called
    assert mock_try_connection_success.tls_insecure_set.mock_calls[0][1] == (True,)

    # check if the ca certificate settings were not set during connection test
    assert mock_try_connection_success.tls_set.mock_calls[0].kwargs[
        "certfile"
    ] == mqtt.util.get_file_path(mqtt.CONF_CLIENT_CERT)
    assert mock_try_connection_success.tls_set.mock_calls[0].kwargs[
        "keyfile"
    ] == mqtt.util.get_file_path(mqtt.CONF_CLIENT_KEY)

    # check if websockets options are set
    assert mock_try_connection_success.ws_set_options.mock_calls[0][1] == (
        "/new/path",
        {"h3": "v3"},
    )
    # Accept default option
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_ssl_context")
async def test_setup_with_advanced_settings(
    hass: HomeAssistant,
    mock_try_connection: MagicMock,
    mock_process_uploaded_file: MagicMock,
) -> None:
    """Test config flow setup with advanced parameters."""
    file_id = mock_process_uploaded_file.file_id

    config_entry = MockConfigEntry(domain=mqtt.DOMAIN)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
        },
    )

    mock_try_connection.return_value = True

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": True}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"
    assert result["data_schema"].schema["advanced_options"]

    # first iteration, basic settings
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 2345,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "secret",
            "advanced_options": True,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"
    assert "advanced_options" not in result["data_schema"].schema
    assert result["data_schema"].schema[CONF_CLIENT_ID]
    assert result["data_schema"].schema[mqtt.CONF_KEEPALIVE]
    assert result["data_schema"].schema["set_client_cert"]
    assert result["data_schema"].schema["set_ca_cert"]
    assert result["data_schema"].schema[mqtt.CONF_TLS_INSECURE]
    assert result["data_schema"].schema[CONF_PROTOCOL]
    assert result["data_schema"].schema[mqtt.CONF_TRANSPORT]
    assert mqtt.CONF_CLIENT_CERT not in result["data_schema"].schema
    assert mqtt.CONF_CLIENT_KEY not in result["data_schema"].schema

    # second iteration, advanced settings with request for client cert
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 2345,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "secret",
            mqtt.CONF_KEEPALIVE: 30,
            "set_ca_cert": "auto",
            "set_client_cert": True,
            mqtt.CONF_TLS_INSECURE: True,
            CONF_PROTOCOL: "3.1.1",
            mqtt.CONF_TRANSPORT: "websockets",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"
    assert "advanced_options" not in result["data_schema"].schema
    assert result["data_schema"].schema[CONF_CLIENT_ID]
    assert result["data_schema"].schema[mqtt.CONF_KEEPALIVE]
    assert result["data_schema"].schema["set_client_cert"]
    assert result["data_schema"].schema["set_ca_cert"]
    assert result["data_schema"].schema[mqtt.CONF_TLS_INSECURE]
    assert result["data_schema"].schema[CONF_PROTOCOL]
    assert result["data_schema"].schema[mqtt.CONF_CLIENT_CERT]
    assert result["data_schema"].schema[mqtt.CONF_CLIENT_KEY]
    assert result["data_schema"].schema[mqtt.CONF_TRANSPORT]
    assert result["data_schema"].schema[mqtt.CONF_WS_PATH]
    assert result["data_schema"].schema[mqtt.CONF_WS_HEADERS]

    # third iteration, advanced settings with client cert and key set and bad json payload
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 2345,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "secret",
            mqtt.CONF_KEEPALIVE: 30,
            "set_ca_cert": "auto",
            "set_client_cert": True,
            mqtt.CONF_CLIENT_CERT: file_id[mqtt.CONF_CLIENT_CERT],
            mqtt.CONF_CLIENT_KEY: file_id[mqtt.CONF_CLIENT_KEY],
            mqtt.CONF_TLS_INSECURE: True,
            mqtt.CONF_TRANSPORT: "websockets",
            mqtt.CONF_WS_PATH: "/custom_path/",
            mqtt.CONF_WS_HEADERS: '{"header_1": "content_header_1", "header_2": "content_header_2"',
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"
    assert result["errors"]["base"] == "bad_ws_headers"

    # fourth iteration, advanced settings with client cert and key set
    # and correct json payload for ws_headers
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 2345,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "secret",
            mqtt.CONF_KEEPALIVE: 30,
            "set_ca_cert": "auto",
            "set_client_cert": True,
            mqtt.CONF_CLIENT_CERT: file_id[mqtt.CONF_CLIENT_CERT],
            mqtt.CONF_CLIENT_KEY: file_id[mqtt.CONF_CLIENT_KEY],
            mqtt.CONF_TLS_INSECURE: True,
            mqtt.CONF_TRANSPORT: "websockets",
            mqtt.CONF_WS_PATH: "/custom_path/",
            mqtt.CONF_WS_HEADERS: '{"header_1": "content_header_1", "header_2": "content_header_2"}',
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_DISCOVERY: True,
            mqtt.CONF_DISCOVERY_PREFIX: "homeassistant_test",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Check config entry result
    assert config_entry.data == {
        mqtt.CONF_BROKER: "test-broker",
        CONF_PORT: 2345,
        CONF_USERNAME: "user",
        CONF_PASSWORD: "secret",
        mqtt.CONF_KEEPALIVE: 30,
        mqtt.CONF_CLIENT_CERT: "## mock client certificate file ##",
        mqtt.CONF_CLIENT_KEY: "## mock key file ##",
        "tls_insecure": True,
        mqtt.CONF_TRANSPORT: "websockets",
        mqtt.CONF_WS_PATH: "/custom_path/",
        mqtt.CONF_WS_HEADERS: {
            "header_1": "content_header_1",
            "header_2": "content_header_2",
        },
        mqtt.CONF_CERTIFICATE: "auto",
        mqtt.CONF_DISCOVERY: True,
        mqtt.CONF_DISCOVERY_PREFIX: "homeassistant_test",
    }


@pytest.mark.usefixtures("mock_ssl_context", "mock_process_uploaded_file")
async def test_change_websockets_transport_to_tcp(
    hass: HomeAssistant, mock_try_connection: MagicMock
) -> None:
    """Test option flow setup with websockets transport settings."""
    config_entry = MockConfigEntry(domain=mqtt.DOMAIN)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
            mqtt.CONF_TRANSPORT: "websockets",
            mqtt.CONF_WS_HEADERS: {"header_1": "custom_header1"},
            mqtt.CONF_WS_PATH: "/some_path",
        },
    )

    mock_try_connection.return_value = True

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"
    assert result["data_schema"].schema["transport"]
    assert result["data_schema"].schema["ws_path"]
    assert result["data_schema"].schema["ws_headers"]

    # Change transport to tcp
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
            mqtt.CONF_TRANSPORT: "tcp",
            mqtt.CONF_WS_HEADERS: '{"header_1": "custom_header1"}',
            mqtt.CONF_WS_PATH: "/some_path",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_DISCOVERY: True,
            mqtt.CONF_DISCOVERY_PREFIX: "homeassistant_test",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Check config entry result
    assert config_entry.data == {
        mqtt.CONF_BROKER: "test-broker",
        CONF_PORT: 1234,
        mqtt.CONF_TRANSPORT: "tcp",
        mqtt.CONF_DISCOVERY: True,
        mqtt.CONF_DISCOVERY_PREFIX: "homeassistant_test",
    }
