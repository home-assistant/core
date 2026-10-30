"""Fixtures for frontend tests."""

from collections.abc import Generator
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.frontend import MANIFEST_JSON


@pytest.fixture(autouse=True)
def isolated_manifest_json() -> Generator[None]:
    """Prevent theme changes to the module-level manifest leaking between tests."""
    original = deepcopy(MANIFEST_JSON.manifest)
    yield
    for key in MANIFEST_JSON.manifest.keys() - original.keys():
        del MANIFEST_JSON.manifest[key]
    for key, value in original.items():
        MANIFEST_JSON.update_key(key, value)


@pytest.fixture
def mock_github_api() -> Generator[AsyncMock]:
    """Mock aiogithubapi GitHubAPI."""
    with patch(
        "homeassistant.components.frontend.pr_download.GitHubAPI"
    ) as mock_gh_class:
        mock_client = AsyncMock()
        mock_gh_class.return_value = mock_client

        # Mock PR response
        pr_response = AsyncMock()
        pr_response.data = {
            "head": {"sha": "abc123def456"},
            "base": {"sha": "base789abc012"},
        }

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
def mock_zipfile() -> Generator[MagicMock]:
    """Mock zipfile extraction."""
    with patch("zipfile.ZipFile") as mock_zip:
        mock_zip_instance = MagicMock()
        # Mock infolist for zip bomb validation
        mock_info = MagicMock()
        mock_info.file_size = 1000  # Small file size
        mock_zip_instance.infolist.return_value = [mock_info]
        mock_zip.return_value.__enter__.return_value = mock_zip_instance
        yield mock_zip_instance
