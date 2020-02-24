"""Tests for the Cert Expiry config flow."""
import socket
import ssl
from unittest.mock import patch

from asynctest import patch as asyncpatch

from homeassistant import data_entry_flow
from homeassistant.components.cert_expiry.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, STATE_UNAVAILABLE

from tests.common import MockConfigEntry

PORT = 443
HOST = "example.com"
GET_CERT_METHOD = "homeassistant.components.cert_expiry.helper.get_cert"
GET_CERT_TIME_METHOD = (
    "homeassistant.components.cert_expiry.config_flow.get_cert_time_to_expiry"
)
GET_SENSOR_CERT_TIME_METHOD = (
    "homeassistant.components.cert_expiry.sensor.get_cert_time_to_expiry"
)


async def test_user(hass):
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with asyncpatch(GET_CERT_TIME_METHOD):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST, CONF_PORT: PORT}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["result"].unique_id == f"{HOST}:{PORT}"

    with asyncpatch(GET_SENSOR_CERT_TIME_METHOD, return_value=100):
        await hass.async_block_till_done()

    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "100"
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")


async def test_user_with_bad_cert(hass):
    """Test user config with bad certificate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(GET_CERT_METHOD, side_effect=ssl.SSLError("some error")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST, CONF_PORT: PORT}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["result"].unique_id == f"{HOST}:{PORT}"

    with patch(GET_CERT_METHOD, side_effect=ssl.SSLError("some error")):
        await hass.async_block_till_done()

    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "0"
    assert state.attributes.get("error") == "some error"
    assert not state.attributes.get("is_valid")


async def test_import_host_only(hass):
    """Test import with host only."""
    with asyncpatch(GET_CERT_TIME_METHOD, return_value=1):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "import"}, data={CONF_HOST: HOST}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == DEFAULT_PORT
    assert result["result"].unique_id == f"{HOST}:{DEFAULT_PORT}"

    with asyncpatch(GET_SENSOR_CERT_TIME_METHOD, return_value=100):
        await hass.async_block_till_done()
    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")
    assert state.state == "100"


async def test_import_host_and_port(hass):
    """Test import with host and port."""
    with asyncpatch(GET_CERT_TIME_METHOD, return_value=1):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={CONF_HOST: HOST, CONF_PORT: PORT},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["result"].unique_id == f"{HOST}:{PORT}"

    with asyncpatch(GET_SENSOR_CERT_TIME_METHOD, return_value=100):
        await hass.async_block_till_done()
    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")
    assert state.state == "100"


async def test_import_non_default_port(hass):
    """Test import with host and non-default port."""
    with asyncpatch(GET_CERT_TIME_METHOD):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "import"}, data={CONF_HOST: HOST, CONF_PORT: 888}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == f"{HOST}:888"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == 888
    assert result["result"].unique_id == f"{HOST}:888"

    with asyncpatch(GET_SENSOR_CERT_TIME_METHOD, return_value=100):
        await hass.async_block_till_done()
    state = hass.states.get("sensor.cert_expiry_example_com_888")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")
    assert state.state == "100"


async def test_import_with_name(hass):
    """Test import with name (deprecated)."""
    with asyncpatch(GET_CERT_TIME_METHOD, return_value=1):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={CONF_NAME: "legacy", CONF_HOST: HOST, CONF_PORT: PORT},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["result"].unique_id == f"{HOST}:{PORT}"

    with asyncpatch(GET_SENSOR_CERT_TIME_METHOD, return_value=100):
        await hass.async_block_till_done()
    state = hass.states.get("sensor.cert_expiry_example_com")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes.get("error") == "None"
    assert state.attributes.get("is_valid")
    assert state.state == "100"


async def test_bad_import(hass):
    """Test import step."""
    with patch(GET_CERT_METHOD, side_effect=ConnectionRefusedError()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "import"}, data={CONF_HOST: HOST}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "import_failed"


async def test_abort_if_already_setup(hass):
    """Test we abort if the cert is already setup."""
    MockConfigEntry(
        domain="cert_expiry",
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data={CONF_HOST: HOST, CONF_PORT: PORT}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data={CONF_HOST: HOST, CONF_PORT: PORT}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_abort_on_socket_failed(hass):
    """Test we abort of we have errors during socket creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    with patch(GET_CERT_METHOD, side_effect=socket.gaierror()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "resolve_failed"}

    with patch(GET_CERT_METHOD, side_effect=socket.timeout()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "connection_timeout"}

    with patch(GET_CERT_METHOD, side_effect=ConnectionRefusedError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "connection_refused"}
