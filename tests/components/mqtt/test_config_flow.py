"""Test config flow."""

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from ssl import SSLError
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import Discovery
import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.components.hassio import AddonError
from homeassistant.components.mqtt.config_flow import PWD_NOT_CHANGED
from homeassistant.components.mqtt.util import learn_more_url
from homeassistant.config_entries import ConfigSubentry, ConfigSubentryData
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .common import (
    MOCK_BINARY_SENSOR_SUBENTRY_DATA_SINGLE,
    MOCK_LIGHT_BASIC_KELVIN_SUBENTRY_DATA_SINGLE,
    MOCK_NOTIFY_SUBENTRY_DATA_MULTI,
    MOCK_NOTIFY_SUBENTRY_DATA_NO_NAME,
    MOCK_NOTIFY_SUBENTRY_DATA_SINGLE,
    MOCK_SENSOR_SUBENTRY_DATA_SINGLE,
    MOCK_SENSOR_SUBENTRY_DATA_SINGLE_LAST_RESET_TEMPLATE,
    MOCK_SENSOR_SUBENTRY_DATA_SINGLE_STATE_CLASS,
    MOCK_SWITCH_SUBENTRY_DATA_SINGLE_STATE_CLASS,
)

from tests.common import MockConfigEntry, MockMqttReasonCode, get_schema_suggested_value
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

MOCK_CA_CERT = (
    b"-----BEGIN CERTIFICATE-----\n"
    b"## mock CA certificate file ##"
    b"\n-----END CERTIFICATE-----\n"
)
MOCK_GENERIC_CERT = (
    b"-----BEGIN CERTIFICATE-----\n"
    b"## mock generic certificate file ##"
    b"\n-----END CERTIFICATE-----\n"
)
MOCK_CA_CERT_DER = b"## mock DER formatted CA certificate file ##\n"
MOCK_CLIENT_CERT = (
    b"-----BEGIN CERTIFICATE-----\n"
    b"## mock client certificate file ##"
    b"\n-----END CERTIFICATE-----\n"
)
MOCK_CLIENT_CERT_DER = b"## mock DER formatted client certificate file ##\n"
MOCK_CLIENT_KEY = (
    b"-----BEGIN PRIVATE KEY-----\n"
    b"## mock client key file ##"
    b"\n-----END PRIVATE KEY-----"
)
MOCK_EC_CLIENT_KEY = (
    b"-----BEGIN EC PRIVATE KEY-----\n"
    b"## mock client key file ##"
    b"\n-----END EC PRIVATE KEY-----"
)
MOCK_RSA_CLIENT_KEY = (
    b"-----BEGIN RSA PRIVATE KEY-----\n"
    b"## mock client key file ##"
    b"\n-----END RSA PRIVATE KEY-----"
)
MOCK_ENCRYPTED_CLIENT_KEY = (
    b"-----BEGIN ENCRYPTED PRIVATE KEY-----\n"
    b"## mock client key file ##\n"
    b"-----END ENCRYPTED PRIVATE KEY-----"
)
MOCK_CLIENT_KEY_DER = b"## mock DER formatted key file ##\n"
MOCK_ENCRYPTED_CLIENT_KEY_DER = b"## mock DER formatted encrypted key file ##\n"


