"""The tests for the Home Assistant HTTP component."""
from datetime import timedelta
from http import HTTPStatus
from ipaddress import ip_network
import logging
import pathlib
from unittest.mock import Mock, patch

import pytest

import homeassistant.components.http as http
from homeassistant.helpers.network import NoURLAvailableError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.ssl import server_context_intermediate, server_context_modern

from tests.common import async_fire_time_changed


def _setup_broken_ssl_pem_files(tmpdir):
    test_dir = tmpdir.mkdir("test_broken_ssl")
    cert_path = pathlib.Path(test_dir) / "cert.pem"
    cert_path.write_text("garbage")
    key_path = pathlib.Path(test_dir) / "key.pem"
    key_path.write_text("garbage")
    return cert_path, key_path


def _setup_empty_ssl_pem_files(tmpdir):
    test_dir = tmpdir.mkdir("test_empty_ssl")
    cert_path = pathlib.Path(test_dir) / "cert.pem"
    cert_path.write_text("-")
    peer_cert_path = pathlib.Path(test_dir) / "peer_cert.pem"
    peer_cert_path.write_text("-")
    key_path = pathlib.Path(test_dir) / "key.pem"
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
    hass, aiohttp_client, aiohttp_unused_port
):
    """Test that we can register a view while the server is running."""
    await async_setup_component(
        hass, http.DOMAIN, {http.DOMAIN: {http.CONF_SERVER_PORT: aiohttp_unused_port()}}
    )

    await hass.async_start()
    # This raises a RuntimeError if app is frozen
    hass.http.register_view(TestView)


async def test_not_log_password(hass, hass_client_no_auth, caplog, legacy_auth):
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


async def test_proxy_config(hass):
    """Test use_x_forwarded_for must config together with trusted_proxies."""
    assert (
        await async_setup_component(
            hass,
            "http",
            {
                "http": {
                    http.CONF_USE_X_FORWARDED_FOR: True,
                    http.CONF_TRUSTED_PROXIES: ["127.0.0.1"],
                }
            },
        )
        is True
    )


async def test_proxy_config_only_use_xff(hass):
    """Test use_x_forwarded_for must config together with trusted_proxies."""
    assert (
        await async_setup_component(
            hass, "http", {"http": {http.CONF_USE_X_FORWARDED_FOR: True}}
        )
        is not True
    )


async def test_proxy_config_only_trust_proxies(hass):
    """Test use_x_forwarded_for must config together with trusted_proxies."""
    assert (
        await async_setup_component(
            hass, "http", {"http": {http.CONF_TRUSTED_PROXIES: ["127.0.0.1"]}}
        )
        is not True
    )


async def test_ssl_profile_defaults_modern(hass, tmpdir):
    """Test default ssl profile."""

    cert_path, key_path, _ = await hass.async_add_executor_job(
        _setup_empty_ssl_pem_files, tmpdir
    )

    with patch("ssl.SSLContext.load_cert_chain"), patch(
        "homeassistant.util.ssl.server_context_modern",
        side_effect=server_context_modern,
    ) as mock_context:
        assert (
            await async_setup_component(
                hass,
                "http",
                {"http": {"ssl_certificate": cert_path, "ssl_key": key_path}},
            )
            is True
        )
        await hass.async_start()
        await hass.async_block_till_done()

    assert len(mock_context.mock_calls) == 1


