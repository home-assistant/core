"""The tests for the Home Assistant HTTP component."""

import asyncio
from collections.abc import Callable, Generator
import errno
from http import HTTPStatus
import logging
import os
from pathlib import Path
import socket
import ssl
from typing import Any
from unittest.mock import ANY, AsyncMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.auth.providers.homeassistant import HassAuthProvider
from homeassistant.components import cloud, http
from homeassistant.components.cloud import CloudNotAvailable
from homeassistant.components.http import DOMAIN
from homeassistant.components.http.config import (
    _DEFAULT_CONFIG,
    AUTO_REVERT_DELAY,
    HTTP_STORAGE_SCHEMA,
    async_get_and_load_store,
    default_server_port,
)
from homeassistant.components.http.const import ENV_SETUP_PORT
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, HASSIO_USER_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.http import KEY_HASS
from homeassistant.helpers.network import NoURLAvailableError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.ssl import server_context_intermediate, server_context_modern

from tests.common import (
    async_call_logger_set_level,
    async_fire_time_changed,
    async_mock_service,
)
from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest.fixture(autouse=True)
def disable_http_server(socket_enabled: None) -> None:
    """Override the global disable_http_server fixture with an empty fixture.

    This allows the HTTP server to start in tests that need it.
    """
    return


# The unpatched original, for tests that exercise the real implementation.
_REAL_CREATE_SERVER = http.HomeAssistantHTTP._async_create_server


async def _ephemeral_server(hass: HomeAssistant) -> asyncio.Server:
    """Create a bound but not serving server on an ephemeral localhost port."""
    return await hass.loop.create_server(
        asyncio.Protocol, "127.0.0.1", 0, start_serving=False
    )


@pytest.fixture(autouse=True)
def mock_create_server() -> Generator[Mock]:
    """Bind an ephemeral localhost server instead of the configured address.

    Binding the configured address for real would make parallel tests collide
    on ports; an ephemeral localhost server keeps the serving path real.
    """
    servers: list[asyncio.Server] = []

    async def _bind_ephemeral(self: http.HomeAssistantHTTP) -> asyncio.Server:
        server = await self.hass.loop.create_server(
            self._make_protocol,
            "127.0.0.1",
            0,
            ssl=self.context,
            start_serving=False,
        )
        servers.append(server)
        return server

    with patch(
        "homeassistant.components.http.HomeAssistantHTTP._async_create_server",
        autospec=True,
        side_effect=_bind_ephemeral,
    ) as mock_create:
        yield mock_create

    # Close any server that is not already closed (closing twice is a no-op).
    for server in servers:
        server.close()


def _setup_broken_ssl_pem_files(tmp_path: Path) -> tuple[Path, Path]:
    test_dir = tmp_path / "test_broken_ssl"
    test_dir.mkdir()
    cert_path = test_dir / "cert.pem"
    cert_path.write_text("garbage")
    key_path = test_dir / "key.pem"
    key_path.write_text("garbage")
    return cert_path, key_path


def _setup_empty_ssl_pem_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    test_dir = tmp_path / "test_empty_ssl"
    test_dir.mkdir()
    cert_path = test_dir / "cert.pem"
    cert_path.write_text("-")
    peer_cert_path = test_dir / "peer_cert.pem"
    peer_cert_path.write_text("-")
    key_path = test_dir / "key.pem"
    key_path.write_text("-")
    return cert_path, key_path, peer_cert_path


@pytest.fixture
def mock_stack():
    """Mock extract stack."""
    with patch(
        "homeassistant.components.http.extract_stack",
        return_value=[
            Mock(
                filename="/home/paulus/core/homeassistant/core.py",
                lineno="23",
                line="do_something()",
            ),
            Mock(
                filename="/home/paulus/core/homeassistant/components/hue/light.py",
                lineno="23",
                line="self.light.is_on",
            ),
            Mock(
                filename="/home/paulus/core/homeassistant/components/http/__init__.py",
                lineno="157",
                line="base_url",
            ),
        ],
    ):
        yield


class TestView(http.HomeAssistantView):
    """Test the HTTP views."""

    name = "test"
    url = "/hello"

    async def get(self, request):
        """Return a get request."""
        return "hello"


async def test_registering_view_while_running(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    unused_tcp_port_factory: Callable[[], int],
) -> None:
    """Test that we can register a view while the server is running."""
    await async_setup_component(
        hass,
        http.DOMAIN,
        {http.DOMAIN: {http.CONF_SERVER_PORT: unused_tcp_port_factory()}},
    )

    await hass.async_start()
    # This raises a RuntimeError if app is frozen
    hass.http.register_view(TestView)


async def test_homeassistant_assigned_to_app(hass: HomeAssistant) -> None:
    """Test HomeAssistant instance is assigned to HomeAssistantApp."""
    assert await async_setup_component(hass, "api", {"http": {}})
    await hass.async_start()
    assert hass.http.app[KEY_HASS] == hass
    assert hass.http.app["hass"] == hass  # For backwards compatibility
    await hass.async_stop()


async def test_not_log_password(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
    local_auth: HassAuthProvider,
) -> None:
    """Test access with password doesn't get logged."""
    assert await async_setup_component(hass, "api", {"http": {}})
    client = await hass_client_no_auth()
    logging.getLogger("aiohttp.access").setLevel(logging.INFO)

    resp = await client.get("/api/", params={"api_password": "test-password"})

    assert resp.status == HTTPStatus.UNAUTHORIZED
    logs = caplog.text

    # Ensure we don't log API passwords
    assert "/api/" in logs
    assert "some-pass" not in logs


async def test_proxy_config(hass: HomeAssistant) -> None:
    """Test use_x_forwarded_for must config together with trusted_proxies."""
    assert (
        await async_setup_component(
            hass,
            DOMAIN,
            {
                "http": {
                    http.CONF_USE_X_FORWARDED_FOR: True,
                    http.CONF_TRUSTED_PROXIES: ["127.0.0.1"],
                }
            },
        )
        is True
    )