MOCK_ENTRY_DATA = {
    mqtt.CONF_BROKER: "test-broker",
    CONF_PORT: 1234,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
}
MOCK_ENTRY_OPTIONS = {
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
def mock_context_client_key() -> bytes:
    """Mock the client key in the moched ssl context."""
    return MOCK_CLIENT_KEY


@pytest.fixture
def mock_ssl_context(mock_context_client_key: bytes) -> Generator[dict[str, MagicMock]]:
    """Mock the SSL context used to load the cert chain and to load verify locations."""
    with (
        patch("homeassistant.components.mqtt.config_flow.SSLContext") as mock_context,
        patch(
            "homeassistant.components.mqtt.config_flow.load_pem_private_key"
        ) as mock_pem_key_check,
        patch(
            "homeassistant.components.mqtt.config_flow.load_der_private_key"
        ) as mock_der_key_check,
        patch(
            "homeassistant.components.mqtt.config_flow.load_pem_x509_certificate"
        ) as mock_pem_cert_check,
        patch(
            "homeassistant.components.mqtt.config_flow.load_der_x509_certificate"
        ) as mock_der_cert_check,
    ):
        mock_pem_key_check().private_bytes.return_value = mock_context_client_key
        mock_pem_cert_check().public_bytes.return_value = MOCK_GENERIC_CERT
        mock_der_key_check().private_bytes.return_value = mock_context_client_key
        mock_der_cert_check().public_bytes.return_value = MOCK_GENERIC_CERT
        yield {
            "context": mock_context,
            "load_der_private_key": mock_der_key_check,
            "load_der_x509_certificate": mock_der_cert_check,
            "load_pem_private_key": mock_pem_key_check,
            "load_pem_x509_certificate": mock_pem_cert_check,
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
        mock_client().on_connect(mock_client, None, None, MockMqttReasonCode(), None)

    def _subscribe(topic, qos=0):
        mid = get_mid()
        mock_client().on_subscribe(mock_client, 0, mid, [MockMqttReasonCode()], None)
        return (0, mid)

    def _unsubscribe(topic):
        mid = get_mid()
        mock_client().on_unsubscribe(mock_client, 0, mid, [MockMqttReasonCode()], None)
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
def mock_ca_cert() -> bytes:
    """Mock the CA certificate."""
    return MOCK_CA_CERT


@pytest.fixture
def mock_client_cert() -> bytes:
    """Mock the client certificate."""
    return MOCK_CLIENT_CERT


@pytest.fixture
def mock_client_key() -> bytes:
    """Mock the client key."""
    return MOCK_CLIENT_KEY


@pytest.fixture
def mock_process_uploaded_file(
    tmp_path: Path,
    mock_ca_cert: bytes,
    mock_client_cert: bytes,
    mock_client_key: bytes,
    mock_temp_dir: str,
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
                cafile.write(mock_ca_cert)
            yield tmp_path / "ca.crt"
        elif file_id == file_id_cert:
            with open(tmp_path / "client.crt", "wb") as certfile:
                certfile.write(mock_client_cert)
            yield tmp_path / "client.crt"
        elif file_id == file_id_key:
            with open(tmp_path / "client.key", "wb") as keyfile:
                keyfile.write(mock_client_key)
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
    }
    # Check we have the latest Config Entry version
    assert result["result"].version == 1
    assert result["result"].minor_version == 2
    # Check we tried the connection
    assert len(mock_try_connection.mock_calls) == 1
    # Check config entry got setup
    assert len(mock_finish_setup.mock_calls) == 1


@pytest.mark.usefixtures("mqtt_client_mock", "supervisor", "supervisor_client")
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
    }
    # Check we tried the connection, with precedence for config entry settings
    mock_try_connection.assert_called_once_with(
        {
            "broker": "127.0.0.1",
            "port": 1883,
        },
    )
    # Check config entry got setup
    assert len(mock_finish_setup.mock_calls) == 1
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    assert config_entry.title == "127.0.0.1"


async def test_user_single_instance(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(
        domain="mqtt",
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_hassio_already_configured(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(
        domain="mqtt",
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "mqtt", context={"source": config_entries.SOURCE_HASSIO}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_hassio_ignored(hass: HomeAssistant) -> None:
    """Test we supervisor discovered instance can be ignored."""
    MockConfigEntry(
        domain=mqtt.DOMAIN,
        source=config_entries.SOURCE_IGNORE,
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
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
    assert result.get("reason") == "single_instance_allowed"


async def test_hassio_confirm(
    hass: HomeAssistant,
    mock_try_connection_success: MqttMockPahoClient,
    mock_finish_setup: MagicMock,
) -> None:
    """Test we can finish a config flow."""
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
@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_mosquitto",
                service="mqtt",
                uuid=uuid4(),
                config=ADD_ON_DISCOVERY_INFO.copy(),
            )
        ]
    ],
)
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
@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_mosquitto",
                service="mqtt",
                uuid=uuid4(),
                config=ADD_ON_DISCOVERY_INFO.copy(),
            )
        ]
    ],
)
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
@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_mosquitto",
                service="mqtt",
                uuid=uuid4(),
                config=ADD_ON_DISCOVERY_INFO.copy(),
            )
        ]
    ],
)
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
@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_mosquitto",
                service="mqtt",
                uuid=uuid4(),
                config=ADD_ON_DISCOVERY_INFO.copy(),
            )
        ]
    ],
)
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
    install_addon.side_effect = SupervisorError()

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
) -> None:
    """Test config flow options."""
    with patch(
        "homeassistant.config.async_hass_config_yaml", AsyncMock(return_value={})
    ) as yaml_mock:
        await mqtt_mock_entry()
        config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "options"

        await hass.async_block_till_done()

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
        await hass.async_block_till_done()
        await hass.async_block_till_done(wait_background_tasks=True)
        assert config_entry.data == {mqtt.CONF_BROKER: "mock-broker"}
        assert config_entry.options == {
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
        # assert that the entry was reloaded with the new config
    assert yaml_mock.await_count


@pytest.mark.parametrize(
    ("mock_ca_cert", "mock_client_cert", "mock_client_key", "client_key_password"),
    [
        (MOCK_GENERIC_CERT, MOCK_GENERIC_CERT, MOCK_CLIENT_KEY, ""),
        (
            MOCK_GENERIC_CERT,
            MOCK_GENERIC_CERT,
            MOCK_ENCRYPTED_CLIENT_KEY,
            "very*secret",
        ),
        (MOCK_CA_CERT_DER, MOCK_CLIENT_CERT_DER, MOCK_CLIENT_KEY_DER, ""),
        (
            MOCK_CA_CERT_DER,
            MOCK_CLIENT_CERT_DER,
            MOCK_ENCRYPTED_CLIENT_KEY_DER,
            "very*secret",
        ),
    ],
    ids=[
        "pem_certs_private_key_no_password",
        "pem_certs_private_key_with_password",
        "der_certs_private_key_no_password",
        "der_certs_private_key_with_password",
    ],
)
@pytest.mark.parametrize(
    "test_error",
    [
        "bad_certificate",
        "bad_client_cert",
        "client_key_error",
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
    client_key_password: str,
    mock_ca_cert: bytes,
) -> None:
    """Test bad certificate tests."""

    def _side_effect_on_client_cert(data: bytes) -> MagicMock:
        """Raise on client cert only.

        The function is called twice, once for the CA chain
        and once for the client cert. We only want to raise on a client cert.
        """
        if data == MOCK_CLIENT_CERT_DER:
            raise ValueError
        mock_certificate_side_effect = MagicMock()
        mock_certificate_side_effect().public_bytes.return_value = MOCK_GENERIC_CERT
        return mock_certificate_side_effect

    # Mock certificate files
    file_id = mock_process_uploaded_file.file_id
    set_ca_cert = "custom"
    set_client_cert = True
    tls_insecure = False
    test_input = {
        mqtt.CONF_BROKER: "another-broker",
        CONF_PORT: 2345,
        mqtt.CONF_CERTIFICATE: file_id[mqtt.CONF_CERTIFICATE],
        mqtt.CONF_CLIENT_CERT: file_id[mqtt.CONF_CLIENT_CERT],
        mqtt.CONF_CLIENT_KEY: file_id[mqtt.CONF_CLIENT_KEY],
        "client_key_password": client_key_password,
        "set_ca_cert": set_ca_cert,
        "set_client_cert": True,
    }
    if test_error == "bad_certificate":
        # CA chain is not loading
        mock_ssl_context["context"]().load_verify_locations.side_effect = SSLError
        # Fail on the CA cert if DER encoded
        mock_ssl_context["load_der_x509_certificate"].side_effect = ValueError
    elif test_error == "bad_client_cert":
        # Client certificate is invalid
        mock_ssl_context["load_pem_x509_certificate"].side_effect = ValueError
        # Fail on the client cert if DER encoded
        mock_ssl_context[
            "load_der_x509_certificate"
        ].side_effect = _side_effect_on_client_cert
    elif test_error == "client_key_error":
        # Client key file is invalid
        mock_ssl_context["load_pem_private_key"].side_effect = ValueError
        mock_ssl_context["load_der_private_key"].side_effect = ValueError
    elif test_error == "bad_client_cert_key":
        # Client key file file and certificate do not pair
        mock_ssl_context["context"]().load_cert_chain.side_effect = SSLError
    elif test_error == "invalid_inclusion":
        # Client key file without client cert, client cert without key file
        test_input.pop(mqtt.CONF_CLIENT_KEY)

    mqtt_mock = await mqtt_mock_entry()
    config_entry: MockConfigEntry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
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

    result = await config_entry.start_reconfigure_flow(hass, show_advanced_options=True)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"

    result = await hass.config_entries.flow.async_configure(
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

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=test_input,
    )
    if test_error is not None:
        assert result["errors"]["base"] == test_error
        return
    assert "errors" not in result


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
    config_entry: MockConfigEntry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
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

    result = await config_entry.start_reconfigure_flow(hass, show_advanced_options=True)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"

    if error:
        with pytest.raises(vol.Invalid):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=test_input,
            )
        return
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=test_input,
    )
    assert "errors" not in result
    assert result["reason"] == "reconfigure_successful"


async def test_disable_birth_will(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mock_try_connection: MagicMock,
    mock_reload_after_entry_update: MagicMock,
) -> None:
    """Test disabling birth and will."""
    await mqtt_mock_entry()
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

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "options"
    await hass.async_block_till_done()

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
    assert result["data"] == {
        "birth_message": {},
        "discovery": True,
        "discovery_prefix": "homeassistant",
        "will_message": {},
    }
    assert config_entry.data == {mqtt.CONF_BROKER: "test-broker", CONF_PORT: 1234}
    assert config_entry.options == {
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
        },
        options={
            mqtt.CONF_DISCOVERY: True,
            mqtt.CONF_DISCOVERY_PREFIX: "homeassistant",
        },
    )
    await hass.async_block_till_done()
    mock_reload_after_entry_update.reset_mock()
    mqtt_mock.async_connect.reset_mock()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
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
    }
    assert config_entry.options == {
        mqtt.CONF_DISCOVERY: True,
        mqtt.CONF_DISCOVERY_PREFIX: "homeassistant",
    }

    await hass.async_block_till_done()
    # assert that the entry was not reloaded with the new config
    assert mock_reload_after_entry_update.call_count == 0


