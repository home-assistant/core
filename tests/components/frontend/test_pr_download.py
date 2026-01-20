"""Tests for frontend PR download functionality."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from aiogithubapi import GitHubException
import pytest

from homeassistant.components.frontend import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def mock_github_api():
    """Mock aiogithubapi GitHubAPI."""
    with patch(
        "homeassistant.components.frontend.pr_download.GitHubAPI"
    ) as mock_gh_class:
        mock_client = AsyncMock()
        mock_gh_class.return_value = mock_client

        # Mock PR response
        pr_response = AsyncMock()
        pr_response.data = {"head": {"sha": "abc123def456"}}

        # Mock workflow runs response
        workflow_response = AsyncMock()
        workflow_response.data = {
            "workflow_runs": [
                {
                    "id": 12345,
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        }

        # Mock artifacts response
        artifacts_response = AsyncMock()
        artifacts_response.data = {
            "artifacts": [
                {
                    "name": "frontend-build",
                    "archive_download_url": "https://api.github.com/artifact/download",
                }
            ]
        }

        # Setup generic method to return appropriate responses
        async def generic_side_effect(endpoint, **kwargs):
            if "pulls" in endpoint:
                return pr_response
            if "workflows" in endpoint and "runs" in endpoint:
                return workflow_response
            if "artifacts" in endpoint:
                return artifacts_response
            raise ValueError(f"Unexpected endpoint: {endpoint}")

        mock_client.generic.side_effect = generic_side_effect

        yield mock_client


@pytest.fixture
def mock_zipfile():
    """Mock zipfile extraction."""
    with patch("zipfile.ZipFile") as mock_zip:
        mock_zip_instance = MagicMock()
        mock_zip.return_value.__enter__.return_value = mock_zip_instance
        yield mock_zip_instance


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
    hass: HomeAssistant, tmp_path: Path, mock_github_api
) -> None:
    """Test that cached PR is used when commit hasn't changed."""
    hass.config.config_dir = str(tmp_path)

    # Create fake cache
    pr_cache_dir = tmp_path / "frontend_development_pr" / "12345"
    frontend_dir = pr_cache_dir / "hass_frontend"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text("test")
    (pr_cache_dir / ".sha").write_text("abc123def456")

    config = {
        DOMAIN: {
            "development_pr": 12345,
            "github_token": "test_token",
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    # Should only call GitHub API to get PR SHA, not download
    # The generic call should only be for getting the PR
    calls = list(mock_github_api.generic.call_args_list)
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
    pr_cache_dir = tmp_path / "frontend_development_pr" / "12345"
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


async def test_pr_download_missing_token(hass: HomeAssistant) -> None:
    """Test that PR download fails gracefully without token."""
    config = {
        DOMAIN: {
            "development_pr": 12345,
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_pr_download_github_error(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test handling of GitHub API errors."""
    hass.config.config_dir = str(tmp_path)

    with patch(
        "homeassistant.components.frontend.pr_download.GitHubAPI"
    ) as mock_gh_class:
        mock_client = AsyncMock()
        mock_gh_class.return_value = mock_client
        mock_client.generic.side_effect = GitHubException("API error")

        config = {
            DOMAIN: {
                "development_pr": 12345,
                "github_token": "test_token",
            }
        }

        # Should not raise, just log error
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
