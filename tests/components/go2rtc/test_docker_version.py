"""Test that the pinned go2rtc Docker image matches or exceeds the recommended version.

The go2rtc image does not expose its version as an OCI label (the version is
only compiled into the binary). The SHA->version mapping is therefore recorded
in script/hassfest/docker.py as the ``_GO2RTC_VERSION`` constant paired with
``_GO2RTC_SHA``. hassfest verifies, against the GHCR registry, that the digest
really is the one published for that version whenever the pair changes, and
stores the verified pair in script/hassfest/generated/go2rtc.json so the check
is not repeated on every CI run.

Given that verified mapping, this test only needs to assert, offline, that the
pinned version is equal to or greater than the RECOMMENDED_VERSION defined in
homeassistant/components/go2rtc/const.py, catching a RECOMMENDED_VERSION bump
without a corresponding image bump (or vice versa).
"""

from awesomeversion import AwesomeVersion

from homeassistant.components.go2rtc.const import RECOMMENDED_VERSION
from script.hassfest.docker import _GO2RTC_VERSION as DOCKER_VERSION


def test_docker_version_matches_recommended() -> None:
    """Test that the pinned go2rtc Docker version is >= RECOMMENDED_VERSION."""
    docker_version = AwesomeVersion(DOCKER_VERSION)
    recommended_version = AwesomeVersion(RECOMMENDED_VERSION)

    assert docker_version >= recommended_version, (
        f"The pinned go2rtc Docker version ({docker_version}) is less than "
        f"RECOMMENDED_VERSION ({recommended_version}). Please update "
        "_GO2RTC_VERSION and _GO2RTC_SHA in script/hassfest/docker.py to a "
        "newer version"
    )