def get_default(schema: vol.Schema, key: str) -> Any | None:
    """Get default value for key in voluptuous schema."""
    for schema_key in schema:  # type:ignore[attr-defined]
        if schema_key == key:
            if schema_key.default == vol.UNDEFINED:
                return None
            return schema_key.default()
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
        },
        options={
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
    await hass.async_block_till_done()

    # Test default/suggested values from config
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "options"
    defaults = {
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
        assert get_schema_suggested_value(result["data_schema"].schema, key) == value

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
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
    assert result["step_id"] == "options"
    defaults = {
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
        assert get_schema_suggested_value(result["data_schema"].schema, key) == value

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
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
    ("advanced_options", "flow_result"),
    [(False, FlowResultType.ABORT), (True, FlowResultType.FORM)],
)
@pytest.mark.usefixtures("mock_reload_after_entry_update")
async def test_skipping_advanced_options(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mock_try_connection: MagicMock,
    advanced_options: bool,
    flow_result: FlowResultType,
) -> None:
    """Test advanced options option."""

    test_input = {
        mqtt.CONF_BROKER: "another-broker",
        CONF_PORT: 2345,
    }
    if advanced_options:
        test_input["advanced_options"] = True

    mqtt_mock = await mqtt_mock_entry()
    mock_try_connection.return_value = True
    config_entry: MockConfigEntry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    mqtt_mock.async_connect.reset_mock()

    result = await config_entry.start_reconfigure_flow(
        hass, show_advanced_options=advanced_options
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"

    assert ("advanced_options" in result["data_schema"].schema) == advanced_options

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=test_input,
    )
    assert result["type"] is flow_result


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
    config_entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data=test_input,
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    )
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


@pytest.mark.parametrize(
    "discovery_info",
    [
        [
            Discovery(
                addon="core_mosquitto",
                service="mqtt",
                uuid=uuid4(),
                config=ADD_ON_DISCOVERY_INFO.copy(),
            )
        ]
    ],
)
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
    config_entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data=entry_data,
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    )
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
        (
            [
                Discovery(
                    addon="core_mosquitto",
                    service="mqtt",
                    uuid=uuid4(),
                    config=ADD_ON_DISCOVERY_INFO.copy(),
                )
            ],
            AddonError,
            "core-mosquitto",
        ),
        (
            [
                Discovery(
                    addon="core_mosquitto",
                    service="mqtt",
                    uuid=uuid4(),
                    config=ADD_ON_DISCOVERY_INFO.copy(),
                )
            ],
            None,
            "broker-not-addon",
        ),
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
    config_entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data=entry_data,
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    )
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


