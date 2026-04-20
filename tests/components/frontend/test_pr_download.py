"""Tests for frontend PR download functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from aiogithubapi import (
    GitHubAuthenticationException,
    GitHubException,
    GitHubNotFoundException,
    GitHubPermissionException,
    GitHubRatelimitException,
)
from aiohttp import ClientError
import pytest

from homeassistant.components.frontend import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_pr_download_success(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_github_api,
    aioclient_mock: AiohttpClientMocker,
    mock_zipfile,
) -> None:
    """Test successful PR artifact download."""
    hass.config.config_dir = str(tmp_path)

    aioclient_mock.get(
        "https://api.github.com/artifact/download",
        content=b"fake zip data",
    )

    config = {
        DOMAIN: {
            "development_pr": 12345,
            "github_token": "test_token",
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert mock_github_api.generic.call_count >= 2  # PR + workflow runs

    assert len(aioclient_mock.mock_calls) == 1

    mock_zipfile.extractall.assert_called_once()


async def test_pr_download_uses_cache(
    hass: HomeAssistant, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that cached PR is used when commit hasn't changed."""
    hass.config.config_dir = str(tmp_path)

    pr_cache_dir = tmp_path / ".cache" / "frontend" / "development_artifacts"
    frontend_dir = pr_cache_dir / "hass_frontend"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text("test")
    (pr_cache_dir / ".sha").write_text("abc123def456:base789abc012")

    with patch(
        "homeassistant.components.frontend.pr_download.GitHubAPI"
    ) as mock_gh_class:
        mock_client = AsyncMock()
        mock_gh_class.return_value = mock_client

        pr_response = AsyncMock()
        pr_response.data = {
            "head": {"sha": "abc123def456"},
            "base": {"sha": "base789abc012"},
        }
        mock_client.generic.return_value = pr_response

        config = {
            DOMAIN: {
                "development_pr": 12345,
                "github_token": "test_token",
            }
        }

        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        assert "Using cached PR #12345" in caplog.text

        calls = list(mock_client.generic.call_args_list)
        assert len(calls) == 1  # Only PR check
        assert "pulls" in str(calls[0])


