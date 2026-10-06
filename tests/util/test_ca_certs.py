"""Test the CA certificates helper."""

from pathlib import Path
import ssl

import certifi

from homeassistant.util.ca_certs import certifi_ca_data, load_ca_data


def _write_single_cert_bundle(path: Path) -> Path:
    """Write a CA bundle containing only the first certifi certificate."""
    certifi_bundle = Path(certifi.where()).read_text(encoding="utf-8")
    end_marker = "-----END CERTIFICATE-----"
    path.write_text(
        certifi_bundle[: certifi_bundle.index(end_marker)] + end_marker,
        encoding="utf-8",
    )
    return path


def test_load_ca_data(tmp_path: Path) -> None:
    """Test CA data is loaded from the bundle once and cached."""
    ca_bundle = str(_write_single_cert_bundle(tmp_path / "ca.pem"))

    ca_data = load_ca_data(ca_bundle)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cadata=ca_data)

    assert context.cert_store_stats()["x509_ca"] == 1
    assert load_ca_data(ca_bundle) is ca_data


def test_certifi_ca_data() -> None:
    """Test the certifi CA data matches the certifi bundle."""
    expected = ssl.create_default_context(cafile=certifi.where())
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cadata=certifi_ca_data())

    assert context.cert_store_stats() == expected.cert_store_stats()
    assert certifi_ca_data() is load_ca_data(certifi.where())