async def test_reconfigure_user_connection_fails(
    hass: HomeAssistant, mock_try_connection_time_out: MagicMock
) -> None:
    """Test if connection cannot be made."""
    config_entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    )
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
        },
    )
    result = await config_entry.start_reconfigure_flow(hass, show_advanced_options=True)
    assert result["type"] is FlowResultType.FORM

    mock_try_connection_time_out.reset_mock()
    result = await hass.config_entries.flow.async_configure(
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
    config_entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    )
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
    config_entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    )
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
    "mock_context_client_key",
    [MOCK_CLIENT_KEY, MOCK_EC_CLIENT_KEY, MOCK_RSA_CLIENT_KEY],
)
@pytest.mark.usefixtures("mock_ssl_context", "mock_process_uploaded_file")
async def test_try_connection_with_advanced_parameters(
    hass: HomeAssistant,
    mock_try_connection_success: MqttMockPahoClient,
    mock_context_client_key: bytes,
) -> None:
    """Test config flow with advanced parameters from config."""
    config_entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    )
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
            mqtt.CONF_CLIENT_KEY: mock_context_client_key.decode(encoding="utf-8"),
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
    result = await config_entry.start_reconfigure_flow(hass, show_advanced_options=True)
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
        assert get_schema_suggested_value(result["data_schema"].schema, k) == v

    # test we can change username and password
    mock_try_connection_success.reset_mock()
    result = await hass.config_entries.flow.async_configure(
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
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    # check if the username and password was set from config flow and not from configuration.yaml
    assert mock_try_connection_success.username_pw_set.mock_calls[0][1] == (
        "us3r",
        "p4ss",
    )
    # check if tls_insecure_set is called
    assert mock_try_connection_success.tls_insecure_set.mock_calls[0][1] == (True,)

    def read_file(path: Path) -> bytes:
        with open(path, mode="rb") as file:
            return file.read()

    # check if the client certificate settings saved
    client_cert_path = await hass.async_add_executor_job(
        mqtt.util.get_file_path, mqtt.CONF_CLIENT_CERT
    )
    assert (
        mock_try_connection_success.tls_set.mock_calls[0].kwargs["certfile"]
        == client_cert_path
    )
    assert (
        await hass.async_add_executor_job(read_file, client_cert_path)
        == MOCK_CLIENT_CERT
    )

    client_key_path = await hass.async_add_executor_job(
        mqtt.util.get_file_path, mqtt.CONF_CLIENT_KEY
    )
    assert (
        mock_try_connection_success.tls_set.mock_calls[0].kwargs["keyfile"]
        == client_key_path
    )
    assert (
        await hass.async_add_executor_job(read_file, client_key_path)
        == mock_context_client_key
    )

    # check if websockets options are set
    assert mock_try_connection_success.ws_set_options.mock_calls[0][1] == (
        "/new/path",
        {"h3": "v3"},
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_ssl_context")
async def test_setup_with_advanced_settings(
    hass: HomeAssistant,
    mock_try_connection: MagicMock,
    mock_process_uploaded_file: MagicMock,
) -> None:
    """Test config flow setup with advanced parameters."""
    file_id = mock_process_uploaded_file.file_id

    config_entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    )
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
        },
    )

    mock_try_connection.return_value = True

    result = await config_entry.start_reconfigure_flow(hass, show_advanced_options=True)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"
    assert result["data_schema"].schema["advanced_options"]

    # first iteration, basic settings
    result = await hass.config_entries.flow.async_configure(
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
    result = await hass.config_entries.flow.async_configure(
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
    result = await hass.config_entries.flow.async_configure(
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
    result = await hass.config_entries.flow.async_configure(
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Check config entry result
    assert config_entry.data == {
        mqtt.CONF_BROKER: "test-broker",
        CONF_PORT: 2345,
        CONF_USERNAME: "user",
        CONF_PASSWORD: "secret",
        mqtt.CONF_KEEPALIVE: 30,
        mqtt.CONF_CLIENT_CERT: MOCK_CLIENT_CERT.decode(encoding="utf-8"),
        mqtt.CONF_CLIENT_KEY: MOCK_CLIENT_KEY.decode(encoding="utf-8"),
        "tls_insecure": True,
        mqtt.CONF_TRANSPORT: "websockets",
        mqtt.CONF_WS_PATH: "/custom_path/",
        mqtt.CONF_WS_HEADERS: {
            "header_1": "content_header_1",
            "header_2": "content_header_2",
        },
        mqtt.CONF_CERTIFICATE: "auto",
    }


@pytest.mark.usefixtures("mock_ssl_context")
@pytest.mark.parametrize(
    ("mock_ca_cert", "mock_client_cert", "mock_client_key", "client_key_password"),
    [
        (MOCK_GENERIC_CERT, MOCK_GENERIC_CERT, MOCK_CLIENT_KEY, ""),
        (
            MOCK_GENERIC_CERT,
            MOCK_GENERIC_CERT,
            MOCK_ENCRYPTED_CLIENT_KEY,
            "very*secret",
        ),
        (MOCK_CA_CERT_DER, MOCK_CLIENT_CERT_DER, MOCK_CLIENT_KEY_DER, ""),
        (
            MOCK_CA_CERT_DER,
            MOCK_CLIENT_CERT_DER,
            MOCK_ENCRYPTED_CLIENT_KEY_DER,
            "very*secret",
        ),
    ],
    ids=[
        "pem_certs_private_key_no_password",
        "pem_certs_private_key_with_password",
        "der_certs_private_key_no_password",
        "der_certs_private_key_with_password",
    ],
)
async def test_setup_with_certificates(
    hass: HomeAssistant,
    mock_try_connection: MagicMock,
    mock_process_uploaded_file: MagicMock,
    client_key_password: str,
) -> None:
    """Test config flow setup with PEM and DER encoded certificates."""
    file_id = mock_process_uploaded_file.file_id

    config_entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    )
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
        },
    )

    mock_try_connection.return_value = True

    result = await config_entry.start_reconfigure_flow(hass, show_advanced_options=True)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"
    assert result["data_schema"].schema["advanced_options"]

    # first iteration, basic settings
    result = await hass.config_entries.flow.async_configure(
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
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 2345,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "secret",
            mqtt.CONF_KEEPALIVE: 30,
            "set_ca_cert": "custom",
            "set_client_cert": True,
            mqtt.CONF_TLS_INSECURE: False,
            CONF_PROTOCOL: "3.1.1",
            mqtt.CONF_TRANSPORT: "tcp",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"
    assert "advanced_options" not in result["data_schema"].schema
    assert result["data_schema"].schema[CONF_CLIENT_ID]
    assert result["data_schema"].schema[mqtt.CONF_KEEPALIVE]
    assert result["data_schema"].schema["set_client_cert"]
    assert result["data_schema"].schema["set_ca_cert"]
    assert result["data_schema"].schema["client_key_password"]
    assert result["data_schema"].schema[mqtt.CONF_TLS_INSECURE]
    assert result["data_schema"].schema[CONF_PROTOCOL]
    assert result["data_schema"].schema[mqtt.CONF_CERTIFICATE]
    assert result["data_schema"].schema[mqtt.CONF_CLIENT_CERT]
    assert result["data_schema"].schema[mqtt.CONF_CLIENT_KEY]
    assert result["data_schema"].schema[mqtt.CONF_TRANSPORT]

    # third iteration, advanced settings with client cert and key and CA certificate
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 2345,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "secret",
            mqtt.CONF_KEEPALIVE: 30,
            "set_ca_cert": "custom",
            "set_client_cert": True,
            "client_key_password": client_key_password,
            mqtt.CONF_CERTIFICATE: file_id[mqtt.CONF_CERTIFICATE],
            mqtt.CONF_CLIENT_CERT: file_id[mqtt.CONF_CLIENT_CERT],
            mqtt.CONF_CLIENT_KEY: file_id[mqtt.CONF_CLIENT_KEY],
            mqtt.CONF_TLS_INSECURE: False,
            mqtt.CONF_TRANSPORT: "tcp",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Check config entry result
    assert config_entry.data == {
        mqtt.CONF_BROKER: "test-broker",
        CONF_PORT: 2345,
        CONF_USERNAME: "user",
        CONF_PASSWORD: "secret",
        mqtt.CONF_KEEPALIVE: 30,
        mqtt.CONF_CLIENT_CERT: MOCK_GENERIC_CERT.decode(encoding="utf-8"),
        mqtt.CONF_CLIENT_KEY: MOCK_CLIENT_KEY.decode(encoding="utf-8"),
        "tls_insecure": False,
        mqtt.CONF_TRANSPORT: "tcp",
        mqtt.CONF_CERTIFICATE: MOCK_GENERIC_CERT.decode(encoding="utf-8"),
    }


@pytest.mark.usefixtures("mock_ssl_context", "mock_process_uploaded_file")
async def test_change_websockets_transport_to_tcp(
    hass: HomeAssistant, mock_try_connection: MagicMock
) -> None:
    """Test reconfiguration flow changing websockets transport settings."""
    config_entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    )
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

    result = await config_entry.start_reconfigure_flow(hass, show_advanced_options=True)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"
    assert result["data_schema"].schema["transport"]
    assert result["data_schema"].schema["ws_path"]
    assert result["data_schema"].schema["ws_headers"]

    # Change transport to tcp
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
            mqtt.CONF_TRANSPORT: "tcp",
            mqtt.CONF_WS_HEADERS: '{"header_1": "custom_header1"}',
            mqtt.CONF_WS_PATH: "/some_path",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Check config entry result
    assert config_entry.data == {
        mqtt.CONF_BROKER: "test-broker",
        CONF_PORT: 1234,
        mqtt.CONF_TRANSPORT: "tcp",
    }


@pytest.mark.usefixtures("mock_ssl_context", "mock_process_uploaded_file")
@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [
        {
            mqtt.CONF_BROKER: "test-broker",
            CONF_PORT: 1234,
            mqtt.CONF_TRANSPORT: "websockets",
            mqtt.CONF_WS_HEADERS: {"header_1": "custom_header1"},
            mqtt.CONF_WS_PATH: "/some_path",
        }
    ],
)
async def test_reconfigure_flow_form(
    hass: HomeAssistant,
    mock_try_connection: MagicMock,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test reconfigure flow."""
    await mqtt_mock_entry()
    entry: MockConfigEntry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    result = await entry.start_reconfigure_flow(hass, show_advanced_options=True)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "10.10.10,10",
            CONF_PORT: 1234,
            mqtt.CONF_TRANSPORT: "websockets",
            mqtt.CONF_WS_HEADERS: '{"header_1": "custom_header1"}',
            mqtt.CONF_WS_PATH: "/some_new_path",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        mqtt.CONF_BROKER: "10.10.10,10",
        CONF_PORT: 1234,
        mqtt.CONF_TRANSPORT: "websockets",
        mqtt.CONF_WS_HEADERS: {"header_1": "custom_header1"},
        mqtt.CONF_WS_PATH: "/some_new_path",
    }
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.usefixtures("mock_ssl_context", "mock_process_uploaded_file")
@pytest.mark.parametrize(
    "mqtt_config_entry_data",
    [
        {
            mqtt.CONF_BROKER: "test-broker",
            CONF_USERNAME: "mqtt-user",
            CONF_PASSWORD: "mqtt-password",
            CONF_PORT: 1234,
            mqtt.CONF_TRANSPORT: "websockets",
            mqtt.CONF_WS_HEADERS: {"header_1": "custom_header1"},
            mqtt.CONF_WS_PATH: "/some_path",
        }
    ],
)
async def test_reconfigure_no_changed_password(
    hass: HomeAssistant,
    mock_try_connection: MagicMock,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test reconfigure flow."""
    await mqtt_mock_entry()
    entry: MockConfigEntry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    result = await entry.start_reconfigure_flow(hass, show_advanced_options=True)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "broker"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            mqtt.CONF_BROKER: "10.10.10,10",
            CONF_USERNAME: "mqtt-user",
            CONF_PASSWORD: PWD_NOT_CHANGED,
            CONF_PORT: 1234,
            mqtt.CONF_TRANSPORT: "websockets",
            mqtt.CONF_WS_HEADERS: '{"header_1": "custom_header1"}',
            mqtt.CONF_WS_PATH: "/some_new_path",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        mqtt.CONF_BROKER: "10.10.10,10",
        CONF_USERNAME: "mqtt-user",
        CONF_PASSWORD: "mqtt-password",
        CONF_PORT: 1234,
        mqtt.CONF_TRANSPORT: "websockets",
        mqtt.CONF_WS_HEADERS: {"header_1": "custom_header1"},
        mqtt.CONF_WS_PATH: "/some_new_path",
    }
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize(
    (
        "version",
        "minor_version",
        "data",
        "options",
        "expected_version",
        "expected_minor_version",
    ),
    [
        (1, 1, MOCK_ENTRY_DATA | MOCK_ENTRY_OPTIONS, {}, 1, 2),
        (1, 2, MOCK_ENTRY_DATA, MOCK_ENTRY_OPTIONS, 1, 2),
        (1, 3, MOCK_ENTRY_DATA, MOCK_ENTRY_OPTIONS, 1, 3),
    ],
)
@pytest.mark.usefixtures("mock_reload_after_entry_update")
async def test_migrate_config_entry(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    version: int,
    minor_version: int,
    data: dict[str, Any],
    options: dict[str, Any],
    expected_version: int,
    expected_minor_version: int,
) -> None:
    """Test migrating a config entry."""
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    # Mock to a migratable or compatbible config entry version
    hass.config_entries.async_update_entry(
        config_entry,
        data=data,
        options=options,
        version=version,
        minor_version=minor_version,
    )
    await hass.async_block_till_done()
    # Start MQTT
    await mqtt_mock_entry()
    await hass.async_block_till_done()
    assert (
        config_entry.data | config_entry.options == MOCK_ENTRY_DATA | MOCK_ENTRY_OPTIONS
    )
    assert config_entry.version == expected_version
    assert config_entry.minor_version == expected_minor_version


