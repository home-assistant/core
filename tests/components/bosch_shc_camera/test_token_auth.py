"""Tests for token_auth.py's TokenAuthCoordinatorMixin refresh logic.

Exercises the public `ensure_valid_token` path through a real
`BoschCameraCoordinator` built from a `MockConfigEntry` — not by binding
private mixin methods onto a bare `SimpleNamespace` — so the coordinator,
config-entry, and locking contracts are all genuinely exercised instead of
bypassed (bug-hunt 2026-07-27, Copilot review round 6).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homeassistant.components.bosch_shc_camera import BoschCameraCoordinator
from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


def _make_coordinator(hass: HomeAssistant) -> BoschCameraCoordinator:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={"bearer_token": "old-token", "refresh_token": "rtok"},
        options={},
    )
    entry.add_to_hass(hass)
    return BoschCameraCoordinator(hass, entry)


async def _refresh(coord: BoschCameraCoordinator) -> str:
    with patch(
        "homeassistant.components.bosch_shc_camera.token_auth.async_get_bosch_cloud_session",
        AsyncMock(return_value=MagicMock()),
    ):
        return await coord.ensure_valid_token("old-token")


@pytest.mark.asyncio
async def test_repeated_timeouts_never_trigger_reauth(hass: HomeAssistant) -> None:
    """A refresh-timeout must stay transient (UpdateFailed) no matter how many times it repeats.

    It proves nothing about the refresh token's validity, unlike a genuine
    invalid-grant rejection (bug-hunt 2026-07-27, Copilot review round 4).
    """
    coord = _make_coordinator(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.config_flow._do_refresh",
            AsyncMock(side_effect=TimeoutError()),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.token_auth.asyncio.sleep",
            AsyncMock(),
        ),
    ):
        for _ in range(5):
            with pytest.raises(UpdateFailed):
                await _refresh(coord)

    # 3 per-attempt retries per call — each one increments the counter.
    assert coord._token_timeout_fail_count == 15
    # The reauth-escalation counter must be completely untouched by timeouts.
    assert coord._token_fail_count == 0


@pytest.mark.asyncio
async def test_repeated_empty_responses_do_trigger_reauth(hass: HomeAssistant) -> None:
    """A genuinely empty/malformed (non-timeout) refresh response is a real failure signal.

    It must still escalate to ConfigEntryAuthFailed after 3 consecutive
    occurrences.
    """
    coord = _make_coordinator(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.config_flow._do_refresh",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.token_auth.asyncio.sleep",
            AsyncMock(),
        ),
    ):
        for _ in range(2):
            with pytest.raises(UpdateFailed):
                await _refresh(coord)
        with pytest.raises(ConfigEntryAuthFailed):
            await _refresh(coord)

    assert coord._token_fail_count == 3
    assert coord._token_timeout_fail_count == 0


@pytest.mark.asyncio
async def test_success_resets_both_counters(hass: HomeAssistant) -> None:
    """A successful refresh clears both the timeout and reauth-escalation counters."""
    coord = _make_coordinator(hass)
    coord._token_fail_count = 2
    coord._token_timeout_fail_count = 4

    with patch(
        "homeassistant.components.bosch_shc_camera.config_flow._do_refresh",
        AsyncMock(
            return_value={"access_token": "new-token", "refresh_token": "new-rtok"}
        ),
    ):
        out = await _refresh(coord)

    assert out == "new-token"
    assert coord._token_fail_count == 0
    assert coord._token_timeout_fail_count == 0


@pytest.mark.asyncio
async def test_repeated_client_errors_never_trigger_reauth(hass: HomeAssistant) -> None:
    """A network/DNS-class aiohttp.ClientError must stay transient too.

    `_do_refresh` used to swallow this into a bare `None` return,
    indistinguishable from an ambiguous HTTP response, so repeated DNS/
    connection failures still incremented `_token_fail_count` and
    eventually triggered unnecessary reauthentication despite the
    timeout-only fix (bug-hunt 2026-07-27, Copilot review round 5).
    """
    coord = _make_coordinator(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.config_flow._do_refresh",
            AsyncMock(side_effect=aiohttp.ClientConnectionError("DNS failure")),
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.token_auth.asyncio.sleep",
            AsyncMock(),
        ),
    ):
        for _ in range(5):
            with pytest.raises(UpdateFailed):
                await _refresh(coord)

    assert coord._token_timeout_fail_count == 15
    assert coord._token_fail_count == 0
