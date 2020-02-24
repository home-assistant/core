"""Tests for the Cert Expiry config flow."""
import socket
import ssl

from asynctest import patch

from homeassistant import data_entry_flow
from homeassistant.components.cert_expiry.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from .const import HOST, PORT

from tests.common import MockConfigEntry


async def test_user(hass):
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_time_to_expiry"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST, CONF_PORT: PORT}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["result"].unique_id == f"{HOST}:{PORT}"

    with patch("homeassistant.components.cert_expiry.sensor.async_setup_entry"):
        await hass.async_block_till_done()


async def test_user_with_bad_cert(hass):
    """Test user config with bad certificate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=ssl.SSLError("some error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST, CONF_PORT: PORT}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["result"].unique_id == f"{HOST}:{PORT}"

    with patch("homeassistant.components.cert_expiry.sensor.async_setup_entry"):
        await hass.async_block_till_done()


async def test_import_host_only(hass):
    """Test import with host only."""
    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_time_to_expiry",
        return_value=1,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "import"}, data={CONF_HOST: HOST}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == DEFAULT_PORT
    assert result["result"].unique_id == f"{HOST}:{DEFAULT_PORT}"

    with patch("homeassistant.components.cert_expiry.sensor.async_setup_entry"):
        await hass.async_block_till_done()


async def test_import_host_and_port(hass):
    """Test import with host and port."""
    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_time_to_expiry",
        return_value=1,
    ):
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

    with patch("homeassistant.components.cert_expiry.sensor.async_setup_entry"):
        await hass.async_block_till_done()


async def test_import_non_default_port(hass):
    """Test import with host and non-default port."""
    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_time_to_expiry"
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "import"}, data={CONF_HOST: HOST, CONF_PORT: 888}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == f"{HOST}:888"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == 888
    assert result["result"].unique_id == f"{HOST}:888"

    with patch("homeassistant.components.cert_expiry.sensor.async_setup_entry"):
        await hass.async_block_till_done()


async def test_import_with_name(hass):
    """Test import with name (deprecated)."""
    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_time_to_expiry",
        return_value=1,
    ):
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

    with patch("homeassistant.components.cert_expiry.sensor.async_setup_entry"):
        await hass.async_block_till_done()


async def test_bad_import(hass):
    """Test import step."""
    with patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=ConnectionRefusedError(),
    ):
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

    with patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=socket.gaierror(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "resolve_failed"}

    with patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=socket.timeout(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "connection_timeout"}

    with patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=ConnectionRefusedError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "connection_refused"}
