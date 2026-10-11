"""Configuration for cert_expiry tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.cert_expiry.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def certificate_key() -> ec.EllipticCurvePrivateKey:
    """Generate a key for the test certificate."""
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def certificate(certificate_key: ec.EllipticCurvePrivateKey) -> x509.Certificate:
    """Create a self-signed certificate valid independently of the test clock."""
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(certificate_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime(2020, 1, 1, tzinfo=UTC))
        .not_valid_after(datetime(2100, 1, 1, tzinfo=UTC))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False
        )
        .sign(certificate_key, hashes.SHA256())
    )


@pytest.fixture
def certificate_der(certificate: x509.Certificate) -> bytes:
    """Return the test certificate in DER format."""
    return certificate.public_bytes(serialization.Encoding.DER)
