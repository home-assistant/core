"""Tests for frontend PR download functionality."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.frontend import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_github():
    """Mock PyGithub."""
    with patch("github.Github") as mock_gh:
        # Mock GitHub client
        mock_client = MagicMock()
        mock_gh.return_value = mock_client

        # Mock repo
        mock_repo = MagicMock()
        mock_client.get_repo.return_value = mock_repo

        # Mock PR
        mock_pr = MagicMock()
        mock_pr.head.sha = "abc123def456"
        mock_repo.get_pull.return_value = mock_pr

        # Mock workflow
        mock_workflow = MagicMock()
        mock_repo.get_workflow.return_value = mock_workflow

        # Mock workflow run
        mock_run = MagicMock()
        mock_run.status = "completed"
        mock_run.conclusion = "success"
        mock_run.id = 12345
        mock_workflow.get_runs.return_value = [mock_run]

        # Mock artifact
        mock_artifact = MagicMock()
        mock_artifact.name = "frontend-build"
        mock_artifact.id = 67890
        mock_artifact.archive_download_url = "https://api.github.com/artifact/download"
        mock_run.get_artifacts.return_value = [mock_artifact]

        yield mock_client


@pytest.fixture
def mock_requests():
    """Mock requests library."""
    with patch("requests.get") as mock_req:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake zip data"
        mock_req.return_value = mock_response
        yield mock_req


@pytest.fixture
def mock_zipfile():
    """Mock zipfile extraction."""
    with patch("zipfile.ZipFile") as mock_zip:
        mock_zip_instance = MagicMock()
        mock_zip.return_value.__enter__.return_value = mock_zip_instance
        yield mock_zip_instance


async def test_pr_download_success(
    hass: HomeAssistant, tmp_path: Path, mock_github, mock_requests, mock_zipfile
) -> None:
    """Test successful PR artifact download."""
    hass.config.config_dir = str(tmp_path)

    config = {
        DOMAIN: {
            "development_pr": 12345,
            "github_token": "test_token",
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)

    # Verify GitHub operations happened
    mock_github.get_repo.assert_called_with("home-assistant/frontend")
    mock_github.get_repo.return_value.get_pull.assert_called_with(12345)

    # Verify artifact was downloaded
    mock_requests.assert_called_once()
    call_args_str = str(mock_requests.call_args)
    assert "token test_token" in call_args_str or "test_token" in call_args_str

    # Verify zip was extracted
    mock_zipfile.extractall.assert_called_once()


async def test_pr_download_uses_cache(
    hass: HomeAssistant, tmp_path: Path, mock_github
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

    with patch("requests.get") as mock_req:
        assert await async_setup_component(hass, DOMAIN, config)

        # Should NOT download - cache is valid
        mock_req.assert_not_called()


async def test_pr_download_cache_invalidated(
    hass: HomeAssistant, tmp_path: Path, mock_github, mock_requests, mock_zipfile
) -> None:
    """Test that cache is invalidated when commit changes."""
    hass.config.config_dir = str(tmp_path)

    # Create fake cache with old commit
    pr_cache_dir = tmp_path / "frontend_development_pr" / "12345"
    frontend_dir = pr_cache_dir / "hass_frontend"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text("test")
    (pr_cache_dir / ".sha").write_text("old_commit_sha")

    config = {
        DOMAIN: {
            "development_pr": 12345,
            "github_token": "test_token",
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)

    # Should download - commit changed
    mock_requests.assert_called_once()
