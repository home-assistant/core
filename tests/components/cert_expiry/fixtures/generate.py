"""Generate cert_expiry's test certificate fixtures.

Output is checked in. Re-run manually when a scenario changes:

    python3 -m tests.components.cert_expiry.fixtures.generate
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, override

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric.types import (
    CertificateIssuerPrivateKeyTypes,
)
from pydantic import TypeAdapter

FIXTURES_DIR = Path(__file__).parent
SCENARIOS_DIR = FIXTURES_DIR / "scenarios"
HOSTNAME = "localhost"  # must resolve locally; see ../cert_helpers.py
PAST_DATE = datetime(2020, 1, 1, tzinfo=UTC)
FUTURE_DATE = datetime(2120, 1, 1, tzinfo=UTC)

type PrivateKey = CertificateIssuerPrivateKeyTypes


@dataclass(frozen=True)
class ScenarioMetadata:
    """The parameters a scenario's certificate was built with (metadata.json).

    Tests assert against these instead of re-parsing cert.pem.
    """

    key_type: str
    common_name: str
    serial_number: int
    not_valid_before: datetime
    not_valid_after: datetime

    @classmethod
    def from_json(cls, data: str) -> ScenarioMetadata:
        """Parse metadata.json's contents."""
        return _METADATA_ADAPTER.validate_json(data)

    def to_json(self) -> str:
        """Serialize to metadata.json's contents."""
        return _METADATA_ADAPTER.dump_json(self, indent=2).decode() + "\n"


_METADATA_ADAPTER = TypeAdapter(ScenarioMetadata)


class KeyFactory(Protocol):
    """Creates private keys of one type."""

    key_type: str

    def create_key(self) -> PrivateKey:
        """Return a private key."""


class RSAKeyFactory:
    """Creates RSA private keys."""

    key_type = "rsa"

    def create_key(self) -> rsa.RSAPrivateKey:
        """Return an RSA private key."""
        return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class ECKeyFactory:
    """Creates EC private keys."""

    key_type = "ec"

    def create_key(self) -> ec.EllipticCurvePrivateKey:
        """Return an EC private key."""
        return ec.generate_private_key(ec.SECP256R1())


@dataclass(frozen=True)
class Credential:
    """A certificate and the private key it was issued for."""

    cert: x509.Certificate
    key: PrivateKey
    key_type: str

    def write_files(
        self,
        output_dir: Path,
        intermediate: x509.Certificate | None = None,
        cert_file_name: str = "cert.pem",
        key_file_name: str = "key.pem",
    ) -> None:
        """Write the cert.pem and key.pem for this credential."""
        output_dir.mkdir(parents=True, exist_ok=True)

        _write_pem(
            output_dir / cert_file_name,
            self.cert.public_bytes(serialization.Encoding.PEM),
            intermediate.public_bytes(serialization.Encoding.PEM)
            if intermediate
            else b"",
        )

        _write_pem(
            output_dir / key_file_name,
            self.key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            ),
        )


def _write_pem(path: Path, *parts: bytes) -> None:
    """Write PEM data to disk, iterating through the provided byte parts."""
    with path.open("wb") as file:
        for part in parts:
            file.write(part)


_ca_key_usage = x509.KeyUsage(
    digital_signature=False,
    content_commitment=False,
    key_encipherment=False,
    data_encipherment=False,
    key_agreement=False,
    key_cert_sign=True,
    crl_sign=True,
    encipher_only=False,
    decipher_only=False,
)


class CredentialFactory:
    """Builds a signed certificate for a key."""

    def __init__(
        self,
        common_name: str,
        key: PrivateKey,
        key_type: str,
        signing_key: CertificateIssuerPrivateKeyTypes,
    ) -> None:
        """Initialize the factory."""
        self.key = key
        self.key_type = key_type
        self._signing_key = signing_key

        self.common_name = common_name
        self.subject = x509.Name(
            [x509.NameAttribute(x509.NameOID.COMMON_NAME, common_name)]
        )
        self.serial_number = x509.random_serial_number()
        self.not_valid_before = PAST_DATE
        self.not_valid_after = FUTURE_DATE

    def _create_builder(self) -> x509.CertificateBuilder:
        return (
            x509.CertificateBuilder()
            .subject_name(self.subject)
            .public_key(self.key.public_key())
            .serial_number(self.serial_number)
            .not_valid_before(self.not_valid_before)
            .not_valid_after(self.not_valid_after)
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(self.key.public_key()),
                critical=False,
            )
        )

    def create_credential(self) -> Credential:
        """Build and sign the certificate."""
        builder = self._create_builder()
        cert = builder.sign(self._signing_key, hashes.SHA256())

        return Credential(cert=cert, key=self.key, key_type=self.key_type)