async def test_proxy_config_forwarded_request(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test a request with X-Forwarded-For from a trusted proxy is accepted.

    The config store persists trusted proxies as strings; this exercises the
    forwarded middleware with a config loaded from the store to guard against
    passing the strings through instead of IP network objects.
    """
    hass_storage[DOMAIN] = _stable_http_storage(
        {
            "use_x_forwarded_for": True,
            "trusted_proxies": ["127.0.0.0/8"],
        }
    )
    assert await async_setup_component(hass, "api", {})
    client = await hass_client()

    resp = await client.get("/api/", headers={"X-Forwarded-For": "203.0.113.5"})

    assert resp.status == HTTPStatus.OK


async def test_proxy_config_only_use_xff(hass: HomeAssistant) -> None:
    """Test use_x_forwarded_for must config together with trusted_proxies."""
    assert (
        await async_setup_component(
            hass, DOMAIN, {"http": {http.CONF_USE_X_FORWARDED_FOR: True}}
        )
        is not True
    )


async def test_proxy_config_only_trust_proxies(hass: HomeAssistant) -> None:
    """Test use_x_forwarded_for must config together with trusted_proxies."""
    assert (
        await async_setup_component(
            hass, DOMAIN, {"http": {http.CONF_TRUSTED_PROXIES: ["127.0.0.1"]}}
        )
        is not True
    )


async def test_ssl_profile_defaults_modern(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test default ssl profile."""

    cert_path, key_path, _ = await hass.async_add_executor_job(
        _setup_empty_ssl_pem_files, tmp_path
    )

    with (
        patch("ssl.SSLContext.load_cert_chain"),
        patch(
            "homeassistant.util.ssl.server_context_modern",
            side_effect=server_context_modern,
        ) as mock_context,
    ):
        assert (
            await async_setup_component(
                hass,
                DOMAIN,
                {"http": {"ssl_certificate": cert_path, "ssl_key": key_path}},
            )
            is True
        )
        await hass.async_start()
        await hass.async_block_till_done()

    assert len(mock_context.mock_calls) == 1


async def test_ssl_profile_change_intermediate(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test setting ssl profile to intermediate."""

    cert_path, key_path, _ = await hass.async_add_executor_job(
        _setup_empty_ssl_pem_files, tmp_path
    )

    with (
        patch("ssl.SSLContext.load_cert_chain"),
        patch(
            "homeassistant.util.ssl.server_context_intermediate",
            side_effect=server_context_intermediate,
        ) as mock_context,
    ):
        assert (
            await async_setup_component(
                hass,
                DOMAIN,
                {
                    "http": {
                        "ssl_profile": "intermediate",
                        "ssl_certificate": cert_path,
                        "ssl_key": key_path,
                    }
                },
            )
            is True
        )
        await hass.async_start()
        await hass.async_block_till_done()

    assert len(mock_context.mock_calls) == 1


async def test_ssl_profile_change_modern(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test setting ssl profile to modern."""

    cert_path, key_path, _ = await hass.async_add_executor_job(
        _setup_empty_ssl_pem_files, tmp_path
    )

    with (
        patch("ssl.SSLContext.load_cert_chain"),
        patch(
            "homeassistant.util.ssl.server_context_modern",
            side_effect=server_context_modern,
        ) as mock_context,
    ):
        assert (
            await async_setup_component(
                hass,
                DOMAIN,
                {
                    "http": {
                        "ssl_profile": "modern",
                        "ssl_certificate": cert_path,
                        "ssl_key": key_path,
                    }
                },
            )
            is True
        )
        await hass.async_start()
        await hass.async_block_till_done()

    assert len(mock_context.mock_calls) == 1


async def test_peer_cert(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test required peer cert."""
    cert_path, key_path, peer_cert_path = await hass.async_add_executor_job(
        _setup_empty_ssl_pem_files, tmp_path
    )

    with (
        patch("ssl.SSLContext.load_cert_chain"),
        patch("ssl.SSLContext.load_verify_locations") as mock_load_verify_locations,
        patch(
            "homeassistant.util.ssl.server_context_modern",
            side_effect=server_context_modern,
        ) as mock_context,
    ):
        assert (
            await async_setup_component(
                hass,
                DOMAIN,
                {
                    "http": {
                        "ssl_peer_certificate": peer_cert_path,
                        "ssl_profile": "modern",
                        "ssl_certificate": cert_path,
                        "ssl_key": key_path,
                    }
                },
            )
            is True
        )
        await hass.async_start()
        await hass.async_block_till_done()

    assert len(mock_context.mock_calls) == 1
    assert len(mock_load_verify_locations.mock_calls) == 1


def _stable_http_storage(
    stable: dict, *, pending: dict | None = None, yaml_migration_done: bool = True
) -> dict:
    """Build a hass_storage entry seeded with a confirmed-working stable config.

    ``stable`` (and ``pending`` if given) are normalised through the storage
    schema, matching what real users have on disk after migration / writes —
    the load path does direct key access and assumes the payload is complete.
    """
    normalised_stable = dict(HTTP_STORAGE_SCHEMA(stable))
    normalised_pending = dict(HTTP_STORAGE_SCHEMA(pending)) if pending else None
    return {
        "version": 2,
        "key": DOMAIN,
        "data": {
            "stable": normalised_stable,
            "pending": normalised_pending,
            "yaml_migration_done": yaml_migration_done,
        },
    }


async def test_emergency_ssl_certificate_when_invalid(
    hass: HomeAssistant,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    hass_storage: dict[str, Any],
) -> None:
    """Test http starts with emergency self-signed cert on invalid cert."""

    cert_path, key_path = await hass.async_add_executor_job(
        _setup_broken_ssl_pem_files, tmp_path
    )
    # In recovery mode YAML is ignored, so seed the broken SSL paths into the
    # store's stable slot — that's the only config recovery mode will look at.
    hass_storage[DOMAIN] = _stable_http_storage(
        {"ssl_certificate": str(cert_path), "ssl_key": str(key_path)}
    )
    hass.config.recovery_mode = True
    assert await async_setup_component(hass, DOMAIN, {}) is True

    await hass.async_start()
    await hass.async_block_till_done()
    assert (
        "Home Assistant is running in recovery mode with an emergency"
        " self signed ssl certificate because the configured SSL"
        " certificate was not usable" in caplog.text
    )

    assert hass.http._server is not None


async def test_emergency_ssl_certificate_not_used_when_not_recovery_mode(
    hass: HomeAssistant,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    hass_storage: dict[str, Any],
) -> None:
    """Test an emergency cert is only used in recovery mode.

    A broken SSL config in the stable slot fails setup (activating recovery
    mode on a real boot); only recovery mode uses the emergency certificate.
    """

    cert_path, key_path = await hass.async_add_executor_job(
        _setup_broken_ssl_pem_files, tmp_path
    )
    hass_storage[DOMAIN] = _stable_http_storage(
        {"ssl_certificate": str(cert_path), "ssl_key": str(key_path)}
    )

    assert await async_setup_component(hass, DOMAIN, {}) is False


async def test_emergency_ssl_certificate_when_invalid_get_url_fails(
    hass: HomeAssistant,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    hass_storage: dict[str, Any],
) -> None:
    """Test http falls back to no ssl when emergency cert creation fails.

    Ensure we can still start of we cannot determine the external url as well.
    """
    cert_path, key_path = await hass.async_add_executor_job(
        _setup_broken_ssl_pem_files, tmp_path
    )
    hass_storage[DOMAIN] = _stable_http_storage(
        {"ssl_certificate": str(cert_path), "ssl_key": str(key_path)}
    )
    hass.config.recovery_mode = True

    with patch(
        "homeassistant.components.http.get_url", side_effect=NoURLAvailableError
    ) as mock_get_url:
        assert await async_setup_component(hass, DOMAIN, {}) is True
        await hass.async_start()
        await hass.async_block_till_done()

    assert len(mock_get_url.mock_calls) == 1
    assert (
        "Home Assistant is running in recovery mode with an emergency"
        " self signed ssl certificate because the configured SSL"
        " certificate was not usable" in caplog.text
    )

    assert hass.http._server is not None


async def test_invalid_ssl_and_cannot_create_emergency_cert(
    hass: HomeAssistant,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    hass_storage: dict[str, Any],
) -> None:
    """Test http falls back to no ssl on emergency cert creation failure."""

    cert_path, key_path = await hass.async_add_executor_job(
        _setup_broken_ssl_pem_files, tmp_path
    )
    hass_storage[DOMAIN] = _stable_http_storage(
        {"ssl_certificate": str(cert_path), "ssl_key": str(key_path)}
    )
    hass.config.recovery_mode = True

    with patch(
        "homeassistant.components.http.x509.CertificateBuilder", side_effect=OSError
    ) as mock_builder:
        assert await async_setup_component(hass, DOMAIN, {}) is True
        await hass.async_start()
        await hass.async_block_till_done()
    assert "Could not create an emergency self signed ssl certificate" in caplog.text
    assert len(mock_builder.mock_calls) == 1

    assert hass.http._server is not None


async def test_invalid_ssl_and_cannot_create_emergency_cert_with_ssl_peer_cert(
    hass: HomeAssistant,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    hass_storage: dict[str, Any],
) -> None:
    """Test no-ssl fallback with peer cert when emergency cert fails.

    When there is a peer cert verification and we cannot create
    an emergency cert (probably will never happen since this means
    the system is very broken), we do not want to startup http
    as it would allow connections that are not verified by the cert.
    This intentionally overrides the recovery-mode fallback to the default
    config: connections must never be accepted without client certificate
    verification once it is configured.
    """

    cert_path, key_path = await hass.async_add_executor_job(
        _setup_broken_ssl_pem_files, tmp_path
    )
    hass_storage[DOMAIN] = _stable_http_storage(
        {
            "ssl_certificate": str(cert_path),
            "ssl_key": str(key_path),
            "ssl_peer_certificate": str(cert_path),
        }
    )
    hass.config.recovery_mode = True

    with patch(
        "homeassistant.components.http.x509.CertificateBuilder", side_effect=OSError
    ) as mock_builder:
        assert await async_setup_component(hass, DOMAIN, {}) is False
        await hass.async_start()
        await hass.async_block_till_done()
    assert "Could not create an emergency self signed ssl certificate" in caplog.text
    assert len(mock_builder.mock_calls) == 1


async def test_emergency_ssl_certificate_enforces_peer_certificate(
    hass: HomeAssistant,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    hass_storage: dict[str, Any],
) -> None:
    """Test the emergency cert still enforces client certificate verification.

    When the configured SSL certificate is broken and recovery mode falls
    back to the emergency self-signed certificate, a configured peer
    certificate must still be applied - connections must never be accepted
    without client certificate verification once it is configured.
    """
    cert_path, key_path = await hass.async_add_executor_job(
        _setup_broken_ssl_pem_files, tmp_path
    )
    hass_storage[DOMAIN] = _stable_http_storage(
        {
            "ssl_certificate": str(cert_path),
            "ssl_key": str(key_path),
            "ssl_peer_certificate": str(cert_path),
        }
    )
    hass.config.recovery_mode = True

    with patch("ssl.SSLContext.load_verify_locations") as mock_load_verify:
        assert await async_setup_component(hass, DOMAIN, {}) is True

    assert "emergency self signed ssl certificate" in caplog.text
    mock_load_verify.assert_called_once_with(str(cert_path))
    assert hass.http.context is not None
    assert hass.http.context.verify_mode is ssl.CERT_REQUIRED


async def test_create_server_passes_configuration(hass: HomeAssistant) -> None:
    """The real server factory passes the configured values to asyncio."""
    server = http.HomeAssistantHTTP(
        hass,
        server_host=["127.0.0.1", "::1"],
        server_port=1234,
        ssl_certificate=None,
        ssl_peer_certificate=None,
        ssl_key=None,
        trusted_proxies=[],
        ssl_profile=http.SSL_MODERN,
    )

    with patch.object(
        hass.loop, "create_server", new=AsyncMock(return_value=Mock())
    ) as mock_create:
        await _REAL_CREATE_SERVER(server)

    mock_create.assert_called_once_with(
        server._make_protocol,
        ["127.0.0.1", "::1"],
        1234,
        ssl=None,
        backlog=128,
        start_serving=False,
    )


async def test_cors_defaults(hass: HomeAssistant) -> None:
    """Test the CORS default settings."""
    with patch("homeassistant.components.http.setup_cors") as mock_setup:
        assert await async_setup_component(hass, DOMAIN, {})

    assert len(mock_setup.mock_calls) == 1
    assert mock_setup.mock_calls[0][1][1] == ["https://cast.home-assistant.io"]


async def test_logging(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Testing the access log works."""
    await asyncio.gather(
        *(
            async_setup_component(hass, domain, {})
            for domain in ("http", "logger", "api")
        )
    )
    hass.states.async_set("logging.entity", "hello")
    async with async_call_logger_set_level(
        "aiohttp.access", "INFO", hass=hass, caplog=caplog
    ):
        client = await hass_client()
        response = await client.get("/api/states/logging.entity")
        assert response.status == HTTPStatus.OK

        assert "GET /api/states/logging.entity" in caplog.text
        caplog.clear()
    async with async_call_logger_set_level(
        "aiohttp.access", "WARNING", hass=hass, caplog=caplog
    ):
        response = await client.get("/api/states/logging.entity")
        assert response.status == HTTPStatus.OK
        assert "GET /api/states/logging.entity" not in caplog.text


async def test_ssl_issue_if_no_urls_configured(
    hass: HomeAssistant,
    tmp_path: Path,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test raising SSL issue if no external or internal URL is configured."""

    assert hass.config.external_url is None
    assert hass.config.internal_url is None

    cert_path, key_path, _ = await hass.async_add_executor_job(
        _setup_empty_ssl_pem_files, tmp_path
    )

    with (
        patch("ssl.SSLContext.load_cert_chain"),
        patch(
            "homeassistant.util.ssl.server_context_modern",
            side_effect=server_context_modern,
        ),
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {"http": {"ssl_certificate": cert_path, "ssl_key": key_path}},
        )
        await hass.async_start()
        await hass.async_block_till_done()

    assert ("http", "ssl_configured_without_configured_urls") in issue_registry.issues


async def test_ssl_issue_if_using_cloud(
    hass: HomeAssistant,
    tmp_path: Path,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test raising no SSL issue if not right configured but using cloud."""
    assert hass.config.external_url is None
    assert hass.config.internal_url is None

    cert_path, key_path, _ = await hass.async_add_executor_job(
        _setup_empty_ssl_pem_files, tmp_path
    )

    with (
        patch("ssl.SSLContext.load_cert_chain"),
        patch.object(cloud, "async_remote_ui_url", return_value="https://example.com"),
        patch(
            "homeassistant.util.ssl.server_context_modern",
            side_effect=server_context_modern,
        ),
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {"http": {"ssl_certificate": cert_path, "ssl_key": key_path}},
        )
        await hass.async_start()
        await hass.async_block_till_done()

    assert (
        "http",
        "ssl_configured_without_configured_urls",
    ) not in issue_registry.issues


async def test_ssl_issue_if_not_connected_to_cloud(
    hass: HomeAssistant,
    tmp_path: Path,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test raising no SSL issue if not right configured and not connected to cloud."""
    assert hass.config.external_url is None
    assert hass.config.internal_url is None

    cert_path, key_path, _ = await hass.async_add_executor_job(
        _setup_empty_ssl_pem_files, tmp_path
    )

    with (
        patch("ssl.SSLContext.load_cert_chain"),
        patch(
            "homeassistant.util.ssl.server_context_modern",
            side_effect=server_context_modern,
        ),
        patch(
            "homeassistant.components.cloud.async_remote_ui_url",
            side_effect=CloudNotAvailable,
        ),
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {"http": {"ssl_certificate": cert_path, "ssl_key": key_path}},
        )
        await hass.async_start()
        await hass.async_block_till_done()

    assert ("http", "ssl_configured_without_configured_urls") in issue_registry.issues


@pytest.mark.parametrize(
    ("external_url", "internal_url"),
    [
        ("https://example.com", "https://example.local"),
        (None, "http://example.local"),
        ("https://example.com", None),
    ],
)
async def test_ssl_issue_urls_configured(
    hass: HomeAssistant,
    tmp_path: Path,
    issue_registry: ir.IssueRegistry,
    external_url: str | None,
    internal_url: str | None,
) -> None:
    """Test raising SSL issue if no external or internal URL is configured."""

    cert_path, key_path, _ = await hass.async_add_executor_job(
        _setup_empty_ssl_pem_files, tmp_path
    )

    hass.config.external_url = external_url
    hass.config.internal_url = internal_url

    with (
        patch("ssl.SSLContext.load_cert_chain"),
        patch(
            "homeassistant.util.ssl.server_context_modern",
            side_effect=server_context_modern,
        ),
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {"http": {"ssl_certificate": cert_path, "ssl_key": key_path}},
        )
        await hass.async_start()
        await hass.async_block_till_done()

    assert (
        "http",
        "ssl_configured_without_configured_urls",
    ) not in issue_registry.issues


@pytest.mark.parametrize(
    (
        "hassio",
        "http_config",
        "expected_serverhost",
        "expected_issues",
    ),
    [
        (False, {}, ["0.0.0.0", "::"], {("http", "deprecated_yaml")}),
        (
            False,
            {"server_host": "0.0.0.0"},
            ["0.0.0.0"],
            {("http", "deprecated_yaml")},
        ),
        (True, {}, ["0.0.0.0", "::"], {("http", "deprecated_yaml")}),
        (
            True,
            {"server_host": "0.0.0.0"},
            [
                "0.0.0.0",
            ],
            {
                ("http", "server_host_deprecated_hassio"),
                ("http", "deprecated_yaml"),
            },
        ),
    ],
)
async def test_server_host(
    hass: HomeAssistant,
    hassio: bool,
    issue_registry: ir.IssueRegistry,
    http_config: dict,
    expected_serverhost: list,
    expected_issues: set[tuple[str, str]],
    caplog: pytest.LogCaptureFixture,
    mock_create_server: Mock,
) -> None:
    """Test server_host behavior."""
    with patch("homeassistant.components.http.is_hassio", return_value=hassio):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {"http": http_config},
        )
        await hass.async_start()
        await hass.async_block_till_done()

    mock_create_server.assert_called_once()
    assert hass.http.server_host == expected_serverhost
    assert hass.http.server_port == 8123

    assert set(issue_registry.issues) == expected_issues


async def test_unix_socket_started_with_supervisor(
    hass: HomeAssistant,
    tmp_path: Path,
) -> None:
    """Test unix socket is started when running under Supervisor."""
    await hass.auth.async_create_system_user(
        HASSIO_USER_NAME, group_ids=["system-admin"]
    )
    socket_path = tmp_path / "core.sock"
    loop = asyncio.get_running_loop()
    mock_sock = Mock()
    with (
        patch.dict(
            os.environ, {"SUPERVISOR_CORE_API_SOCKET": str(socket_path)}, clear=False
        ),
        patch(
            "homeassistant.components.http.web_runner.HomeAssistantUnixSite"
            "._create_unix_socket",
            return_value=mock_sock,
        ) as mock_create_sock,
        patch.object(
            loop, "create_unix_server", return_value=Mock()
        ) as mock_create_unix,
    ):
        assert await async_setup_component(hass, DOMAIN, {"http": {}})
        await hass.async_start()
        await hass.async_block_till_done()

    mock_create_sock.assert_called_once()
    mock_create_unix.assert_called_once_with(ANY, sock=mock_sock, backlog=128)
    assert hass.http.supervisor_site is not None


async def test_unix_socket_not_started_without_supervisor(
    hass: HomeAssistant,
) -> None:
    """Test unix socket is not started when not running under Supervisor."""
    with (
        patch.dict(os.environ, {}, clear=False),
    ):
        os.environ.pop("SUPERVISOR_CORE_API_SOCKET", None)
        assert await async_setup_component(hass, DOMAIN, {"http": {}})
        await hass.async_start()
        await hass.async_block_till_done()

    assert hass.http.supervisor_site is None


async def test_unix_socket_rejected_relative_path(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unix socket is rejected when path is relative."""
    with (
        patch.dict(
            os.environ,
            {"SUPERVISOR_CORE_API_SOCKET": "relative/path.sock"},
            clear=False,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {"http": {}})
        await hass.async_start()
        await hass.async_block_till_done()

    assert hass.http.supervisor_site is None
    assert "path must be absolute" in caplog.text


async def test_yaml_migration_to_storage(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test YAML config is migrated to the HTTP config store with a deprecation issue.

    With no prior store, the migration stages YAML in ``pending`` (stable stays
    on the schema defaults). The pending slot is what HA boots from until the
    user confirms / promotes it via the UI.
    """
    yaml_conf = {
        "server_port": 9123,
        "cors_allowed_origins": ["https://example.com"],
        "use_x_forwarded_for": True,
        "trusted_proxies": ["127.0.0.0/8"],
        "ip_ban_enabled": False,
    }
    assert await async_setup_component(hass, DOMAIN, {"http": yaml_conf})
    await hass.async_start()
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING

    assert (
        issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_import_error") is None
    )

    stored = hass_storage[DOMAIN]["data"]
    assert stored["yaml_migration_done"] is True
    assert stored["stable"]["server_port"] == 8123  # untouched defaults
    pending = stored["pending"]
    assert pending is not None
    assert pending["server_port"] == 9123
    assert pending["cors_allowed_origins"] == ["https://example.com"]
    assert pending["trusted_proxies"] == ["127.0.0.0/8"]
    assert pending["ip_ban_enabled"] is False


async def test_yaml_migration_matches_stable_no_pending(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """If the YAML matches the existing stable config, no pending should be created."""
    existing_stable = {
        "server_port": 9123,
        "cors_allowed_origins": ["https://example.com"],
        "use_x_forwarded_for": True,
        "trusted_proxies": ["127.0.0.0/8"],
        "ip_ban_enabled": False,
        "login_attempts_threshold": -1,
        "ssl_profile": "modern",
        "use_x_frame_options": True,
    }
    hass_storage[DOMAIN] = {
        "version": 2,
        "key": DOMAIN,
        "data": {
            "stable": existing_stable,
            "pending": None,
            "yaml_migration_done": False,
        },
    }

    yaml_conf = {
        "server_port": 9123,
        "cors_allowed_origins": ["https://example.com"],
        "use_x_forwarded_for": True,
        "trusted_proxies": ["127.0.0.0/8"],
        "ip_ban_enabled": False,
    }
    assert await async_setup_component(hass, DOMAIN, {"http": yaml_conf})
    await hass.async_start()
    await hass.async_block_till_done()

    stored = hass_storage[DOMAIN]["data"]
    assert stored["pending"] is None
    assert stored["stable"] == existing_stable

    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")
    assert issue is not None


async def test_yaml_migration_differs_from_stable_creates_pending(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """If the YAML differs from the existing stable config, it must be stored as pending."""
    existing_stable = {
        "server_port": 9123,
        "cors_allowed_origins": ["https://example.com"],
        "login_attempts_threshold": -1,
        "ip_ban_enabled": True,
        "ssl_profile": "modern",
        "use_x_frame_options": True,
    }
    hass_storage[DOMAIN] = {
        "version": 2,
        "key": DOMAIN,
        "data": {
            "stable": existing_stable,
            "pending": None,
            "yaml_migration_done": False,
        },
    }

    yaml_conf = {"server_port": 8765, "ip_ban_enabled": False}
    assert await async_setup_component(hass, DOMAIN, {"http": yaml_conf})
    await hass.async_start()
    await hass.async_block_till_done()

    stored = hass_storage[DOMAIN]["data"]
    assert stored["stable"] == existing_stable
    assert stored["pending"] == {
        "server_port": 8765,
        "cors_allowed_origins": ["https://cast.home-assistant.io"],
        "login_attempts_threshold": -1,
        "ip_ban_enabled": False,
        "ssl_profile": "modern",
        "use_x_frame_options": True,
    }

    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")
    assert issue is not None


async def test_yaml_migration_failure_creates_error_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that an error during YAML migration creates an error issue."""
    yaml_conf = {"server_port": 9123}

    with (
        patch(
            "homeassistant.components.http.config.HTTPConfigStore.async_migrate_yaml",
            side_effect=RuntimeError("boom"),
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {"http": yaml_conf})
        await hass.async_start()
        await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_import_error")
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR

    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml") is None


async def test_yaml_still_present_after_migration_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """When YAML lingers after migration, a repair issue is surfaced and YAML is ignored."""
    hass_storage[DOMAIN] = _stable_http_storage(
        {"server_port": 9876}, yaml_migration_done=True
    )

    yaml_conf = {"server_port": 1234}
    assert await async_setup_component(hass, DOMAIN, {"http": yaml_conf})
    await hass.async_start()
    await hass.async_block_till_done()

    # YAML must be ignored once migration is done; stable wins.
    assert hass.config.api.port == 9876

    issue = issue_registry.async_get_issue(DOMAIN, "yaml_still_present_after_migration")
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING


async def test_yaml_still_present_issue_cleared_when_yaml_removed(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """A previously created leftover-YAML issue is cleared once YAML is removed."""
    hass_storage[DOMAIN] = _stable_http_storage(
        {"server_port": 9876}, yaml_migration_done=True
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        "yaml_still_present_after_migration",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="yaml_still_present_after_migration",
    )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_start()
    await hass.async_block_till_done()

    assert (
        issue_registry.async_get_issue(DOMAIN, "yaml_still_present_after_migration")
        is None
    )


async def test_setup_uses_stable_config_when_no_yaml(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test HTTP config is loaded from the stable slot when no YAML or pending is set."""
    hass_storage[DOMAIN] = _stable_http_storage(
        {
            "server_port": 9876,
            "cors_allowed_origins": ["https://stored.example.com"],
        }
    )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.config.api.port == 9876

    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml") is None
    assert (
        issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_import_error") is None
    )


async def test_setup_prefers_pending_over_stable_in_normal_mode(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Pending overrides stable on a normal boot so the new config gets tested."""
    hass_storage[DOMAIN] = _stable_http_storage(
        {"server_port": 9876}, pending={"server_port": 9999}
    )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.config.api.port == 9999


async def test_recovery_mode_falls_back_to_stable(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """In recovery mode the pending config is ignored to keep HA reachable."""
    hass_storage[DOMAIN] = _stable_http_storage(
        {"server_port": 9876}, pending={"server_port": 9999}
    )
    hass.config.recovery_mode = True

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.config.api.port == 9876


async def test_recovery_mode_with_no_storage(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Recovery mode with no prior storage starts HTTP on the schema defaults.

    This covers the first-ever-boot-into-recovery-mode case: bootstrap fell
    through to recovery before HTTP ever had a chance to migrate YAML, so the
    store is empty and we must come up cleanly on defaults.
    """
    assert "http" not in hass_storage
    hass.config.recovery_mode = True

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.config.api.port == 8123
    # Recovery mode must not trigger YAML migration side effects.
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml") is None


async def test_recovery_mode_ignores_yaml(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """YAML config must not be applied or migrated while in recovery mode.

    The whole point of recovery mode is to ignore the user's (possibly bad)
    config and fall back to the last known good ``stable`` slot. Migrating
    YAML here would defeat that and could re-introduce the broken config.
    """
    hass_storage[DOMAIN] = _stable_http_storage(
        {"server_port": 5555}, yaml_migration_done=False
    )
    hass.config.recovery_mode = True

    assert await async_setup_component(hass, DOMAIN, {"http": {"server_port": 1234}})
    await hass.async_start()
    await hass.async_block_till_done()

    # YAML's port must NOT win: stable is the only source of truth in recovery.
    assert hass.config.api.port == 5555
    # The migration must not run in recovery mode, so its flag stays untouched
    # and no deprecation issue is created on this boot.
    assert hass_storage[DOMAIN]["data"]["yaml_migration_done"] is False
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml") is None


async def test_setup_migrates_v1_storage_to_v2(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """An existing v1 store is migrated into the stable slot."""
    hass_storage[DOMAIN] = {
        "version": 1,
        "key": "http",
        "data": {"server_port": 9876},
    }

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_start()
    await hass.async_block_till_done()

    # The migrated v1 store config is only used in recovery mode. Since this
    # test isn't running in recovery mode, the YAML migration runs on first
    # boot after store migration. With no YAML http config, the default config is migrated to the pending slot and used. Therefore we assert below the default port (8123)
    assert hass.config.api.port == 8123
    assert hass_storage[DOMAIN]["version"] == 2
    data = hass_storage[DOMAIN]["data"]
    # The v1→v2 migration normalises the payload through the storage schema,
    # so the v2 stable slot is well-formed (all keys present) on disk.
    assert data["stable"]["server_port"] == 9876
    assert data["stable"]["ip_ban_enabled"] is True
    assert data["pending"] == _DEFAULT_CONFIG
    assert data["yaml_migration_done"] is True


@pytest.mark.parametrize(
    ("env", "expected_port"),
    [
        pytest.param({}, 8123, id="unset"),
        pytest.param({ENV_SETUP_PORT: "80"}, 80, id="valid"),
        pytest.param({ENV_SETUP_PORT: "0"}, 8123, id="out-of-range"),
        pytest.param({ENV_SETUP_PORT: "notaport"}, 8123, id="not-a-number"),
        pytest.param({ENV_SETUP_PORT: ""}, 8123, id="empty"),
    ],
)
def test_default_server_port(
    env: dict[str, str],
    expected_port: int,
) -> None:
    """Test SETUP_PORT overrides the default port and invalid values fall back."""
    with patch.dict(os.environ, env, clear=True):
        assert default_server_port() == expected_port


async def test_setup_port_env_var_used_as_default(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test SETUP_PORT is used as the default server port without YAML config."""
    with (
        patch.dict(os.environ, {ENV_SETUP_PORT: "80"}),
    ):
        assert await async_setup_component(hass, "http", {})
        await hass.async_start()
        await hass.async_block_till_done()

    assert hass.config.api.port == 80
    assert hass_storage["http"]["data"]["pending"]["server_port"] == 80


async def test_websocket_http_config(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test the http/config, configure and promote websocket commands."""
    assert await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "websocket_api", {})
    await hass.async_start()
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)

    # Staging a new config triggers a restart so the pending config is applied.
    restart_calls = async_mock_service(hass, "homeassistant", "restart")

    # On a fresh setup the stable slot is seeded with the schema defaults and
    # there is no pending config.
    await ws_client.send_json_auto_id({"type": "http/config"})
    response = await ws_client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "stable": _DEFAULT_CONFIG,
        "pending": None,
        "revert_at": None,
    }

    new_config = {
        "server_port": 9123,
        "cors_allowed_origins": ["https://example.com"],
        "use_x_forwarded_for": True,
        "trusted_proxies": ["127.0.0.0/8"],
        "ip_ban_enabled": False,
        "login_attempts_threshold": 5,
        "ssl_profile": "modern",
        "use_x_frame_options": True,
    }
    await ws_client.send_json_auto_id(
        {"type": "http/config/configure", "config": new_config}
    )
    response = await ws_client.receive_json()
    assert response["success"]
    assert response["result"] == {"restart": True}
    pending = hass_storage["http"]["data"]["pending"]
    assert pending["server_port"] == 9123
    assert pending["trusted_proxies"] == ["127.0.0.0/8"]
    await hass.async_block_till_done()
    assert len(restart_calls) == 1

    # Stable is unchanged until the user promotes, but the pending config is
    # now returned alongside it.
    await ws_client.send_json_auto_id({"type": "http/config"})
    response = await ws_client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "stable": _DEFAULT_CONFIG,
        "pending": new_config,
        "revert_at": None,
    }

    # Promote: pending becomes stable, pending is cleared.
    await ws_client.send_json_auto_id({"type": "http/config/promote"})
    response = await ws_client.receive_json()
    assert response["success"]
    assert hass_storage["http"]["data"]["pending"] is None
    assert hass_storage["http"]["data"]["stable"]["server_port"] == 9123

    await ws_client.send_json_auto_id({"type": "http/config"})
    response = await ws_client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "stable": new_config,
        "pending": None,
        "revert_at": None,
    }

    # Promoting again with no pending is rejected.
    await ws_client.send_json_auto_id({"type": "http/config/promote"})
    response = await ws_client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "not_allowed"

    # Staging a different config again changes the pending slot -> restart.
    await ws_client.send_json_auto_id(
        {"type": "http/config/configure", "config": {"server_port": 7000}}
    )
    response = await ws_client.receive_json()
    assert response["success"]
    assert response["result"] == {"restart": True}
    assert hass_storage["http"]["data"]["pending"]["server_port"] == 7000
    await hass.async_block_till_done()
    assert len(restart_calls) == 2

    # Clearing a previously staged config also changes the active config back
    # to stable, so it must trigger a restart too.
    await ws_client.send_json_auto_id({"type": "http/config/configure", "config": None})
    response = await ws_client.receive_json()
    assert response["success"]
    assert response["result"] == {"restart": True}
    assert hass_storage["http"]["data"]["pending"] is None
    assert hass_storage["http"]["data"]["stable"]["server_port"] == 9123
    await hass.async_block_till_done()
    assert len(restart_calls) == 3

    # Clearing again when there is no pending config is a no-op -> no restart.
    await ws_client.send_json_auto_id({"type": "http/config/configure", "config": None})
    response = await ws_client.receive_json()
    assert response["success"]
    assert response["result"] == {"restart": False}
    await hass.async_block_till_done()
    assert len(restart_calls) == 3


async def test_pending_config_auto_reverts_to_stable(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A loaded pending config reverts to stable if it is not confirmed in time."""
    hass_storage["http"] = _stable_http_storage(
        {"server_port": 9876}, pending={"server_port": 9999}
    )

    # A revert clears the pending config and restarts to apply stable.
    restart_calls = async_mock_service(hass, "homeassistant", "restart")

    # The revert deadline is anchored to the (frozen) load time.
    revert_at = dt_util.utcnow() + AUTO_REVERT_DELAY

    assert await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "websocket_api", {})
    await hass.async_start()
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)

    # While the unconfirmed pending config is active, a revert deadline is
    # returned alongside it.
    await ws_client.send_json_auto_id({"type": "http/config"})
    response = await ws_client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "stable": HTTP_STORAGE_SCHEMA({"server_port": 9876}),
        "pending": HTTP_STORAGE_SCHEMA({"server_port": 9999}),
        "revert_at": revert_at.isoformat(),
    }

    # After the delay elapses without a promotion, pending is dropped and a
    # restart is requested so the stable config is applied.
    freezer.tick(AUTO_REVERT_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass_storage["http"]["data"] == {
        "stable": HTTP_STORAGE_SCHEMA({"server_port": 9876}),
        "pending": None,
        "yaml_migration_done": True,
    }
    assert len(restart_calls) == 1


@pytest.mark.parametrize(
    "bind_error",
    [
        OSError(errno.EADDRINUSE, "Address already in use"),
        PermissionError(errno.EACCES, "Permission denied"),
        socket.gaierror(socket.EAI_NONAME, "Name or service not known"),
    ],
    ids=["address-in-use", "permission-denied", "unresolvable-host"],
)
async def test_pending_config_reverted_in_place_on_bind_failure(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    mock_create_server: Mock,
    bind_error: OSError,
) -> None:
    """A pending config that cannot be bound is reverted within the same start.

    The trial fails while the config is realized during setup, so the stable
    config is applied in place - no restart, no waiting out the trial window.
    """
    hass_storage[DOMAIN] = _stable_http_storage(
        {"server_port": 9876}, pending={"server_port": 80}
    )

    restart_calls = async_mock_service(hass, "homeassistant", "restart")

    stable_server = await _ephemeral_server(hass)
    mock_create_server.side_effect = [bind_error, stable_server]

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # The pending config is dropped and this same start continues on stable.
    assert hass_storage["http"]["data"] == {
        "stable": HTTP_STORAGE_SCHEMA({"server_port": 9876}),
        "pending": None,
        "yaml_migration_done": True,
    }
    assert hass.config.api is not None
    assert hass.config.api.port == 9876
    # The second bind attempt was for the stable config.
    assert mock_create_server.call_args_list[1].args[0].server_port == 9876
    # No restart is involved and no revert stays scheduled.
    assert len(restart_calls) == 0
    store = await async_get_and_load_store(hass)
    assert store.revert_deadline is None
    assert "could not be applied, reverting" in caplog.text
    assert "previous HTTP configuration has been restored (server port 9876)" in (
        caplog.text
    )
    stable_server.close()
    await stable_server.wait_closed()


async def test_pending_config_reverted_in_place_on_ssl_failure(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """A pending config whose SSL certificate is unusable reverts in place."""
    stable = dict(HTTP_STORAGE_SCHEMA({"server_port": 9876}))
    # Craft the raw storage payload: the schema validates that the SSL files
    # exist when the config is set, but they can vanish before the next start.
    pending = dict(HTTP_STORAGE_SCHEMA({"server_port": 9999}))
    pending["ssl_certificate"] = "/nonexistent/cert.pem"
    pending["ssl_key"] = "/nonexistent/key.pem"
    hass_storage[DOMAIN] = {
        "version": 2,
        "key": DOMAIN,
        "data": {"stable": stable, "pending": pending, "yaml_migration_done": True},
    }

    restart_calls = async_mock_service(hass, "homeassistant", "restart")

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass_storage["http"]["data"]["pending"] is None
    assert hass.config.api is not None
    assert hass.config.api.port == 9876
    assert hass.config.api.use_ssl is False
    assert len(restart_calls) == 0


async def test_pending_config_reverted_in_place_on_ssl_peer_cert_failure(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    tmp_path: Path,
) -> None:
    """A pending config whose SSL peer certificate is unusable reverts in place."""
    cert_path, key_path, _ = await hass.async_add_executor_job(
        _setup_empty_ssl_pem_files, tmp_path
    )
    stable = dict(HTTP_STORAGE_SCHEMA({"server_port": 9876}))
    pending = dict(
        HTTP_STORAGE_SCHEMA(
            {
                "server_port": 9999,
                "ssl_certificate": str(cert_path),
                "ssl_key": str(key_path),
            }
        )
    )
    # The peer certificate vanished after the config was stored.
    pending["ssl_peer_certificate"] = "/nonexistent/peer.pem"
    hass_storage[DOMAIN] = {
        "version": 2,
        "key": DOMAIN,
        "data": {"stable": stable, "pending": pending, "yaml_migration_done": True},
    }

    restart_calls = async_mock_service(hass, "homeassistant", "restart")

    with patch("ssl.SSLContext.load_cert_chain"):
        assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass_storage["http"]["data"]["pending"] is None
    assert hass.config.api is not None
    assert hass.config.api.port == 9876
    assert hass.config.api.use_ssl is False
    assert len(restart_calls) == 0


async def test_stable_config_ssl_peer_cert_failure_fails_setup(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    tmp_path: Path,
) -> None:
    """A stable config whose SSL peer certificate is unusable fails setup.

    An unusable stable SSL configuration must fail setup, activating recovery
    mode on a real boot.
    """
    cert_path, key_path, _ = await hass.async_add_executor_job(
        _setup_empty_ssl_pem_files, tmp_path
    )
    stable = dict(
        HTTP_STORAGE_SCHEMA(
            {
                "server_port": 9876,
                "ssl_certificate": str(cert_path),
                "ssl_key": str(key_path),
            }
        )
    )
    stable["ssl_peer_certificate"] = "/nonexistent/peer.pem"
    hass_storage[DOMAIN] = {
        "version": 2,
        "key": DOMAIN,
        "data": {"stable": stable, "pending": None, "yaml_migration_done": True},
    }

    with patch("ssl.SSLContext.load_cert_chain"):
        assert await async_setup_component(hass, DOMAIN, {}) is False


async def test_bound_server_closed_on_stop_before_start(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_create_server: Mock,
) -> None:
    """A bound server is closed on stop even if it never started serving.

    If setup fails after binding (or recovery mode tears Home Assistant down
    before serving starts), the stop event must close the server so a
    follow-up boot in the same process can bind the address again.
    """
    hass_storage[DOMAIN] = _stable_http_storage({"server_port": 9876})

    server = await _ephemeral_server(hass)
    mock_create_server.side_effect = [server]

    with patch.object(
        http.HomeAssistantHTTP,
        "async_initialize",
        side_effect=HomeAssistantError("Setup failed after binding"),
    ):
        assert not await async_setup_component(hass, DOMAIN, {})

    assert server.sockets
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert not server.sockets


async def test_stable_config_bind_failure_fails_setup(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_create_server: Mock,
) -> None:
    """A stable config that cannot be bound fails setup.

    Failing setup activates recovery mode on a real boot, which retries with
    the stable config and falls back to the default config, so Home Assistant
    stays reachable.
    """
    hass_storage[DOMAIN] = _stable_http_storage({"server_port": 80})

    restart_calls = async_mock_service(hass, "homeassistant", "restart")
    mock_create_server.side_effect = OSError(errno.EADDRINUSE, "Address already in use")

    assert not await async_setup_component(hass, DOMAIN, {})

    assert len(restart_calls) == 0
    assert hass_storage["http"]["data"] == {
        "stable": HTTP_STORAGE_SCHEMA({"server_port": 80}),
        "pending": None,
        "yaml_migration_done": True,
    }


async def test_pending_and_stable_config_bind_failure_fails_setup(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_create_server: Mock,
) -> None:
    """Setup fails when the trialed pending and the stable config cannot bind.

    The pending config must already be cleared and persisted, so the recovery
    boot and future normal starts use stable instead of re-trialing it.
    """
    hass_storage[DOMAIN] = _stable_http_storage(
        {"server_port": 9876}, pending={"server_port": 80}
    )

    mock_create_server.side_effect = [
        OSError(errno.EADDRINUSE, "Address already in use"),
        OSError(errno.EADDRINUSE, "Address already in use"),
    ]

    assert not await async_setup_component(hass, DOMAIN, {})

    assert hass_storage["http"]["data"]["pending"] is None


async def test_create_server_normalizes_unencodable_host(
    hass: HomeAssistant,
) -> None:
    """A host name the IDNA codec cannot encode raises OSError.

    create_server() raises UnicodeError (a ValueError) for such host names,
    e.g. a label longer than 63 characters; it must be normalized to OSError
    so the config fallback chain handles it like any other bind failure.
    """
    server = http.HomeAssistantHTTP(
        hass,
        server_host=[f"{'x' * 64}.example"],
        server_port=8123,
        ssl_certificate=None,
        ssl_peer_certificate=None,
        ssl_key=None,
        trusted_proxies=[],
        ssl_profile=http.SSL_MODERN,
    )
    with (
        patch.object(
            hass.loop,
            "create_server",
            side_effect=UnicodeError(
                "encoding with 'idna' codec failed (UnicodeError: label too long)"
            ),
        ),
        pytest.raises(OSError, match="error while resolving host"),
    ):
        await _REAL_CREATE_SERVER(server)


async def test_recovery_mode_bind_failure_falls_back_to_default_config(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    mock_create_server: Mock,
) -> None:
    """In recovery mode an unbindable stable config falls back to defaults.

    Recovery mode is the last resort and must not fail setup again, so the
    default config is applied in place to keep the recovery UI reachable.
    The stable config is left untouched.
    """
    hass_storage[DOMAIN] = _stable_http_storage({"server_port": 80})
    hass.config.recovery_mode = True

    default_server = await _ephemeral_server(hass)
    mock_create_server.side_effect = [
        OSError(errno.EADDRINUSE, "Address already in use"),
        default_server,
    ]

    assert await async_setup_component(hass, DOMAIN, {})

    assert "falling back to the default configuration" in caplog.text
    assert hass.config.api is not None
    assert hass.config.api.port == default_server_port()
    # The second bind attempt was for the default config.
    assert mock_create_server.call_args_list[1].args[0].server_port == (
        default_server_port()
    )
    assert hass_storage["http"]["data"]["stable"] == HTTP_STORAGE_SCHEMA(
        {"server_port": 80}
    )
    default_server.close()
    await default_server.wait_closed()


async def test_recovery_mode_default_config_bind_failure_fails_setup(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    mock_create_server: Mock,
) -> None:
    """Setup fails in recovery mode when even the default config cannot bind.

    The fallback chain is exhausted; failing setup makes the failure visible
    to the outside (e.g. the Supervisor rolls back a Core update whose API
    does not come up).
    """
    hass_storage[DOMAIN] = _stable_http_storage({"server_port": 80})
    hass.config.recovery_mode = True

    mock_create_server.side_effect = OSError(errno.EADDRINUSE, "Address already in use")

    assert not await async_setup_component(hass, DOMAIN, {})

    assert f"Failed to create HTTP server at port {default_server_port()}" in (
        caplog.text
    )


async def test_pending_config_promote_cancels_revert(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Promoting a pending config cancels the scheduled revert."""
    hass_storage["http"] = _stable_http_storage(
        {"server_port": 9876}, pending={"server_port": 9999}
    )

    restart_calls = async_mock_service(hass, "homeassistant", "restart")

    assert await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "websocket_api", {})
    await hass.async_start()
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)

    # Confirm the pending config before the revert fires.
    await ws_client.send_json_auto_id({"type": "http/config/promote"})
    response = await ws_client.receive_json()
    assert response["success"]

    # The deadline is cleared once the config is confirmed.
    await ws_client.send_json_auto_id({"type": "http/config"})
    response = await ws_client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "stable": HTTP_STORAGE_SCHEMA({"server_port": 9999}),
        "pending": None,
        "revert_at": None,
    }

    # The cancelled revert must not fire after the delay.
    freezer.tick(AUTO_REVERT_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass_storage["http"]["data"] == {
        "stable": HTTP_STORAGE_SCHEMA({"server_port": 9999}),
        "pending": None,
        "yaml_migration_done": True,
    }
    assert len(restart_calls) == 0


@pytest.mark.parametrize(
    "config",
    [
        {"server_port": "not-a-port"},
        {
            "use_x_forwarded_for": True,
            "trusted_proxies": ["not-an-ip-network"],
        },
    ],
)
async def test_websocket_http_config_invalid(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    config: dict,
) -> None:
    """Test that an invalid HTTP config is rejected."""
    assert await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "websocket_api", {})
    await hass.async_start()
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {"type": "http/config/configure", "config": config}
    )
    response = await ws_client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"