@pytest.mark.parametrize(
    (
        "version",
        "minor_version",
        "data",
        "options",
        "expected_version",
        "expected_minor_version",
    ),
    [
        (2, 1, MOCK_ENTRY_DATA, MOCK_ENTRY_OPTIONS, 2, 1),
    ],
)
@pytest.mark.usefixtures("mock_reload_after_entry_update")
async def test_migrate_of_incompatible_config_entry(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    version: int,
    minor_version: int,
    data: dict[str, Any],
    options: dict[str, Any],
    expected_version: int,
    expected_minor_version: int,
) -> None:
    """Test migrating a config entry."""
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    # Mock an incompatible config entry version
    hass.config_entries.async_update_entry(
        config_entry,
        data=data,
        options=options,
        version=version,
        minor_version=minor_version,
    )
    await hass.async_block_till_done()
    assert config_entry.version == expected_version
    assert config_entry.minor_version == expected_minor_version

    # Try to start MQTT with incompatible config entry
    with pytest.raises(AssertionError):
        await mqtt_mock_entry()

    assert config_entry.state is config_entries.ConfigEntryState.MIGRATION_ERROR


@pytest.mark.parametrize(
    (
        "config_subentries_data",
        "mock_device_user_input",
        "mock_entity_user_input",
        "mock_entity_details_user_input",
        "mock_entity_details_failed_user_input",
        "mock_mqtt_user_input",
        "mock_failed_mqtt_user_input",
        "entity_name",
    ),
    [
        (
            MOCK_BINARY_SENSOR_SUBENTRY_DATA_SINGLE,
            {"name": "Milk notifier", "mqtt_settings": {"qos": 2}},
            {"name": "Hatch"},
            {"device_class": "door"},
            (),
            {
                "state_topic": "test-topic",
                "value_template": "{{ value_json.value }}",
                "advanced_settings": {"expire_after": 1200, "off_delay": 5},
            },
            (
                (
                    {"state_topic": "test-topic#invalid"},
                    {"state_topic": "invalid_subscribe_topic"},
                ),
            ),
            "Milk notifier Hatch",
        ),
        (
            MOCK_NOTIFY_SUBENTRY_DATA_SINGLE,
            {"name": "Milk notifier", "mqtt_settings": {"qos": 1}},
            {"name": "Milkman alert"},
            None,
            None,
            {
                "command_topic": "test-topic",
                "command_template": "{{ value }}",
                "retain": False,
            },
            (
                (
                    {"command_topic": "test-topic#invalid"},
                    {"command_topic": "invalid_publish_topic"},
                ),
            ),
            "Milk notifier Milkman alert",
        ),
        (
            MOCK_NOTIFY_SUBENTRY_DATA_NO_NAME,
            {"name": "Milk notifier", "mqtt_settings": {"qos": 0}},
            {},
            None,
            None,
            {
                "command_topic": "test-topic",
                "command_template": "{{ value }}",
                "retain": False,
            },
            (
                (
                    {"command_topic": "test-topic#invalid"},
                    {"command_topic": "invalid_publish_topic"},
                ),
            ),
            "Milk notifier",
        ),
        (
            MOCK_SENSOR_SUBENTRY_DATA_SINGLE,
            {"name": "Milk notifier", "mqtt_settings": {"qos": 0}},
            {"name": "Energy"},
            {"device_class": "enum", "options": ["low", "medium", "high"]},
            (
                (
                    {
                        "device_class": "energy",
                        "unit_of_measurement": "ppm",
                    },
                    {"unit_of_measurement": "invalid_uom"},
                ),
                # Trigger options to be shown on the form
                (
                    {"device_class": "enum"},
                    {"options": "options_with_enum_device_class"},
                ),
                # Test options are only allowed with device_class enum
                (
                    {
                        "device_class": "energy",
                        "options": ["less", "more"],
                    },
                    {
                        "device_class": "options_device_class_enum",
                        "unit_of_measurement": "uom_required_for_device_class",
                    },
                ),
                # Include options again to allow flow with valid data
                (
                    {"device_class": "enum"},
                    {"options": "options_with_enum_device_class"},
                ),
                (
                    {
                        "device_class": "enum",
                        "state_class": "measurement",
                        "options": ["less", "more"],
                    },
                    {"options": "options_not_allowed_with_state_class_or_uom"},
                ),
            ),
            {
                "state_topic": "test-topic",
                "value_template": "{{ value_json.value }}",
                "advanced_settings": {"expire_after": 30},
            },
            (
                (
                    {"state_topic": "test-topic#invalid"},
                    {"state_topic": "invalid_subscribe_topic"},
                ),
            ),
            "Milk notifier Energy",
        ),
        (
            MOCK_SENSOR_SUBENTRY_DATA_SINGLE_STATE_CLASS,
            {"name": "Milk notifier", "mqtt_settings": {"qos": 0}},
            {"name": "Energy"},
            {
                "state_class": "measurement",
            },
            (),
            {
                "state_topic": "test-topic",
            },
            (),
            "Milk notifier Energy",
        ),
        (
            MOCK_SWITCH_SUBENTRY_DATA_SINGLE_STATE_CLASS,
            {"name": "Milk notifier", "mqtt_settings": {"qos": 0}},
            {"name": "Outlet"},
            {"device_class": "outlet"},
            (),
            {
                "command_topic": "test-topic",
                "command_template": "{{ value }}",
                "state_topic": "test-topic",
                "value_template": "{{ value_json.value }}",
                "optimistic": True,
            },
            (
                (
                    {"command_topic": "test-topic#invalid"},
                    {"command_topic": "invalid_publish_topic"},
                ),
                (
                    {
                        "command_topic": "test-topic",
                        "state_topic": "test-topic#invalid",
                    },
                    {"state_topic": "invalid_subscribe_topic"},
                ),
            ),
            "Milk notifier Outlet",
        ),
        (
            MOCK_LIGHT_BASIC_KELVIN_SUBENTRY_DATA_SINGLE,
            {"name": "Milk notifier", "mqtt_settings": {"qos": 1}},
            {"name": "Basic light"},
            {},
            {},
            {
                "command_topic": "test-topic",
                "state_topic": "test-topic",
                "state_value_template": "{{ value_json.value }}",
                "optimistic": True,
            },
            (
                (
                    {"command_topic": "test-topic#invalid"},
                    {"command_topic": "invalid_publish_topic"},
                ),
                (
                    {
                        "command_topic": "test-topic",
                        "state_topic": "test-topic#invalid",
                    },
                    {"state_topic": "invalid_subscribe_topic"},
                ),
                (
                    {
                        "command_topic": "test-topic",
                        "advanced_settings": {"max_kelvin": 2000, "min_kelvin": 2000},
                    },
                    {
                        "max_kelvin": "max_below_min_kelvin",
                        "min_kelvin": "max_below_min_kelvin",
                    },
                ),
            ),
            "Milk notifier Basic light",
        ),
    ],
    ids=[
        "binary_sensor",
        "notify_with_entity_name",
        "notify_no_entity_name",
        "sensor_options",
        "sensor_total",
        "switch",
        "light_basic_kelvin",
    ],
)
async def test_subentry_configflow(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    config_subentries_data: dict[str, Any],
    mock_device_user_input: dict[str, Any],
    mock_entity_user_input: dict[str, Any],
    mock_entity_details_user_input: dict[str, Any],
    mock_entity_details_failed_user_input: tuple[
        tuple[dict[str, Any], dict[str, str]],
    ],
    mock_mqtt_user_input: dict[str, Any],
    mock_failed_mqtt_user_input: tuple[tuple[dict[str, Any], dict[str, str]],],
    entity_name: str,
) -> None:
    """Test the subentry ConfigFlow."""
    device_name = mock_device_user_input["name"]
    component = next(iter(config_subentries_data["components"].values()))

    await mqtt_mock_entry()
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "device"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device"

    # Test the URL validation
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "name": device_name,
            "configuration_url": "http:/badurl.example.com",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device"
    assert result["errors"]["configuration_url"] == "invalid_url"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input=mock_device_user_input,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "entity"
    assert result["errors"] == {}

    # Process entity flow (initial step)

    # Test the entity picture URL validation
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "platform": component["platform"],
            "entity_picture": "invalid url",
        }
        | mock_entity_user_input,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "entity"

    # Try again with valid data
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "platform": component["platform"],
            "entity_picture": component["entity_picture"],
        }
        | mock_entity_user_input,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["description_placeholders"] == {
        "mqtt_device": device_name,
        "platform": component["platform"],
        "entity": entity_name,
        "url": learn_more_url(component["platform"]),
    }

    # Process extra step if the platform supports it
    if mock_entity_details_user_input is not None:
        # Extra entity details flow step
        assert result["step_id"] == "entity_platform_config"

        # First test validators if set of test
        for failed_user_input, failed_errors in mock_entity_details_failed_user_input:
            # Test an invalid entity details user input case
            result = await hass.config_entries.subentries.async_configure(
                result["flow_id"],
                user_input=failed_user_input,
            )
            assert result["type"] is FlowResultType.FORM
            assert result["errors"] == failed_errors

        # Now try again with valid data
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input=mock_entity_details_user_input,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        assert result["description_placeholders"] == {
            "mqtt_device": device_name,
            "platform": component["platform"],
            "entity": entity_name,
            "url": learn_more_url(component["platform"]),
        }
    else:
        # No details form step
        assert result["step_id"] == "mqtt_platform_config"

    # Process mqtt platform config flow
    # Test an invalid mqtt user input case
    for failed_user_input, failed_errors in mock_failed_mqtt_user_input:
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input=failed_user_input,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == failed_errors

    # Try again with a valid configuration
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input=mock_mqtt_user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == device_name

    subentry_component = next(
        iter(next(iter(config_entry.subentries.values())).data["components"].values())
    )
    assert subentry_component == next(
        iter(config_subentries_data["components"].values())
    )

    subentry_device_data = next(iter(config_entry.subentries.values())).data["device"]
    for option, value in mock_device_user_input.items():
        assert subentry_device_data[option] == value

    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "mqtt_config_subentries_data",
    [
        (
            ConfigSubentryData(
                data=MOCK_NOTIFY_SUBENTRY_DATA_MULTI,
                subentry_type="device",
                title="Mock subentry",
            ),
        )
    ],
    ids=["notify"],
)
async def test_subentry_reconfigure_remove_entity(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the subentry ConfigFlow reconfigure removing an entity."""
    await mqtt_mock_entry()
    config_entry: MockConfigEntry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    subentry_id: str
    subentry: ConfigSubentry
    subentry_id, subentry = next(iter(config_entry.subentries.items()))
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, "device", subentry_id
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "summary_menu"

    # assert we have a device for the subentry
    device = device_registry.async_get_device(identifiers={(mqtt.DOMAIN, subentry_id)})
    assert device is not None

    # assert we have an entity for all subentry components
    components = deepcopy(dict(subentry.data))["components"]
    assert len(components) == 2
    object_list = list(components)
    component_list = list(components.values())
    entity_name_0 = (
        f"{device.name} {component_list[0]['name']} ({component_list[0]['platform']})"
    )
    entity_name_1 = (
        f"{device.name} {component_list[1]['name']} ({component_list[1]['platform']})"
    )

    for key, component in components.items():
        unique_entity_id = f"{subentry_id}_{key}"
        entity_id = entity_registry.async_get_entity_id(
            domain=component["platform"],
            platform=mqtt.DOMAIN,
            unique_id=unique_entity_id,
        )
        assert entity_id is not None
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None
        assert entity_entry.config_subentry_id == subentry_id

    # assert menu options, we have the option to delete one entity
    # we have no option to save and finish yet
    assert result["menu_options"] == [
        "entity",
        "update_entity",
        "delete_entity",
        "device",
        "availability",
    ]

    # assert we can delete an entity
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "delete_entity"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "delete_entity"
    assert result["data_schema"].schema["component"].config["options"] == [
        {"value": object_list[0], "label": entity_name_0},
        {"value": object_list[1], "label": entity_name_1},
    ]
    # remove notify_the_second_notifier
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "component": object_list[1],
        },
    )

    # assert menu options, we have only one item left, we cannot delete it
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "summary_menu"
    assert result["menu_options"] == [
        "entity",
        "update_entity",
        "device",
        "availability",
        "save_changes",
    ]

    # finish reconfigure flow
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "save_changes"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # check if the second entity was removed from the subentry and entity registry
    unique_entity_id = f"{subentry_id}_{object_list[1]}"
    entity_id = entity_registry.async_get_entity_id(
        domain=components[object_list[1]]["platform"],
        platform=mqtt.DOMAIN,
        unique_id=unique_entity_id,
    )
    assert entity_id is None
    new_components = deepcopy(dict(subentry.data))["components"]
    assert object_list[0] in new_components
    assert object_list[1] not in new_components


@pytest.mark.parametrize(
    ("mqtt_config_subentries_data", "user_input_mqtt"),
    [
        (
            (
                ConfigSubentryData(
                    data=MOCK_NOTIFY_SUBENTRY_DATA_MULTI,
                    subentry_type="device",
                    title="Mock subentry",
                ),
            ),
            {"command_topic": "test-topic2-updated"},
        )
    ],
    ids=["notify"],
)
async def test_subentry_reconfigure_edit_entity_multi_entitites(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    user_input_mqtt: dict[str, Any],
) -> None:
    """Test the subentry ConfigFlow reconfigure with multi entities."""
    await mqtt_mock_entry()
    config_entry: MockConfigEntry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    subentry_id: str
    subentry: ConfigSubentry
    subentry_id, subentry = next(iter(config_entry.subentries.items()))
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, "device", subentry_id
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "summary_menu"

    # assert we have a device for the subentry
    device = device_registry.async_get_device(identifiers={(mqtt.DOMAIN, subentry_id)})
    assert device is not None

    # assert we have an entity for all subentry components
    components = deepcopy(dict(subentry.data))["components"]
    assert len(components) == 2
    object_list = list(components)
    component_list = list(components.values())
    entity_name_0 = (
        f"{device.name} {component_list[0]['name']} ({component_list[0]['platform']})"
    )
    entity_name_1 = (
        f"{device.name} {component_list[1]['name']} ({component_list[1]['platform']})"
    )

    for key in components:
        unique_entity_id = f"{subentry_id}_{key}"
        entity_id = entity_registry.async_get_entity_id(
            domain="notify", platform=mqtt.DOMAIN, unique_id=unique_entity_id
        )
        assert entity_id is not None
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None
        assert entity_entry.config_subentry_id == subentry_id

    # assert menu options, we have the option to delete one entity
    # we have no option to save and finish yet
    assert result["menu_options"] == [
        "entity",
        "update_entity",
        "delete_entity",
        "device",
        "availability",
    ]

    # assert we can update an entity
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "update_entity"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "update_entity"
    assert result["data_schema"].schema["component"].config["options"] == [
        {"value": object_list[0], "label": entity_name_0},
        {"value": object_list[1], "label": entity_name_1},
    ]
    # select second entity
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "component": object_list[1],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "entity"

    # submit the common entity data with changed entity_picture
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "entity_picture": "https://example.com",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mqtt_platform_config"

    # submit the new platform specific entity data
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input=user_input_mqtt,
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "summary_menu"

    # finish reconfigure flow
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "save_changes"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Check we still have our components
    new_components = deepcopy(dict(subentry.data))["components"]

    # Check the second component was updated
    assert new_components[object_list[0]] == components[object_list[0]]
    for key, value in user_input_mqtt.items():
        assert new_components[object_list[1]][key] == value


@pytest.mark.parametrize(
    (
        "mqtt_config_subentries_data",
        "user_input_platform_config_validation",
        "user_input_platform_config",
        "user_input_mqtt",
        "component_data",
        "removed_options",
    ),
    [
        (
            (
                ConfigSubentryData(
                    data=MOCK_NOTIFY_SUBENTRY_DATA_SINGLE,
                    subentry_type="device",
                    title="Mock subentry",
                ),
            ),
            (),
            None,
            {
                "command_topic": "test-topic1-updated",
                "command_template": "{{ value }}",
                "retain": True,
            },
            {
                "command_topic": "test-topic1-updated",
                "command_template": "{{ value }}",
                "retain": True,
            },
            {"entity_picture"},
        ),
        (
            (
                ConfigSubentryData(
                    data=MOCK_SENSOR_SUBENTRY_DATA_SINGLE,
                    subentry_type="device",
                    title="Mock subentry",
                ),
            ),
            (
                (
                    {
                        "device_class": "battery",
                        "options": [],
                        "state_class": "measurement",
                        "unit_of_measurement": "invalid",
                    },
                    # Allow to accept options are being removed
                    {
                        "device_class": "options_device_class_enum",
                        "options": "options_not_allowed_with_state_class_or_uom",
                        "unit_of_measurement": "invalid_uom",
                    },
                ),
            ),
            {
                "device_class": "battery",
                "state_class": "measurement",
                "unit_of_measurement": "%",
                "advanced_settings": {"suggested_display_precision": 1},
            },
            {
                "state_topic": "test-topic1-updated",
                "value_template": "{{ value_json.value }}",
            },
            {
                "state_topic": "test-topic1-updated",
                "value_template": "{{ value_json.value }}",
            },
            {"options", "expire_after", "entity_picture"},
        ),
        (
            (
                ConfigSubentryData(
                    data=MOCK_LIGHT_BASIC_KELVIN_SUBENTRY_DATA_SINGLE,
                    subentry_type="device",
                    title="Mock subentry",
                ),
            ),
            None,
            None,
            {
                "command_topic": "test-topic1-updated",
                "state_topic": "test-topic1-updated",
                "light_brightness_settings": {
                    "brightness_command_template": "{{ value_json.value }}"
                },
            },
            {
                "command_topic": "test-topic1-updated",
                "state_topic": "test-topic1-updated",
                "brightness_command_template": "{{ value_json.value }}",
            },
            {"optimistic", "state_value_template", "entity_picture"},
        ),
    ],
    ids=["notify", "sensor", "light_basic"],
)
async def test_subentry_reconfigure_edit_entity_single_entity(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    user_input_platform_config_validation: tuple[
        tuple[dict[str, Any], dict[str, str] | None], ...
    ]
    | None,
    user_input_platform_config: dict[str, Any] | None,
    user_input_mqtt: dict[str, Any],
    component_data: dict[str, Any],
    removed_options: tuple[str, ...],
) -> None:
    """Test the subentry ConfigFlow reconfigure with single entity."""
    await mqtt_mock_entry()
    config_entry: MockConfigEntry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    subentry_id: str
    subentry: ConfigSubentry
    subentry_id, subentry = next(iter(config_entry.subentries.items()))
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, "device", subentry_id
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "summary_menu"

    # assert we have a device for the subentry
    device = device_registry.async_get_device(identifiers={(mqtt.DOMAIN, subentry_id)})
    assert device is not None

    # assert we have an entity for the subentry component
    # Check we have "notify_milkman_alert" in our mock data
    components = deepcopy(dict(subentry.data))["components"]
    assert len(components) == 1

    component_id, component = next(iter(components.items()))

    unique_entity_id = f"{subentry_id}_{component_id}"
    entity_id = entity_registry.async_get_entity_id(
        domain=component["platform"], platform=mqtt.DOMAIN, unique_id=unique_entity_id
    )
    assert entity_id is not None
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.config_subentry_id == subentry_id

    # assert menu options, we do not have the option to delete an entity
    # we have no option to save and finish yet
    assert result["menu_options"] == [
        "entity",
        "update_entity",
        "device",
        "availability",
    ]

    # assert we can update the entity, there is no select step
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "update_entity"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "entity"

    # submit the new common entity data, reset entity_picture
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.FORM

    if user_input_platform_config is None:
        # Skip entity flow step
        assert result["step_id"] == "mqtt_platform_config"
    else:
        # Additional entity flow step
        assert result["step_id"] == "entity_platform_config"
        for entity_validation_config, errors in user_input_platform_config_validation:
            result = await hass.config_entries.subentries.async_configure(
                result["flow_id"],
                user_input=entity_validation_config,
            )
            assert result["step_id"] == "entity_platform_config"
            assert result.get("errors") == errors
            assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input=user_input_platform_config,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "mqtt_platform_config"

    # submit the new platform specific entity data,
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input=user_input_mqtt,
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "summary_menu"

    # finish reconfigure flow
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "save_changes"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Check we still have out components
    new_components = deepcopy(dict(subentry.data))["components"]
    assert len(new_components) == 1

    # Check our update was successful
    assert "entity_picture" not in new_components[component_id]

    # Check the second component was updated
    for key, value in component_data.items():
        assert new_components[component_id][key] == value

    assert set(component) - set(new_components[component_id]) == removed_options


@pytest.mark.parametrize(
    (
        "mqtt_config_subentries_data",
        "user_input_entity_details",
        "user_input_mqtt",
        "filtered_out_fields",
    ),
    [
        (
            (
                ConfigSubentryData(
                    data=MOCK_SENSOR_SUBENTRY_DATA_SINGLE_LAST_RESET_TEMPLATE,
                    subentry_type="device",
                    title="Mock subentry",
                ),
            ),
            {
                "state_class": "measurement",
            },
            {
                "state_topic": "test-topic",
            },
            ("last_reset_value_template",),
        ),
    ],
    ids=["sensor_last_reset_template"],
)
async def test_subentry_reconfigure_edit_entity_reset_fields(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    user_input_entity_details: dict[str, Any],
    user_input_mqtt: dict[str, Any],
    filtered_out_fields: tuple[str, ...],
) -> None:
    """Test the subentry ConfigFlow reconfigure resets filtered out fields."""
    await mqtt_mock_entry()
    config_entry: MockConfigEntry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    subentry_id: str
    subentry: ConfigSubentry
    subentry_id, subentry = next(iter(config_entry.subentries.items()))
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, "device", subentry_id
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "summary_menu"

    # assert we have a device for the subentry
    device = device_registry.async_get_device(identifiers={(mqtt.DOMAIN, subentry_id)})
    assert device is not None

    # assert we have an entity for the subentry component
    components = deepcopy(dict(subentry.data))["components"]
    assert len(components) == 1

    component_id, component = next(iter(components.items()))
    for field in filtered_out_fields:
        assert field in component

    unique_entity_id = f"{subentry_id}_{component_id}"
    entity_id = entity_registry.async_get_entity_id(
        domain=component["platform"], platform=mqtt.DOMAIN, unique_id=unique_entity_id
    )
    assert entity_id is not None
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.config_subentry_id == subentry_id

    # assert menu options, we do not have the option to delete an entity
    # we have no option to save and finish yet
    assert result["menu_options"] == [
        "entity",
        "update_entity",
        "device",
        "availability",
    ]

    # assert we can update the entity, there is no select step
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "update_entity"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "entity"

    # submit the new common entity data, reset entity_picture
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "entity_platform_config"

    # submit the new entity platform config
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input=user_input_entity_details,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mqtt_platform_config"

    # submit the new platform specific mqtt data,
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input=user_input_mqtt,
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "summary_menu"

    # finish reconfigure flow
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "save_changes"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Check we still have out components
    new_components = deepcopy(dict(subentry.data))["components"]
    assert len(new_components) == 1

    # Check our update was successful
    assert "entity_picture" not in new_components[component_id]

    # Check the second component was updated
    for key, value in user_input_mqtt.items():
        assert new_components[component_id][key] == value

    # Check field are filtered out correctly
    for field in filtered_out_fields:
        assert field not in new_components[component_id]


@pytest.mark.parametrize(
    ("mqtt_config_subentries_data", "user_input_entity", "user_input_mqtt"),
    [
        (
            (
                ConfigSubentryData(
                    data=MOCK_NOTIFY_SUBENTRY_DATA_SINGLE,
                    subentry_type="device",
                    title="Mock subentry",
                ),
            ),
            {
                "platform": "notify",
                "name": "The second notifier",
                "entity_picture": "https://example.com",
            },
            {
                "command_topic": "test-topic2",
            },
        )
    ],
    ids=["notify_notify"],
)
async def test_subentry_reconfigure_add_entity(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    user_input_entity: dict[str, Any],
    user_input_mqtt: dict[str, Any],
) -> None:
    """Test the subentry ConfigFlow reconfigure and add an entity."""
    await mqtt_mock_entry()
    config_entry: MockConfigEntry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    subentry_id: str
    subentry: ConfigSubentry
    subentry_id, subentry = next(iter(config_entry.subentries.items()))
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, "device", subentry_id
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "summary_menu"

    # assert we have a device for the subentry
    device = device_registry.async_get_device(identifiers={(mqtt.DOMAIN, subentry_id)})
    assert device is not None

    # assert we have an entity for the subentry component
    components = deepcopy(dict(subentry.data))["components"]
    assert len(components) == 1
    component_id_1, component1 = next(iter(components.items()))
    unique_entity_id = f"{subentry_id}_{component_id_1}"
    entity_id = entity_registry.async_get_entity_id(
        domain=component1["platform"], platform=mqtt.DOMAIN, unique_id=unique_entity_id
    )
    assert entity_id is not None
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.config_subentry_id == subentry_id

    # assert menu options, we do not have the option to delete an entity
    # we have no option to save and finish yet
    assert result["menu_options"] == [
        "entity",
        "update_entity",
        "device",
        "availability",
    ]

    # assert we can update the entity, there is no select step
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "entity"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "entity"

    # submit the new common entity data
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input=user_input_entity,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mqtt_platform_config"

    # submit the new platform specific entity data
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input=user_input_mqtt,
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "summary_menu"

    # Finish reconfigure flow
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "save_changes"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Check we still have out components
    new_components = deepcopy(dict(subentry.data))["components"]
    assert len(new_components) == 2

    component_id_2 = next(iter(set(new_components) - {component_id_1}))

    # Check our new entity was added correctly
    expected_component_config = user_input_entity | user_input_mqtt
    for key, value in expected_component_config.items():
        assert new_components[component_id_2][key] == value


@pytest.mark.parametrize(
    "mqtt_config_subentries_data",
    [
        (
            ConfigSubentryData(
                data=MOCK_NOTIFY_SUBENTRY_DATA_MULTI,
                subentry_type="device",
                title="Mock subentry",
            ),
        )
    ],
)
async def test_subentry_reconfigure_update_device_properties(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the subentry ConfigFlow reconfigure and update device properties."""
    await mqtt_mock_entry()
    config_entry: MockConfigEntry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    subentry_id: str
    subentry: ConfigSubentry
    subentry_id, subentry = next(iter(config_entry.subentries.items()))
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, "device", subentry_id
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "summary_menu"

    # assert we have a device for the subentry
    device = device_registry.async_get_device(identifiers={(mqtt.DOMAIN, subentry_id)})
    assert device is not None

    # assert we have an entity for all subentry components
    components = deepcopy(dict(subentry.data))["components"]
    assert len(components) == 2

    # Assert initial data
    device = deepcopy(dict(subentry.data))["device"]
    assert device["name"] == "Milk notifier"
    assert device["sw_version"] == "1.0"
    assert device["hw_version"] == "2.1 rev a"
    assert device["model"] == "Model XL"
    assert device["model_id"] == "mn002"

    # assert menu options, we have the option to delete one entity
    # we have no option to save and finish yet
    assert result["menu_options"] == [
        "entity",
        "update_entity",
        "delete_entity",
        "device",
        "availability",
    ]

    # assert we can update the device properties
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "device"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device"

    # Update the device details
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "name": "Beer notifier",
            "sw_version": "1.1",
            "model": "Beer bottle XL",
            "model_id": "bn003",
            "configuration_url": "https://example.com",
        },
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "summary_menu"

    # finish reconfigure flow
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "save_changes"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Check our device was updated
    device = deepcopy(dict(subentry.data))["device"]
    assert device["name"] == "Beer notifier"
    assert "hw_version" not in device
    assert device["model"] == "Beer bottle XL"
    assert device["model_id"] == "bn003"


