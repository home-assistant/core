"""Test that the go2rtc Docker image version matches or exceeds the recommended version.

This test ensures that the go2rtc Docker image SHA pinned in
script/hassfest/docker.py corresponds to a version that is equal to or
greater than the RECOMMENDED_VERSION defined in homeassistant/components/go2rtc/const.py.

The test pulls the Docker image using the pinned SHA and runs the
`go2rtc --version` command inside the container to extract the version,
then compares it against RECOMMENDED_VERSION.
"""

import asyncio
import os
import re

from awesomeversion import AwesomeVersion
import pytest

from homeassistant.components.go2rtc.const import RECOMMENDED_VERSION
from script.hassfest.docker import _GO2RTC_SHA as DOCKER_SHA


async def _get_version_from_docker_sha() -> str:
    """Extract go2rtc version from Docker image using the pinned SHA."""

    image = f"ghcr.io/alexxit/go2rtc@sha256:{DOCKER_SHA}"

    pull_process = await asyncio.create_subprocess_exec(
        "docker",
        "pull",
        image,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, pull_stderr = await pull_process.communicate()

    if pull_process.returncode != 0:
        raise RuntimeError(f"Failed to pull go2rtc image: {pull_stderr.decode()}")

    # Run the container to get version
    run_process = await asyncio.create_subprocess_exec(
        "docker",
        "run",
        "--rm",
        image,
        "go2rtc",
        "--version",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    run_stdout, run_stderr = await run_process.communicate()

    if run_process.returncode != 0:
        raise RuntimeError(f"Failed to run go2rtc --version: {run_stderr.decode()}")

    # Parse version from output
    # Expected output format: "go2rtc version 1.9.12 (commit) linux/amd64" or similar
    output = run_stdout.decode().strip()
    version_match = re.search(r"version\s+([\d.]+)", output)

    if not version_match:
        raise RuntimeError(f"Could not parse version from go2rtc output: {output}")

    return version_match.group(1)


@pytest.mark.skipif(
    not os.environ.get("CI"),
    reason="This test requires Docker and only runs in CI",
)
async def test_docker_version_matches_recommended() -> None:
    """Test that the go2rtc Docker SHA version matches or exceeds RECOMMENDED_VERSION."""
    # Extract version from the actual Docker container
    docker_version_str = await _get_version_from_docker_sha()

    # Parse versions
    docker_version = AwesomeVersion(docker_version_str)
    recommended_version = AwesomeVersion(RECOMMENDED_VERSION)

    # Assert that Docker version is equal to or greater than recommended version
    assert docker_version >= recommended_version, (
        f"go2rtc Docker version ({docker_version}) is less than "
        f"RECOMMENDED_VERSION ({recommended_version}). "
        "Please update _GO2RTC_SHA in script/hassfest/docker.py to a newer version"
    )
