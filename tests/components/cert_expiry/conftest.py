"""Configuration for cert_expiry tests."""

from collections.abc import Generator
from datetime import UTC, datetime
import ssl
from unittest.mock import AsyncMock, patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
import pytest
from pytest_homeassistant.patch_time import ha_datetime_to_fakedatetime


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.cert_expiry.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def certificate_key() -> ec.EllipticCurvePrivateKey:
    """Generate a key for the test certificate."""
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def certificate_dates() -> tuple[datetime, datetime]:
    """Keep the test certificate valid independently of the test clock."""
    return datetime(2020, 1, 1, tzinfo=UTC), datetime(2100, 1, 1, tzinfo=UTC)


def _certificate_builder(
    certificate_dates: tuple[datetime, datetime],
) -> x509.CertificateBuilder:
    """Use consistent datetime types when signing test certificates."""
    # Cryptography can cache a fake datetime type while the clock is frozen.
    return (
        x509.CertificateBuilder()
        .not_valid_before(ha_datetime_to_fakedatetime(certificate_dates[0]))
        .not_valid_after(ha_datetime_to_fakedatetime(certificate_dates[1]))
    )


@pytest.fixture
def certificate(
    certificate_key: ec.EllipticCurvePrivateKey,
    certificate_dates: tuple[datetime, datetime],
    ca_signed_certificate: x509.Certificate,
    request: pytest.FixtureRequest,
) -> x509.Certificate:
    """Create a self-signed certificate valid independently of the test clock."""
    if getattr(request, "param", None) == "private-ca":
        return ca_signed_certificate
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    return (
        _certificate_builder(certificate_dates)
        .subject_name(name)
        .issuer_name(name)
        .public_key(certificate_key.public_key())
        .serial_number(x509.random_serial_number())
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False
        )
        .sign(certificate_key, hashes.SHA256())
    )


@pytest.fixture
def certificate_der(certificate: x509.Certificate) -> bytes:
    """Return the test certificate in DER format."""
    return certificate.public_bytes(serialization.Encoding.DER)


@pytest.fixture
def certificate_pem(certificate: x509.Certificate) -> str:
    """Return the test certificate in PEM format."""
    return certificate.public_bytes(serialization.Encoding.PEM).decode("ascii")


@pytest.fixture
def unsupported_certificate_der(certificate_der: bytes) -> bytes:
    """Use X.509 v2, which OpenSSL accepts but cryptography cannot parse."""
    return certificate_der.replace(b"\xa0\x03\x02\x01\x02", b"\xa0\x03\x02\x01\x01", 1)


@pytest.fixture
def unsupported_certificate_pem(unsupported_certificate_der: bytes) -> str:
    """Encode the unsupported certificate version as PEM."""
    return ssl.DER_cert_to_PEM_cert(unsupported_certificate_der)


@pytest.fixture
def ca_key() -> ec.EllipticCurvePrivateKey:
    """Generate a private certificate authority's key."""
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def ca_certificate(ca_key: ec.EllipticCurvePrivateKey) -> x509.Certificate:
    """Create a private root CA accepted by strict OpenSSL verification."""
    return _create_ca_certificate(ca_key)


@pytest.fixture
def unrelated_ca_certificate() -> x509.Certificate:
    """Create a different CA key to test replacing an entry's trusted issuer."""
    return _create_ca_certificate(ec.generate_private_key(ec.SECP256R1()))


def _create_ca_certificate(ca_key: ec.EllipticCurvePrivateKey) -> x509.Certificate:
    """Build a private root CA with the extensions needed for strict validation."""
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Private test CA")])
    return (
        _certificate_builder(
            (datetime(2020, 1, 1, tzinfo=UTC), datetime(2100, 1, 1, tzinfo=UTC))
        )
        .subject_name(name)
        .issuer_name(name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )


@pytest.fixture
def ca_signed_certificate(
    certificate_key: ec.EllipticCurvePrivateKey,
    ca_key: ec.EllipticCurvePrivateKey,
    ca_certificate: x509.Certificate,
    certificate_dates: tuple[datetime, datetime],
) -> x509.Certificate:
    """Create a server certificate issued by the private CA."""
    return (
        _certificate_builder(certificate_dates)
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(ca_certificate.subject)
        .public_key(certificate_key.public_key())
        .serial_number(x509.random_serial_number())
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
