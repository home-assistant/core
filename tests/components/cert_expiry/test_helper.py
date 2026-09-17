"""Real end-to-end tests for cert_expiry.helper, driven by checked-in cert fixtures."""

from collections.abc import Generator

import pytest

from homeassistant.components.cert_expiry.helper import get_cert_expiry_timestamp
from homeassistant.core import HomeAssistant
from homeassistant.util import ssl as ssl_util

from .cert_helpers import FIXTURES_DIR, load_scenario, local_tls_server, server_context


@pytest.fixture(autouse=True)
def trust_test_ca(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    """Make the default SSL context trust the test root CA."""
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(FIXTURES_DIR / "root_ca.pem"))
    ssl_util._client_context.cache_clear()
    yield
    monkeypatch.undo()
    ssl_util._client_context.cache_clear()


@pytest.mark.parametrize(
    "server",
    [
        ("rsa_leaf_with_full_chain", None),
        ("ec_leaf_with_full_chain", None),
        ("leaf_signed_directly_by_root", None),
        ("leaf_missing_intermediate", None),
        ("legacy_cipher_only_server", "AES256-GCM-SHA384"),
        pytest.param(
            ("rsa_leaf_with_full_chain", "DHE-RSA-CHACHA20-POLY1305"),
            id="cipher_outside_intermediate_list",
        ),
    ],
    ids=lambda server: server[0],
)
@pytest.mark.usefixtures("socket_enabled")
async def test_get_cert_expiry_timestamp(
    hass: HomeAssistant, server: tuple[str, str | None]
) -> None:
    """The expiry is returned for each served certificate scenario."""
    scenario, ciphers = server
    cert = load_scenario(scenario)
    async with local_tls_server(server_context(cert, ciphers=ciphers)) as port:
        timestamp = await get_cert_expiry_timestamp(hass, "localhost", port)
    assert timestamp == cert.metadata.not_valid_after
