"""Tests for certificate retrieval and decoding."""

import asyncio
import ssl
from unittest.mock import Mock, patch

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
import pytest

from homeassistant.components.cert_expiry.errors import (
    ConnectionTimeout,
    InvalidCACertificate,
    ValidationFailure,
)
from homeassistant.components.cert_expiry.helper import (
    async_get_cert,
    async_get_ssl_context,
    get_cert_expiry_timestamp,
    normalize_ca_certificates,
)
from homeassistant.core import HomeAssistant
from homeassistant.util.ssl import get_default_context, get_default_no_verify_context

from .const import HOST, PORT


@pytest.mark.parametrize(
    ("tls_options", "context"),
    [
        pytest.param({}, get_default_context(), id="default"),
        pytest.param({"verify_ssl": True}, get_default_context(), id="verified"),
        pytest.param(
            {"verify_ssl": False}, get_default_no_verify_context(), id="unverified"
        ),
    ],
)
async def test_get_certificate(
    hass: HomeAssistant,
    certificate_der: bytes,
    tls_options: dict[str, bool],
    context: ssl.SSLContext,
) -> None:
    """Retrieve raw bytes with SNI and the selected, unmodified TLS context."""
    transport = Mock(spec=asyncio.Transport)
    ssl_object = Mock(spec=ssl.SSLObject)
    ssl_object.getpeercert.return_value = certificate_der
    transport.get_extra_info.return_value = ssl_object

    with patch.object(
        hass.loop, "create_connection", return_value=(transport, Mock())
    ) as create_connection:
        assert await async_get_cert(hass, HOST, PORT, **tls_options) == certificate_der

    create_connection.assert_awaited_once_with(
        asyncio.Protocol,
        HOST,
        PORT,
        ssl=context,
        happy_eyeballs_delay=0.25,
        server_hostname=HOST,
    )
    transport.get_extra_info.assert_called_once_with("ssl_object")
    ssl_object.getpeercert.assert_called_once_with(binary_form=True)
    transport.close.assert_called_once_with()
    assert get_default_context().check_hostname
    assert get_default_context().verify_mode == ssl.CERT_REQUIRED
    assert not get_default_no_verify_context().check_hostname
    assert get_default_no_verify_context().verify_mode == ssl.CERT_NONE


@pytest.mark.parametrize(
    "verify_ssl",
    [pytest.param(True, id="verified"), pytest.param(False, id="unverified")],
)
async def test_certificate_expiry(
    hass: HomeAssistant,
    certificate: x509.Certificate,
    certificate_der: bytes,
    verify_ssl: bool,
) -> None:
    """Decode the raw certificate into a timezone-aware expiry timestamp."""
    with patch(
        "homeassistant.components.cert_expiry.helper.async_get_cert",
        return_value=certificate_der,
    ) as get_cert:
        assert (
            await get_cert_expiry_timestamp(hass, HOST, PORT, verify_ssl=verify_ssl)
            == certificate.not_valid_after_utc
        )

    get_cert.assert_awaited_once_with(
        hass, HOST, PORT, verify_ssl=verify_ssl, ssl_context=None
    )


@pytest.mark.parametrize(
    ("certificate_data", "error"),
    [
        pytest.param(None, "No certificate expiration found", id="missing"),
        pytest.param(
            b"invalid certificate", "Invalid certificate received", id="invalid"
        ),
    ],
)
async def test_invalid_certificate(
    hass: HomeAssistant, certificate_data: bytes | None, error: str
) -> None:
    """Report missing and malformed certificates as validation failures."""
    with (
        patch(
            "homeassistant.components.cert_expiry.helper.async_get_cert",
            return_value=certificate_data,
        ),
        pytest.raises(ValidationFailure, match=error),
    ):
        await get_cert_expiry_timestamp(hass, HOST, PORT)


async def test_unsupported_certificate_version(
    hass: HomeAssistant, unsupported_certificate_der: bytes
) -> None:
    """Map an unsupported peer certificate version to a validation failure."""
    with (
        patch(
            "homeassistant.components.cert_expiry.helper.async_get_cert",
            return_value=unsupported_certificate_der,
        ),
        pytest.raises(ValidationFailure, match="Invalid certificate received") as exc,
    ):
        await get_cert_expiry_timestamp(hass, HOST, PORT)

    assert isinstance(exc.value.__cause__, x509.InvalidVersion)


async def test_transport_closed_on_certificate_error(hass: HomeAssistant) -> None:
    """Close a successful TLS connection even when reading its certificate fails."""
    transport = Mock(spec=asyncio.Transport)
    ssl_object = Mock(spec=ssl.SSLObject)
    ssl_object.getpeercert.side_effect = ValueError("certificate unavailable")
    transport.get_extra_info.return_value = ssl_object

    with (
        patch.object(hass.loop, "create_connection", return_value=(transport, Mock())),
        pytest.raises(ValueError, match="certificate unavailable"),
    ):
        await async_get_cert(hass, HOST, PORT)

    transport.close.assert_called_once_with()