@pytest.mark.parametrize(
    "mqtt_config_subentries_data",
    [
        (
            ConfigSubentryData(
                data=MOCK_NOTIFY_SUBENTRY_DATA_MULTI,
                subentry_type="device",
                title="Mock subentry",
            ),
        )
    ],
)
async def test_subentry_reconfigure_availablity(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test the subentry ConfigFlow reconfigure and update device properties."""
    await mqtt_mock_entry()
    config_entry: MockConfigEntry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    subentry_id: str
    subentry: ConfigSubentry
    subentry_id, subentry = next(iter(config_entry.subentries.items()))

    expected_availability = {
        "availability_topic": "test/availability",
        "availability_template": "{{ value_json.availability }}",
        "payload_available": "online",
        "payload_not_available": "offline",
    }
    assert subentry.data.get("availability") == expected_availability

    result = await config_entry.start_subentry_reconfigure_flow(
        hass, "device", subentry_id
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "summary_menu"

    # assert we can set the availability config
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "availability"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "availability"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "availability_topic": "test/new_availability#invalid_topic",
            "payload_available": "1",
            "payload_not_available": "0",
        },
    )
    assert result["errors"] == {"availability_topic": "invalid_subscribe_topic"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "availability_topic": "test/new_availability",
            "payload_available": "1",
            "payload_not_available": "0",
        },
    )

    # finish reconfigure flow
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "save_changes"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Check the availability was updated
    expected_availability = {
        "availability_topic": "test/new_availability",
        "payload_available": "1",
        "payload_not_available": "0",
    }
    assert subentry.data.get("availability") == expected_availability

    # Assert we can reset the availability config
    result = await config_entry.start_subentry_reconfigure_flow(
        hass, "device", subentry_id
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "summary_menu"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "availability"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "availability"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "payload_available": "1",
            "payload_not_available": "0",
        },
    )

    # Finish reconfigure flow
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "save_changes"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Check the availability was updated
    assert subentry.data.get("availability") == {
        "payload_available": "1",
        "payload_not_available": "0",
    }
