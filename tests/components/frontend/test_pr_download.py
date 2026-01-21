"""Tests for frontend PR download functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

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

    # Mock artifact download
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

    # Verify GitHub API was called
    assert mock_github_api.generic.call_count >= 2  # PR + workflow runs

    # Verify artifact was downloaded
    assert len(aioclient_mock.mock_calls) == 1

    # Verify zip was extracted
    mock_zipfile.extractall.assert_called_once()


async def test_pr_download_uses_cache(
    hass: HomeAssistant, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that cached PR is used when commit hasn't changed."""
    hass.config.config_dir = str(tmp_path)

    # Create fake cache
    pr_cache_dir = tmp_path / "frontend_development_artifacts" / "12345"
    frontend_dir = pr_cache_dir / "hass_frontend"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text("test")
    (pr_cache_dir / ".sha").write_text("abc123def456")

    with patch(
        "homeassistant.components.frontend.pr_download.GitHubAPI"
    ) as mock_gh_class:
        mock_client = AsyncMock()
        mock_gh_class.return_value = mock_client

        # Mock PR response with same SHA as cache
        pr_response = AsyncMock()
        pr_response.data = {"head": {"sha": "abc123def456"}}
        mock_client.generic.return_value = pr_response

        config = {
            DOMAIN: {
                "development_pr": 12345,
                "github_token": "test_token",
            }
        }

        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        # Verify cache was used
        assert "Using cached PR #12345" in caplog.text

        # Should only call GitHub API to get PR SHA, not download
        # The generic call should only be for getting the PR
        calls = list(mock_client.generic.call_args_list)
        assert len(calls) == 1  # Only PR check
        assert "pulls" in str(calls[0])


async def test_pr_download_cache_invalidated(
    hass: HomeAssistant,
    tmp_path: Path,
    mock_github_api,
    aioclient_mock: AiohttpClientMocker,
    mock_zipfile,
) -> None:
    """Test that cache is invalidated when commit changes."""
    hass.config.config_dir = str(tmp_path)

    # Create fake cache with old commit
    pr_cache_dir = tmp_path / "frontend_development_artifacts" / "12345"
    frontend_dir = pr_cache_dir / "hass_frontend"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text("test")
    (pr_cache_dir / ".sha").write_text("old_commit_sha")

    # Mock artifact download
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

    # Should download - commit changed
    assert len(aioclient_mock.mock_calls) == 1


async def test_pr_download_missing_token(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that PR download fails gracefully without token."""
    config = {
        DOMAIN: {
            "development_pr": 12345,
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    # Verify error was logged
    assert "GitHub token is required to download PR artifacts" in caplog.text


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

        # Should not raise, just log error and fall back
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        # Verify appropriate error was logged
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

        # Mock PR response
        pr_response = AsyncMock()
        pr_response.data = {"head": {"sha": "abc123def456"}}

        # Mock workflow runs response with no artifacts
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

        # Verify error was logged
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

    # Mock artifact download failure
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

    # Verify error was logged
    assert "Failed to download PR #12345" in caplog.text
