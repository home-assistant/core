"""Tests for the Cert Expiry config flow."""
import socket
import ssl
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.cert_expiry.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import HOST, PORT
from .helpers import future_timestamp

from tests.common import MockConfigEntry


async def test_user(hass: HomeAssistant) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_expiry_timestamp"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST, CONF_PORT: PORT}
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["result"].unique_id == f"{HOST}:{PORT}"

    with patch("homeassistant.components.cert_expiry.sensor.async_setup_entry"):
        await hass.async_block_till_done()


async def test_user_with_bad_cert(hass: HomeAssistant) -> None:
    """Test user config with bad certificate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=ssl.SSLError("some error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST, CONF_PORT: PORT}
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["result"].unique_id == f"{HOST}:{PORT}"

    with patch("homeassistant.components.cert_expiry.sensor.async_setup_entry"):
        await hass.async_block_till_done()


async def test_import_host_only(hass: HomeAssistant) -> None:
    """Test import with host only."""
    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_expiry_timestamp"
    ), patch(
        "homeassistant.components.cert_expiry.get_cert_expiry_timestamp",
        return_value=future_timestamp(1),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_HOST: HOST},
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == DEFAULT_PORT
    assert result["result"].unique_id == f"{HOST}:{DEFAULT_PORT}"


async def test_import_host_and_port(hass: HomeAssistant) -> None:
    """Test import with host and port."""
    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_expiry_timestamp"
    ), patch(
        "homeassistant.components.cert_expiry.get_cert_expiry_timestamp",
        return_value=future_timestamp(1),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_HOST: HOST, CONF_PORT: PORT},
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["result"].unique_id == f"{HOST}:{PORT}"


async def test_import_non_default_port(hass: HomeAssistant) -> None:
    """Test import with host and non-default port."""
    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_expiry_timestamp"
    ), patch(
        "homeassistant.components.cert_expiry.get_cert_expiry_timestamp",
        return_value=future_timestamp(1),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_HOST: HOST, CONF_PORT: 888},
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{HOST}:888"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == 888
    assert result["result"].unique_id == f"{HOST}:888"


async def test_import_with_name(hass: HomeAssistant) -> None:
    """Test import with name (deprecated)."""
    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_expiry_timestamp"
    ), patch(
        "homeassistant.components.cert_expiry.get_cert_expiry_timestamp",
        return_value=future_timestamp(1),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_NAME: "legacy", CONF_HOST: HOST, CONF_PORT: PORT},
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["result"].unique_id == f"{HOST}:{PORT}"


async def test_bad_import(hass: HomeAssistant) -> None:
    """Test import step."""
    with patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=ConnectionRefusedError(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_HOST: HOST},
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "import_failed"


async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if the cert is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_HOST: HOST, CONF_PORT: PORT},
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: HOST, CONF_PORT: PORT},
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_abort_on_socket_failed(hass: HomeAssistant) -> None:
    """Test we abort of we have errors during socket creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=socket.gaierror(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST}
        )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "resolve_failed"}

    with patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=socket.timeout(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST}
        )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "connection_timeout"}

    with patch(
        "homeassistant.components.cert_expiry.helper.get_cert",
        side_effect=ConnectionRefusedError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST}
        )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "connection_refused"}
