"""GitHub PR artifact download functionality for frontend development."""

from __future__ import annotations

import io
import logging
import pathlib
import shutil
import zipfile

from aiogithubapi import (
    GitHubAPI,
    GitHubAuthenticationException,
    GitHubException,
    GitHubNotFoundException,
    GitHubPermissionException,
    GitHubRatelimitException,
)
from aiohttp import ClientError, ClientResponseError, ClientTimeout

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

GITHUB_REPO = "home-assistant/frontend"
ARTIFACT_NAME = "frontend-build"

ERROR_INVALID_TOKEN = (
    "GitHub token is invalid or expired. "
    "Please check your github_token in the frontend configuration. "
    "Generate a new token at https://github.com/settings/tokens"
)
ERROR_RATE_LIMIT = (
    "GitHub API rate limit exceeded or token lacks permissions. "
    "Ensure your token has 'repo' or 'public_repo' scope"
)


async def _get_pr_head_sha(client: GitHubAPI, pr_number: int) -> str:
    """Get the head SHA for the PR."""
    try:
        response = await client.generic(
            endpoint=f"/repos/home-assistant/frontend/pulls/{pr_number}",
        )
        return str(response.data["head"]["sha"])
    except GitHubAuthenticationException as err:
        raise HomeAssistantError(ERROR_INVALID_TOKEN) from err
    except (GitHubRatelimitException, GitHubPermissionException) as err:
        raise HomeAssistantError(ERROR_RATE_LIMIT) from err
    except GitHubNotFoundException as err:
        raise HomeAssistantError(
            f"PR #{pr_number} does not exist in repository {GITHUB_REPO}"
        ) from err
    except GitHubException as err:
        raise HomeAssistantError(f"GitHub API error: {err}") from err


async def _find_pr_artifact(client: GitHubAPI, pr_number: int, head_sha: str) -> str:
    """Find the build artifact for the given PR and commit SHA.

    Returns the artifact download URL.
    """
    try:
        response = await client.generic(
            endpoint="/repos/home-assistant/frontend/actions/workflows/ci.yaml/runs",
            params={"head_sha": head_sha, "per_page": 10},
        )

        for run in response.data.get("workflow_runs", []):
            if run["status"] == "completed" and run["conclusion"] == "success":
                artifacts_response = await client.generic(
                    endpoint=f"/repos/home-assistant/frontend/actions/runs/{run['id']}/artifacts",
                )

                for artifact in artifacts_response.data.get("artifacts", []):
                    if artifact["name"] == ARTIFACT_NAME:
                        _LOGGER.info(
                            "Found artifact '%s' from CI run #%s",
                            ARTIFACT_NAME,
                            run["id"],
                        )
                        return str(artifact["archive_download_url"])

        raise HomeAssistantError(
            f"No '{ARTIFACT_NAME}' artifact found for PR #{pr_number}. "
            "Possible reasons: CI has not run yet or is running, "
            "or the build failed, or the PR artifact expired. "
            f"Check https://github.com/{GITHUB_REPO}/pull/{pr_number}/checks"
        )
    except GitHubAuthenticationException as err:
        raise HomeAssistantError(ERROR_INVALID_TOKEN) from err
    except (GitHubRatelimitException, GitHubPermissionException) as err:
        raise HomeAssistantError(ERROR_RATE_LIMIT) from err
    except GitHubException as err:
        raise HomeAssistantError(f"GitHub API error: {err}") from err


async def _download_artifact_data(
    hass: HomeAssistant, artifact_url: str, github_token: str
) -> bytes:
    """Download artifact data from GitHub."""
    session = async_get_clientsession(hass)
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github+json",
    }

    try:
        response = await session.get(
            artifact_url, headers=headers, timeout=ClientTimeout(total=60)
        )
        response.raise_for_status()
        return await response.read()
    except ClientResponseError as err:
        if err.status == 401:
            raise HomeAssistantError(ERROR_INVALID_TOKEN) from err
        if err.status == 403:
            raise HomeAssistantError(ERROR_RATE_LIMIT) from err
        raise HomeAssistantError(
            f"Failed to download artifact: HTTP {err.status}"
        ) from err
    except TimeoutError as err:
        raise HomeAssistantError(
            "Timeout downloading artifact (>60s). Check your network connection"
        ) from err
    except ClientError as err:
        raise HomeAssistantError(f"Network error downloading artifact: {err}") from err


def _extract_artifact(
    artifact_data: bytes,
    cache_dir: pathlib.Path,
    head_sha: str,
) -> None:
    """Extract artifact and save SHA (runs in executor)."""
    frontend_dir = cache_dir / "hass_frontend"

    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    frontend_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(artifact_data)) as zip_file:
        zip_file.extractall(str(frontend_dir))

    # Save the commit SHA for cache validation
    sha_file = cache_dir / ".sha"
    sha_file.write_text(head_sha)


async def download_pr_artifact(
    hass: HomeAssistant,
    pr_number: int,
    github_token: str,
    tmp_dir: pathlib.Path,
) -> pathlib.Path | None:
    """Download and extract frontend PR artifact from GitHub.

    Returns the path to the tmp directory containing hass_frontend/, or None on failure.
    """
    client = GitHubAPI(
        token=github_token,
        session=async_get_clientsession(hass),
    )

    try:
        head_sha = await _get_pr_head_sha(client, pr_number)
    except HomeAssistantError as err:
        _LOGGER.error("%s", err)
        return None

    frontend_dir = tmp_dir / "hass_frontend"
    sha_file = tmp_dir / ".sha"

    if frontend_dir.exists() and sha_file.exists():
        cached_sha = await hass.async_add_executor_job(sha_file.read_text)
        if cached_sha.strip() == head_sha:
            _LOGGER.info(
                "Using cached PR #%s (commit %s) from %s",
                pr_number,
                head_sha[:8],
                tmp_dir,
            )
            return tmp_dir
        _LOGGER.info(
            "PR #%s has new commits (cached: %s, current: %s), re-downloading",
            pr_number,
            cached_sha[:8],
            head_sha[:8],
        )

    try:
        artifact_url = await _find_pr_artifact(client, pr_number, head_sha)

        _LOGGER.info("Downloading frontend PR #%s artifact", pr_number)
        artifact_data = await _download_artifact_data(hass, artifact_url, github_token)

        await hass.async_add_executor_job(
            _extract_artifact, artifact_data, tmp_dir, head_sha
        )

        _LOGGER.info(
            "Successfully downloaded and extracted PR #%s (commit %s) to %s",
            pr_number,
            head_sha[:8],
            tmp_dir,
        )
    except HomeAssistantError as err:
        _LOGGER.error("%s", err)
        return None
    except Exception:
        _LOGGER.exception("Unexpected error downloading PR #%s", pr_number)
        return None
    else:
        return tmp_dir