async def test_ssl_profile_change_intermediate(hass, tmpdir):
    """Test setting ssl profile to intermediate."""

    cert_path, key_path, _ = await hass.async_add_executor_job(
        _setup_empty_ssl_pem_files, tmpdir
    )

    with patch("ssl.SSLContext.load_cert_chain"), patch(
        "homeassistant.util.ssl.server_context_intermediate",
        side_effect=server_context_intermediate,
    ) as mock_context:
        assert (
            await async_setup_component(
                hass,
                "http",
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


async def test_ssl_profile_change_modern(hass, tmpdir):
    """Test setting ssl profile to modern."""

    cert_path, key_path, _ = await hass.async_add_executor_job(
        _setup_empty_ssl_pem_files, tmpdir
    )

    with patch("ssl.SSLContext.load_cert_chain"), patch(
        "homeassistant.util.ssl.server_context_modern",
        side_effect=server_context_modern,
    ) as mock_context:
        assert (
            await async_setup_component(
                hass,
                "http",
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


async def test_peer_cert(hass, tmpdir):
    """Test required peer cert."""
    cert_path, key_path, peer_cert_path = await hass.async_add_executor_job(
        _setup_empty_ssl_pem_files, tmpdir
    )

    with patch("ssl.SSLContext.load_cert_chain"), patch(
        "ssl.SSLContext.load_verify_locations"
    ) as mock_load_verify_locations, patch(
        "homeassistant.util.ssl.server_context_modern",
        side_effect=server_context_modern,
    ) as mock_context:
        assert (
            await async_setup_component(
                hass,
                "http",
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


async def test_emergency_ssl_certificate_when_invalid(hass, tmpdir, caplog):
    """Test http can startup with an emergency self signed cert when the current one is broken."""

    cert_path, key_path = await hass.async_add_executor_job(
        _setup_broken_ssl_pem_files, tmpdir
    )

    hass.config.safe_mode = True
    assert (
        await async_setup_component(
            hass,
            "http",
            {
                "http": {"ssl_certificate": cert_path, "ssl_key": key_path},
            },
        )
        is True
    )

    await hass.async_start()
    await hass.async_block_till_done()
    assert (
        "Home Assistant is running in safe mode with an emergency self signed ssl certificate because the configured SSL certificate was not usable"
        in caplog.text
    )

    assert hass.http.site is not None


async def test_emergency_ssl_certificate_not_used_when_not_safe_mode(
    hass, tmpdir, caplog
):
    """Test an emergency cert is only used in safe mode."""

    cert_path, key_path = await hass.async_add_executor_job(
        _setup_broken_ssl_pem_files, tmpdir
    )

    assert (
        await async_setup_component(
            hass, "http", {"http": {"ssl_certificate": cert_path, "ssl_key": key_path}}
        )
        is False
    )


async def test_emergency_ssl_certificate_when_invalid_get_url_fails(
    hass, tmpdir, caplog
):
    """Test http falls back to no ssl when an emergency cert cannot be created when the configured one is broken.

    Ensure we can still start of we cannot determine the external url as well.
    """
    cert_path, key_path = await hass.async_add_executor_job(
        _setup_broken_ssl_pem_files, tmpdir
    )
    hass.config.safe_mode = True

    with patch(
        "homeassistant.components.http.get_url", side_effect=NoURLAvailableError
    ) as mock_get_url:
        assert (
            await async_setup_component(
                hass,
                "http",
                {
                    "http": {"ssl_certificate": cert_path, "ssl_key": key_path},
                },
            )
            is True
        )
        await hass.async_start()
        await hass.async_block_till_done()

    assert len(mock_get_url.mock_calls) == 1
    assert (
        "Home Assistant is running in safe mode with an emergency self signed ssl certificate because the configured SSL certificate was not usable"
        in caplog.text
    )

    assert hass.http.site is not None


async def test_invalid_ssl_and_cannot_create_emergency_cert(hass, tmpdir, caplog):
    """Test http falls back to no ssl when an emergency cert cannot be created when the configured one is broken."""

    cert_path, key_path = await hass.async_add_executor_job(
        _setup_broken_ssl_pem_files, tmpdir
    )
    hass.config.safe_mode = True

    with patch(
        "homeassistant.components.http.x509.CertificateBuilder", side_effect=OSError
    ) as mock_builder:
        assert (
            await async_setup_component(
                hass,
                "http",
                {
                    "http": {"ssl_certificate": cert_path, "ssl_key": key_path},
                },
            )
            is True
        )
        await hass.async_start()
        await hass.async_block_till_done()
    assert "Could not create an emergency self signed ssl certificate" in caplog.text
    assert len(mock_builder.mock_calls) == 1

    assert hass.http.site is not None


async def test_invalid_ssl_and_cannot_create_emergency_cert_with_ssl_peer_cert(
    hass, tmpdir, caplog
):
    """Test http falls back to no ssl when an emergency cert cannot be created when the configured one is broken.

    When there is a peer cert verification and we cannot create
    an emergency cert (probably will never happen since this means
    the system is very broken), we do not want to startup http
    as it would allow connections that are not verified by the cert.
    """

    cert_path, key_path = await hass.async_add_executor_job(
        _setup_broken_ssl_pem_files, tmpdir
    )
    hass.config.safe_mode = True

    with patch(
        "homeassistant.components.http.x509.CertificateBuilder", side_effect=OSError
    ) as mock_builder:
        assert (
            await async_setup_component(
                hass,
                "http",
                {
                    "http": {
                        "ssl_certificate": cert_path,
                        "ssl_key": key_path,
                        "ssl_peer_certificate": cert_path,
                    },
                },
            )
            is False
        )
        await hass.async_start()
        await hass.async_block_till_done()
    assert "Could not create an emergency self signed ssl certificate" in caplog.text
    assert len(mock_builder.mock_calls) == 1


async def test_cors_defaults(hass):
    """Test the CORS default settings."""
    with patch("homeassistant.components.http.setup_cors") as mock_setup:
        assert await async_setup_component(hass, "http", {})

    assert len(mock_setup.mock_calls) == 1
    assert mock_setup.mock_calls[0][1][1] == ["https://cast.home-assistant.io"]


async def test_storing_config(hass, aiohttp_client, aiohttp_unused_port):
    """Test that we store last working config."""
    config = {
        http.CONF_SERVER_PORT: aiohttp_unused_port(),
        "use_x_forwarded_for": True,
        "trusted_proxies": ["192.168.1.100"],
    }

    assert await async_setup_component(hass, http.DOMAIN, {http.DOMAIN: config})

    await hass.async_start()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=200))
    await hass.async_block_till_done()

    restored = await hass.components.http.async_get_last_config()
    restored["trusted_proxies"][0] = ip_network(restored["trusted_proxies"][0])

    assert restored == http.HTTP_SCHEMA(config)
