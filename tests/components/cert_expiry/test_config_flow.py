"""Tests for the Cert Expiry config flow."""

import socket
import ssl
from unittest.mock import ANY, patch

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
import pytest

from homeassistant import config_entries
from homeassistant.components.cert_expiry.const import CONF_CA_CERTIFICATES, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import HOST, PORT

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.parametrize(
    ("tls_options", "verify_ssl"),
    [
        pytest.param({}, True, id="default"),
        pytest.param({CONF_VERIFY_SSL: True}, True, id="verified"),
        pytest.param({CONF_VERIFY_SSL: False}, False, id="unverified"),
    ],
)
async def test_user(
    hass: HomeAssistant, tls_options: dict[str, bool], verify_ssl: bool
) -> None:
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
            result["flow_id"],
            user_input={CONF_HOST: HOST, CONF_PORT: PORT, **tls_options},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["data"][CONF_VERIFY_SSL] is verify_ssl
    assert result["data"][CONF_CA_CERTIFICATES] == ""
    assert result["result"].unique_id == f"{HOST}:{PORT}"


@pytest.mark.parametrize(
    "whitespace",
    [pytest.param("", id="pem"), pytest.param(" \n\t ", id="outer-whitespace")],
)
async def test_user_with_ca_certificates(
    hass: HomeAssistant, certificate_pem: str, whitespace: str
) -> None:
    """Persist normalized CA certificates after validating them."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_expiry_timestamp"
    ) as get_timestamp:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_CA_CERTIFICATES: whitespace + certificate_pem + whitespace,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CA_CERTIFICATES] == certificate_pem
    assert result["result"].unique_id == f"{HOST}:{PORT}"
    get_timestamp.assert_awaited_once_with(
        hass, HOST, PORT, verify_ssl=True, ssl_context=ANY
    )


@pytest.mark.parametrize(
    "verify_ssl",
    [pytest.param(True, id="verified"), pytest.param(False, id="unverified")],
)
async def test_invalid_ca_certificates_recovers(
    hass: HomeAssistant, certificate_pem: str, verify_ssl: bool
) -> None:
    """Show a field error for invalid CA input and allow correcting it."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_expiry_timestamp"
    ) as get_timestamp:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_VERIFY_SSL: verify_ssl,
                CONF_CA_CERTIFICATES: "-----BEGIN CERTIFICATE-----\nZmFrZQ==\n-----END CERTIFICATE-----",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_CA_CERTIFICATES: "invalid_ca_certificates"}
        get_timestamp.assert_not_awaited()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_VERIFY_SSL: verify_ssl,
                CONF_CA_CERTIFICATES: certificate_pem,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CA_CERTIFICATES] == certificate_pem
    assert result["data"][CONF_VERIFY_SSL] is verify_ssl

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
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: HOST, CONF_PORT: PORT}
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

    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_expiry_timestamp"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: HOST}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


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
    ("initial_options", "verify_ssl"),
    [
        pytest.param({}, False, id="legacy-entry"),
        pytest.param({CONF_VERIFY_SSL: True}, False, id="disable-verification"),
        pytest.param({CONF_VERIFY_SSL: False}, True, id="enable-verification"),
    ],
)
async def test_reconfigure_verification(
    hass: HomeAssistant, initial_options: dict[str, bool], verify_ssl: bool
) -> None:
    """Allow changing verification without replacing the config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT, **initial_options},
        unique_id=f"{HOST}:{PORT}",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_expiry_timestamp"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_VERIFY_SSL: verify_ssl,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_VERIFY_SSL] is verify_ssl
    assert entry.unique_id == f"{HOST}:{PORT}"


@pytest.mark.parametrize(
    ("initial_bundle", "new_bundle", "expected_bundle"),
    [
        pytest.param("empty", "first", "first", id="add"),
        pytest.param("first", "second", "second", id="replace"),
        pytest.param("first", "empty", "empty", id="clear"),
        pytest.param("first", "whitespace", "empty", id="clear-with-whitespace"),
    ],
)
async def test_reconfigure_ca_certificates(
    hass: HomeAssistant,
    certificate_pem: str,
    ca_certificate: x509.Certificate,
    initial_bundle: str,
    new_bundle: str,
    expected_bundle: str,
) -> None:
    """Allow adding, replacing, and clearing trusted certificates on an entry."""
    bundles = {
        "empty": "",
        "first": certificate_pem,
        "second": ca_certificate.public_bytes(Encoding.PEM).decode("ascii"),
        "whitespace": " \n\t ",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_VERIFY_SSL: True,
            CONF_CA_CERTIFICATES: bundles[initial_bundle],
        },
        unique_id=f"{HOST}:{PORT}",
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.cert_expiry.config_flow.get_cert_expiry_timestamp"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_VERIFY_SSL: True,
                CONF_CA_CERTIFICATES: bundles[new_bundle],
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_CA_CERTIFICATES] == bundles[expected_bundle]
    assert entry.unique_id == f"{HOST}:{PORT}"


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