@pytest.mark.parametrize(
    ("cache_key"),
    [
        ("old_head_sha:base789abc012"),
        ("abc123def456:old_base_sha"),
    ],
)
async def test_pr_download_cache_invalidated(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_github_api,
    aioclient_mock: AiohttpClientMocker,
    mock_zipfile,
    cache_key: str,
) -> None:
    """Test that cache is invalidated when head commit changes."""
    hass.config.config_dir = str(tmp_path)

    pr_cache_dir = tmp_path / ".cache" / "frontend" / "development_artifacts"
    frontend_dir = pr_cache_dir / "hass_frontend"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text("test")
    (pr_cache_dir / ".sha").write_text(cache_key)

    aioclient_mock.get(
        "https://api.github.com/artifact/download",
        content=b"fake zip data",
    )

    config = {
        DOMAIN: {
            "development_pr": 12345,
            "github_token": "test_token",
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    # Should download - head commit changed
    assert len(aioclient_mock.mock_calls) == 1


async def test_pr_download_cache_sha_read_error(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_github_api: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    mock_zipfile: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that cache SHA read errors are handled gracefully."""
    hass.config.config_dir = str(tmp_path)

    pr_cache_dir = tmp_path / ".cache" / "frontend" / "development_artifacts"
    frontend_dir = pr_cache_dir / "hass_frontend"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text("test")
    sha_file = pr_cache_dir / ".sha"
    sha_file.write_text("abc123def456")
    sha_file.chmod(0o000)

    aioclient_mock.get(
        "https://api.github.com/artifact/download",
        content=b"fake zip data",
    )

    try:
        config = {
            DOMAIN: {
                "development_pr": 12345,
                "github_token": "test_token",
            }
        }

        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert "Failed to read cache SHA file" in caplog.text
    finally:
        sha_file.chmod(0o644)


async def test_pr_download_session_error(
    hass: HomeAssistant,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of session creation errors."""
    hass.config.config_dir = str(tmp_path)

    with patch(
        "homeassistant.components.frontend.pr_download.async_get_clientsession",
        side_effect=RuntimeError("Session error"),
    ):
        config = {
            DOMAIN: {
                "development_pr": 12345,
                "github_token": "test_token",
            }
        }

        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        assert "Failed to download PR #12345" in caplog.text


@pytest.mark.parametrize(
    ("exc", "error_message"),
    [
        (GitHubAuthenticationException("Unauthorized"), "invalid or expired"),
        (GitHubRatelimitException("Rate limit exceeded"), "rate limit"),
        (GitHubPermissionException("Forbidden"), "rate limit"),
        (GitHubNotFoundException("Not found"), "does not exist"),
        (GitHubException("API error"), "api error"),
    ],
)
async def test_pr_download_github_errors(
    hass: HomeAssistant,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    exc: Exception,
    error_message: str,
) -> None:
    """Test handling of various GitHub API errors."""
    hass.config.config_dir = str(tmp_path)

    with patch(
        "homeassistant.components.frontend.pr_download.GitHubAPI"
    ) as mock_gh_class:
        mock_client = AsyncMock()
        mock_gh_class.return_value = mock_client
        mock_client.generic.side_effect = exc

        config = {
            DOMAIN: {
                "development_pr": 12345,
                "github_token": "test_token",
            }
        }

        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        assert error_message in caplog.text.lower()
        assert "Failed to download PR #12345" in caplog.text


@pytest.mark.parametrize(
    ("exc", "error_message"),
    [
        (GitHubAuthenticationException("Unauthorized"), "invalid or expired"),
        (GitHubRatelimitException("Rate limit exceeded"), "rate limit"),
        (GitHubPermissionException("Forbidden"), "rate limit"),
        (GitHubException("API error"), "api error"),
    ],
)
async def test_pr_download_artifact_search_github_errors(
    hass: HomeAssistant,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    exc: Exception,
    error_message: str,
) -> None:
    """Test handling of GitHub API errors during artifact search."""
    hass.config.config_dir = str(tmp_path)

    with patch(
        "homeassistant.components.frontend.pr_download.GitHubAPI"
    ) as mock_gh_class:
        mock_client = AsyncMock()
        mock_gh_class.return_value = mock_client

        pr_response = AsyncMock()
        pr_response.data = {
            "head": {"sha": "abc123def456"},
            "base": {"sha": "base789abc012"},
        }

        async def generic_side_effect(endpoint, **_kwargs):
            if "pulls" in endpoint:
                return pr_response
            raise exc

        mock_client.generic.side_effect = generic_side_effect

        config = {
            DOMAIN: {
                "development_pr": 12345,
                "github_token": "test_token",
            }
        }

        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        assert error_message in caplog.text.lower()
        assert "Failed to download PR #12345" in caplog.text


async def test_pr_download_artifact_not_found(
    hass: HomeAssistant,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling when artifact is not found."""
    hass.config.config_dir = str(tmp_path)

    with patch(
        "homeassistant.components.frontend.pr_download.GitHubAPI"
    ) as mock_gh_class:
        mock_client = AsyncMock()
        mock_gh_class.return_value = mock_client

        pr_response = AsyncMock()
        pr_response.data = {
            "head": {"sha": "abc123def456"},
            "base": {"sha": "base789abc012"},
        }

        workflow_response = AsyncMock()
        workflow_response.data = {"workflow_runs": []}

        async def generic_side_effect(endpoint, **kwargs):
            if "pulls" in endpoint:
                return pr_response
            if "workflows" in endpoint:
                return workflow_response
            raise ValueError(f"Unexpected endpoint: {endpoint}")

        mock_client.generic.side_effect = generic_side_effect

        config = {
            DOMAIN: {
                "development_pr": 12345,
                "github_token": "test_token",
            }
        }

        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        assert "No 'frontend-build' artifact found" in caplog.text


async def test_pr_download_http_error(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_github_api: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of HTTP download errors."""
    hass.config.config_dir = str(tmp_path)

    aioclient_mock.get(
        "https://api.github.com/artifact/download",
        exc=ClientError("Download failed"),
    )

    config = {
        DOMAIN: {
            "development_pr": 12345,
            "github_token": "test_token",
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert "Failed to download PR #12345" in caplog.text


@pytest.mark.parametrize(
    ("status", "error_message"),
    [
        (401, "invalid or expired"),
        (403, "rate limit"),
        (500, "http 500"),
    ],
)
async def test_pr_download_http_status_errors(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_github_api: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    status: int,
    error_message: str,
) -> None:
    """Test handling of HTTP status errors during artifact download."""
    hass.config.config_dir = str(tmp_path)

    aioclient_mock.get(
        "https://api.github.com/artifact/download",
        status=status,
    )

    config = {
        DOMAIN: {
            "development_pr": 12345,
            "github_token": "test_token",
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert error_message in caplog.text.lower()
    assert "Failed to download PR #12345" in caplog.text


async def test_pr_download_timeout_error(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_github_api: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of timeout during artifact download."""
    hass.config.config_dir = str(tmp_path)

    aioclient_mock.get(
        "https://api.github.com/artifact/download",
        exc=TimeoutError("Connection timed out"),
    )

    config = {
        DOMAIN: {
            "development_pr": 12345,
            "github_token": "test_token",
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert "timeout" in caplog.text.lower()
    assert "Failed to download PR #12345" in caplog.text


async def test_pr_download_bad_zip_file(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_github_api: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of corrupted zip file."""
    hass.config.config_dir = str(tmp_path)

    aioclient_mock.get(
        "https://api.github.com/artifact/download",
        content=b"not a valid zip file",
    )

    config = {
        DOMAIN: {
            "development_pr": 12345,
            "github_token": "test_token",
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert "Failed to download PR #12345" in caplog.text
    assert "corrupted or invalid" in caplog.text.lower()


async def test_pr_download_zip_bomb_too_many_files(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_github_api: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that zip bombs with too many files are rejected."""
    hass.config.config_dir = str(tmp_path)

    aioclient_mock.get(
        "https://api.github.com/artifact/download",
        content=b"fake zip data",
    )

    with patch("zipfile.ZipFile") as mock_zip:
        mock_zip_instance = MagicMock()
        mock_info = MagicMock()
        mock_info.file_size = 100
        mock_zip_instance.infolist.return_value = [mock_info] * 55000
        mock_zip.return_value.__enter__.return_value = mock_zip_instance

        config = {
            DOMAIN: {
                "development_pr": 12345,
                "github_token": "test_token",
            }
        }

        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        assert "Failed to download PR #12345" in caplog.text
        assert "too many files" in caplog.text.lower()


async def test_pr_download_zip_bomb_too_large(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_github_api: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that zip bombs with excessive uncompressed size are rejected."""
    hass.config.config_dir = str(tmp_path)

    aioclient_mock.get(
        "https://api.github.com/artifact/download",
        content=b"fake zip data",
    )

    with patch("zipfile.ZipFile") as mock_zip:
        mock_zip_instance = MagicMock()
        mock_info = MagicMock()
        mock_info.file_size = 2 * 1024 * 1024 * 1024  # 2GB per file
        mock_zip_instance.infolist.return_value = [mock_info]
        mock_zip.return_value.__enter__.return_value = mock_zip_instance

        config = {
            DOMAIN: {
                "development_pr": 12345,
                "github_token": "test_token",
            }
        }

        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        assert "Failed to download PR #12345" in caplog.text
        assert "too large" in caplog.text.lower()


async def test_pr_download_extraction_os_error(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_github_api: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of OS errors during extraction."""
    hass.config.config_dir = str(tmp_path)

    aioclient_mock.get(
        "https://api.github.com/artifact/download",
        content=b"fake zip data",
    )

    with patch("zipfile.ZipFile") as mock_zip:
        mock_zip_instance = MagicMock()
        mock_info = MagicMock()
        mock_info.file_size = 100
        mock_zip_instance.infolist.return_value = [mock_info]
        mock_zip_instance.extractall.side_effect = OSError("Disk full")
        mock_zip.return_value.__enter__.return_value = mock_zip_instance

        config = {
            DOMAIN: {
                "development_pr": 12345,
                "github_token": "test_token",
            }
        }

        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        assert "Failed to download PR #12345" in caplog.text
        assert "failed to extract" in caplog.text.lower()
