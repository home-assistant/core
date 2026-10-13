"""Test certificate monitoring against a local TLS server."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
import ssl
from unittest.mock import Mock, patch

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
import pytest
import pytest_socket

from homeassistant.components.cert_expiry.const import CONF_CA_CERTIFICATES, DOMAIN
from homeassistant.components.cert_expiry.errors import ValidationFailure
from homeassistant.components.cert_expiry.helper import (
    async_get_ssl_context,
    get_cert_expiry_timestamp,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_VERIFY_SSL, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util.ssl import create_client_context, get_default_context

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("socket_enabled")

# Python's ssl module does not expose OpenSSL's verification code constants.
X509_V_ERR_CERT_NOT_YET_VALID = 9
X509_V_ERR_CERT_HAS_EXPIRED = 10
X509_V_ERR_DEPTH_ZERO_SELF_SIGNED_CERT = 18
X509_V_ERR_IP_ADDRESS_MISMATCH = 64


@pytest.fixture(autouse=True)
def allow_loopback() -> None:
    """Permit both loopback addresses used by localhost and Happy Eyeballs."""
    pytest_socket.socket_allow_hosts(["127.0.0.1", "::1"])


@pytest.fixture
async def ignore_tls_client_abort(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Allow the local server's expected reset when the client rejects its cert."""
    original_handler = hass.loop.get_exception_handler()
    assert original_handler is not None

    def handle_exception(
        loop: asyncio.AbstractEventLoop, context: dict[str, object]
    ) -> None:
        if (
            isinstance(context.get("exception"), ConnectionResetError)
            and context.get("message")
            == "Error on transport creation for incoming connection"
        ):
            return
        original_handler(loop, context)

    hass.loop.set_exception_handler(handle_exception)
    try:
        yield
        await hass.async_block_till_done()
    finally:
        hass.loop.set_exception_handler(original_handler)


@pytest.fixture
def server_context(
    tmp_path: Path,
    certificate_key: ec.EllipticCurvePrivateKey,
    certificate_pem: str,
    request: pytest.FixtureRequest,
) -> ssl.SSLContext:
    """Load the test server's certificate and private key."""
    cert_path = tmp_path / "certificate.pem"
    key_path = tmp_path / "key.pem"
    if hasattr(request, "param"):
        certificate_pem = request.getfixturevalue(request.param)
    cert_path.write_text(certificate_pem, encoding="ascii")
    key_path.write_bytes(
        certificate_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    return context


@pytest.fixture
async def tls_port(
    hass: HomeAssistant, server_context: ssl.SSLContext
) -> AsyncGenerator[int]:
    """Serve TLS on an ephemeral loopback port."""
    server = await hass.loop.create_server(
        asyncio.Protocol, "127.0.0.1", 0, ssl=server_context
    )
    async with server:
        yield server.sockets[0].getsockname()[1]


@pytest.fixture
def trusted_context(certificate: x509.Certificate) -> ssl.SSLContext:
    """Trust the local certificate without modifying shared contexts."""
    context = create_client_context()
    context.load_verify_locations(
        cadata=certificate.public_bytes(serialization.Encoding.PEM).decode("ascii")
    )
    return context


@pytest.mark.parametrize(
    "certificate_dates",
    [
        pytest.param(
            (datetime(2020, 1, 1, tzinfo=UTC), datetime(2100, 1, 1, tzinfo=UTC)),
            id="self-signed",
        ),
        pytest.param(
            (datetime(2010, 1, 1, tzinfo=UTC), datetime(2020, 1, 1, tzinfo=UTC)),
            id="expired",
        ),
        pytest.param(
            (datetime(2090, 1, 1, tzinfo=UTC), datetime(2100, 1, 1, tzinfo=UTC)),
            id="not-yet-valid",
        ),
    ],
)
async def test_unverified_tls_sensor(
    hass: HomeAssistant,
    certificate: x509.Certificate,
    tls_port: int,
    server_context: ssl.SSLContext,
) -> None:
    """Monitor presented certificates even when their trust or dates are invalid."""
    sni_callback = Mock(return_value=None)
    server_context.set_servername_callback(sni_callback)
    shared_context = get_default_context()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "localhost", CONF_PORT: tls_port, CONF_VERIFY_SSL: False},
        unique_id=f"localhost:{tls_port}",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.localhost_{tls_port}_cert_expiry")
    assert state is not None
    assert state.state == certificate.not_valid_after_utc.isoformat()
    assert state.attributes["is_valid"] is False
    assert state.attributes["error"] is None
    assert sni_callback.call_args.args[1] == "localhost"
    assert get_default_context() is shared_context
    assert shared_context.check_hostname
    assert shared_context.verify_mode == ssl.CERT_REQUIRED