async def test_connection_timeout_cancels_handshake(hass: HomeAssistant) -> None:
    """Cancel a stalled connection rather than leaving its handshake running."""
    cancelled = asyncio.Event()

    async def stalled_connection(*_args: object, **_kwargs: object) -> None:
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with (
        patch.object(hass.loop, "create_connection", side_effect=stalled_connection),
        patch("homeassistant.components.cert_expiry.helper.TIMEOUT", 0),
        pytest.raises(ConnectionTimeout),
    ):
        await get_cert_expiry_timestamp(hass, HOST, PORT)

    assert cancelled.is_set()


@pytest.mark.parametrize(
    ("verify_ssl", "context"),
    [
        pytest.param(True, get_default_context(), id="verified"),
        pytest.param(False, get_default_no_verify_context(), id="unverified"),
    ],
)
async def test_default_ssl_context(
    hass: HomeAssistant, verify_ssl: bool, context: ssl.SSLContext
) -> None:
    """Reuse the existing contexts when no custom certificates are configured."""
    assert await async_get_ssl_context(hass, verify_ssl=verify_ssl) is context


async def test_custom_ca_context(
    hass: HomeAssistant, ca_certificate: x509.Certificate
) -> None:
    """Add custom trust to an independent context retaining the normal CA bundle."""
    shared = get_default_context()
    original_certs = shared.get_ca_certs(binary_form=True)
    ca_pem = ca_certificate.public_bytes(Encoding.PEM).decode("ascii")

    context = await async_get_ssl_context(hass, ca_certificates=ca_pem)

    assert context is not shared
    assert context.check_hostname
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert set(original_certs).issubset(context.get_ca_certs(binary_form=True))
    assert ca_certificate.public_bytes(Encoding.DER) in context.get_ca_certs(
        binary_form=True
    )
    assert shared.get_ca_certs(binary_form=True) == original_certs
    assert shared.check_hostname
    assert shared.verify_mode == ssl.CERT_REQUIRED


async def test_ca_not_used_without_verification(
    hass: HomeAssistant, certificate_pem: str
) -> None:
    """Configured CA data does not enable verification when it was disabled."""
    assert (
        await async_get_ssl_context(
            hass, verify_ssl=False, ca_certificates=certificate_pem
        )
        is get_default_no_verify_context()
    )


@pytest.mark.parametrize(
    "ca_data",
    [
        pytest.param("not a certificate", id="text"),
        pytest.param("\u00e9", id="non-ascii"),
        pytest.param("-----BEGIN CERTIFICATE-----\n", id="incomplete"),
        pytest.param(
            "-----BEGIN CERTIFICATE-----\nZmFrZQ==\n-----END CERTIFICATE-----\n",
            id="base64-without-x509",
        ),
    ],
)
async def test_invalid_ca_context(hass: HomeAssistant, ca_data: str) -> None:
    """Reject malformed certificates before attempting a network connection."""
    with pytest.raises(InvalidCACertificate):
        await async_get_ssl_context(hass, ca_certificates=ca_data)


def test_unsupported_ca_version(unsupported_certificate_pem: str) -> None:
    """Map an unsupported CA certificate version to an invalid CA error."""
    with pytest.raises(InvalidCACertificate) as exc:
        normalize_ca_certificates(unsupported_certificate_pem)

    assert isinstance(exc.value.__cause__, x509.InvalidVersion)


@pytest.mark.parametrize(
    "extra_data",
    [
        pytest.param("not a certificate", id="trailing-text"),
        pytest.param("-----BEGIN CERTIFICATE-----\n", id="partial-certificate"),
        pytest.param(
            "-----BEGIN PRIVATE KEY-----\nZmFrZQ==\n-----END PRIVATE KEY-----\n",
            id="private-key",
        ),
    ],
)
def test_ca_bundle_rejects_other_data(certificate_pem: str, extra_data: str) -> None:
    """Reject data that would otherwise be silently stored alongside certificates."""
    with pytest.raises(InvalidCACertificate):
        normalize_ca_certificates(certificate_pem + extra_data)


def test_ca_bundle(certificate_pem: str, ca_certificate: x509.Certificate) -> None:
    """Support multiple trusted certificates and normalize outer whitespace."""
    bundle = certificate_pem + ca_certificate.public_bytes(Encoding.PEM).decode("ascii")
    assert normalize_ca_certificates(f" \n{bundle}\n\t ") == bundle


@pytest.mark.parametrize("ca_data", ["", " \n\t "])
def test_empty_ca_bundle(ca_data: str) -> None:
    """Normalize a cleared field to the same empty string used by default."""
    assert normalize_ca_certificates(ca_data) == ""
