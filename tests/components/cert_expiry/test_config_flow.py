"""Tests for the Cert Expiry config flow."""

import socket
import ssl
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.cert_expiry.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import HOST, PORT

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user(hass: HomeAssistant) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_expiry_timestamp"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST, CONF_PORT: PORT}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["result"].unique_id == f"{HOST}:{PORT}"


async def test_user_with_bad_cert(hass: HomeAssistant) -> None:
    """Test user config with bad certificate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.cert_expiry.helper.async_get_cert",
        side_effect=ssl.SSLError("some error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST, CONF_PORT: PORT}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["result"].unique_id == f"{HOST}:{PORT}"


async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if the cert is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: HOST, CONF_PORT: PORT},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_abort_on_socket_failed(hass: HomeAssistant) -> None:
    """Test we abort of we have errors during socket creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.cert_expiry.helper.async_get_cert",
        side_effect=socket.gaierror(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "resolve_failed"}

    with patch(
        "homeassistant.components.cert_expiry.helper.async_get_cert",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "connection_timeout"}

    with patch(
        "homeassistant.components.cert_expiry.helper.async_get_cert",
        side_effect=ConnectionRefusedError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "connection_refused"}

    with patch(
        "homeassistant.components.cert_expiry.helper.async_get_cert",
        side_effect=ConnectionResetError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "connection_reset"}


async def test_reconfigure_successful(hass: HomeAssistant) -> None:
    """Test reconfiguration of an existing entry updates its data and unique_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_host = "new.example.com"
    new_port = 8443
    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_expiry_timestamp"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: new_host, CONF_PORT: new_port}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == new_host
    assert entry.data[CONF_PORT] == new_port
    assert entry.unique_id == f"{new_host}:{new_port}"


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (socket.gaierror(), "resolve_failed"),
        (TimeoutError, "connection_timeout"),
        (ConnectionRefusedError, "connection_refused"),
        (ConnectionResetError, "connection_reset"),
    ],
)
async def test_reconfigure_validation_failure_recovers(
    hass: HomeAssistant, side_effect: Exception, error_key: str
) -> None:
    """Test the reconfigure form re-shows on failure then recovers on retry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_host = "new.example.com"
    new_port = 8443

    with patch(
        "homeassistant.components.cert_expiry.helper.async_get_cert",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: new_host, CONF_PORT: new_port},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {CONF_HOST: error_key}
    assert entry.data[CONF_HOST] == HOST
    assert entry.data[CONF_PORT] == PORT

    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_expiry_timestamp"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: new_host, CONF_PORT: new_port},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == new_host
    assert entry.data[CONF_PORT] == new_port
    assert entry.unique_id == f"{new_host}:{new_port}"


async def test_reconfigure_already_exists(hass: HomeAssistant) -> None:
    """Test reconfiguration aborts when target host:port matches another entry."""
    other_host = "other.example.com"
    other_port = 8443
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: other_host, CONF_PORT: other_port},
        unique_id=f"{other_host}:{other_port}",
    ).add_to_hass(hass)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: other_host, CONF_PORT: other_port},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == HOST
    assert entry.data[CONF_PORT] == PORT