@pytest.mark.parametrize(
    "server_context",
    [pytest.param("unsupported_certificate_pem", id="unsupported-version")],
    indirect=True,
)
async def test_unverified_tls_unsupported_version(
    hass: HomeAssistant, tls_port: int
) -> None:
    """Keep an unsupported peer certificate available with a validation error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "localhost", CONF_PORT: tls_port, CONF_VERIFY_SSL: False},
        unique_id=f"localhost:{tls_port}",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.localhost_{tls_port}_cert_expiry")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["is_valid"] is False
    assert state.attributes["error"] == (
        f"Invalid certificate received from: localhost:{tls_port}"
    )


@pytest.mark.usefixtures("ignore_tls_client_abort")
async def test_untrusted_tls_certificate(hass: HomeAssistant, tls_port: int) -> None:
    """Default verification rejects a self-signed certificate."""
    with pytest.raises(ValidationFailure) as exc:
        await get_cert_expiry_timestamp(hass, "localhost", tls_port)

    cause = exc.value.__cause__
    assert isinstance(cause, ssl.SSLCertVerificationError)
    assert cause.verify_code == X509_V_ERR_DEPTH_ZERO_SELF_SIGNED_CERT


async def test_trusted_tls_certificate(
    hass: HomeAssistant,
    tls_port: int,
    certificate: x509.Certificate,
    trusted_context: ssl.SSLContext,
) -> None:
    """Verification still retrieves the expiry of a trusted certificate."""
    with patch(
        "homeassistant.components.cert_expiry.helper.get_default_context",
        return_value=trusted_context,
    ):
        assert (
            await get_cert_expiry_timestamp(hass, "localhost", tls_port)
            == certificate.not_valid_after_utc
        )


@pytest.mark.parametrize(
    ("certificate_dates", "verify_code"),
    [
        pytest.param(
            (datetime(2010, 1, 1, tzinfo=UTC), datetime(2020, 1, 1, tzinfo=UTC)),
            X509_V_ERR_CERT_HAS_EXPIRED,
            id="expired",
        ),
        pytest.param(
            (datetime(2090, 1, 1, tzinfo=UTC), datetime(2100, 1, 1, tzinfo=UTC)),
            X509_V_ERR_CERT_NOT_YET_VALID,
            id="not-yet-valid",
        ),
    ],
)
@pytest.mark.usefixtures("ignore_tls_client_abort")
async def test_verified_tls_invalid_dates(
    hass: HomeAssistant,
    tls_port: int,
    trusted_context: ssl.SSLContext,
    verify_code: int,
) -> None:
    """Trusting a certificate still enforces its validity period."""
    with (
        patch(
            "homeassistant.components.cert_expiry.helper.get_default_context",
            return_value=trusted_context,
        ),
        pytest.raises(ValidationFailure) as exc,
    ):
        await get_cert_expiry_timestamp(hass, "localhost", tls_port)

    cause = exc.value.__cause__
    assert isinstance(cause, ssl.SSLCertVerificationError)
    assert cause.verify_code == verify_code


@pytest.mark.usefixtures("ignore_tls_client_abort")
async def test_tls_hostname_mismatch(
    hass: HomeAssistant, tls_port: int, trusted_context: ssl.SSLContext
) -> None:
    """Trusting a certificate does not disable hostname verification."""
    with (
        patch(
            "homeassistant.components.cert_expiry.helper.get_default_context",
            return_value=trusted_context,
        ),
        pytest.raises(ValidationFailure) as exc,
    ):
        await get_cert_expiry_timestamp(hass, "127.0.0.1", tls_port)

    cause = exc.value.__cause__
    assert isinstance(cause, ssl.SSLCertVerificationError)
    assert cause.verify_code == X509_V_ERR_IP_ADDRESS_MISMATCH


@pytest.mark.parametrize("certificate", ["private-ca"], indirect=True)
async def test_private_ca_tls_sensor(
    hass: HomeAssistant,
    certificate: x509.Certificate,
    ca_certificate: x509.Certificate,
    tls_port: int,
) -> None:
    """Verify a real CA-issued certificate using only the entry's extra trust."""
    shared_certificates = get_default_context().get_ca_certs(binary_form=True)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "localhost",
            CONF_PORT: tls_port,
            CONF_VERIFY_SSL: True,
            CONF_CA_CERTIFICATES: ca_certificate.public_bytes(
                serialization.Encoding.PEM
            ).decode("ascii"),
        },
        unique_id=f"localhost:{tls_port}",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.localhost_{tls_port}_cert_expiry")
    assert state is not None
    assert state.state == certificate.not_valid_after_utc.isoformat()
    assert state.attributes["is_valid"] is True
    assert state.attributes["error"] is None
    assert get_default_context().get_ca_certs(binary_form=True) == shared_certificates


@pytest.mark.parametrize("certificate", ["private-ca"], indirect=True)
@pytest.mark.usefixtures("ignore_tls_client_abort")
async def test_private_ca_hostname_mismatch(
    hass: HomeAssistant, ca_certificate: x509.Certificate, tls_port: int
) -> None:
    """Additional CA trust does not weaken hostname validation."""
    context = await async_get_ssl_context(
        hass,
        ca_certificates=ca_certificate.public_bytes(serialization.Encoding.PEM).decode(
            "ascii"
        ),
    )
    with pytest.raises(ValidationFailure) as exc:
        await get_cert_expiry_timestamp(
            hass, "127.0.0.1", tls_port, ssl_context=context
        )

    cause = exc.value.__cause__
    assert isinstance(cause, ssl.SSLCertVerificationError)
    assert cause.verify_code == X509_V_ERR_IP_ADDRESS_MISMATCH