class RootCredentialFactory(CredentialFactory):
    """Builds a self-signed root CA."""

    def __init__(self, common_name: str, key: PrivateKey, key_type: str) -> None:
        """Initialize the factory."""
        super().__init__(common_name, key, key_type, signing_key=key)

    @override
    def _create_builder(self) -> x509.CertificateBuilder:
        return (
            super()
            ._create_builder()
            .issuer_name(self.subject)
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None), critical=True
            )
            .add_extension(_ca_key_usage, critical=True)
        )


class ChildCredentialFactory(CredentialFactory):
    """Builds a certificate signed by an issuer."""

    def __init__(
        self, common_name: str, key: PrivateKey, key_type: str, issuer: Credential
    ) -> None:
        """Initialize the factory."""
        super().__init__(common_name, key, key_type, issuer.key)
        self._issuer = issuer

    @override
    def _create_builder(self) -> x509.CertificateBuilder:
        return (
            super()
            ._create_builder()
            .issuer_name(self._issuer.cert.subject)
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(
                    self._issuer.cert.extensions.get_extension_for_class(
                        x509.SubjectKeyIdentifier
                    ).value
                ),
                critical=False,
            )
        )


class IntermediateCredentialFactory(ChildCredentialFactory):
    """Builds an intermediate CA."""

    @override
    def _create_builder(self) -> x509.CertificateBuilder:
        return (
            super()
            ._create_builder()
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None), critical=True
            )
            .add_extension(_ca_key_usage, critical=True)
        )


class LeafCredentialFactory(ChildCredentialFactory):
    """Builds a leaf certificate."""

    @override
    def _create_builder(self) -> x509.CertificateBuilder:
        return (
            super()
            ._create_builder()
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName(self.common_name)]),
                critical=False,
            )
            # Static-RSA cipher suites need keyEncipherment.
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=True,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
        )


def _write_scenario(
    name: str,
    issuer: Credential,
    key_factory: KeyFactory,
    chain: x509.Certificate | None = None,
) -> None:
    credential_factory = LeafCredentialFactory(
        HOSTNAME, key_factory.create_key(), key_factory.key_type, issuer
    )

    credential = credential_factory.create_credential()

    credential.write_files(SCENARIOS_DIR / name, chain)
    metadata = ScenarioMetadata(
        key_type=credential_factory.key_type,
        common_name=credential_factory.common_name,
        serial_number=credential_factory.serial_number,
        not_valid_before=credential_factory.not_valid_before,
        not_valid_after=credential_factory.not_valid_after,
    )
    (SCENARIOS_DIR / name / "metadata.json").write_text(metadata.to_json())


def main() -> None:
    """Generate the root/intermediate CAs and all leaf certificate fixtures."""
    rsa_key_factory = RSAKeyFactory()
    ec_key_factory = ECKeyFactory()

    root = RootCredentialFactory(
        "cert_expiry Test Root CA",
        rsa_key_factory.create_key(),
        rsa_key_factory.key_type,
    ).create_credential()
    root.write_files(
        FIXTURES_DIR, cert_file_name="root_ca.pem", key_file_name="root_ca.key.pem"
    )

    intermediate = IntermediateCredentialFactory(
        "cert_expiry Test Intermediate CA",
        rsa_key_factory.create_key(),
        rsa_key_factory.key_type,
        root,
    ).create_credential()
    intermediate.write_files(
        FIXTURES_DIR,
        cert_file_name="intermediate_ca.pem",
        key_file_name="intermediate_ca.key.pem",
    )

    _write_scenario(
        "rsa_leaf_with_full_chain",
        intermediate,
        rsa_key_factory,
        chain=intermediate.cert,
    )

    _write_scenario(
        "ec_leaf_with_full_chain", intermediate, ec_key_factory, chain=intermediate.cert
    )

    _write_scenario("leaf_signed_directly_by_root", root, ec_key_factory)

    _write_scenario("leaf_missing_intermediate", intermediate, ec_key_factory)

    _write_scenario(
        "legacy_cipher_only_server",
        intermediate,
        rsa_key_factory,
        chain=intermediate.cert,
    )


if __name__ == "__main__":
    main()
