"""Tests for the Zeversolar coordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.zeversolar.const import DOMAIN
from homeassistant.components.zeversolar.coordinator import ZeversolarCoordinator
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import MOCK_HOST, MOCK_ZEVERSOLAR_DATA, init_integration

from tests.common import MockConfigEntry


def _make_session_mock(response_text: str) -> MagicMock:
    """Return a mocked aiohttp ClientSession whose GET returns response_text."""
    mock_resp = AsyncMock()
    mock_resp.text.return_value = response_text

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_resp

    mock_session = MagicMock()
    mock_session.get.return_value = mock_cm
    return mock_session


def _adv_cgi_response(
    enlim: int = 1,
    ac_value1: int = 100,
    ac_mode: int = 1,
    num_lines: int = 15,
) -> str:
    """Build a minimal adv.cgi response with given field values."""
    lines = ["0"] * num_lines
    if num_lines > 8:
        lines[8] = str(enlim)
    if num_lines > 11:
        lines[11] = str(float(ac_value1))
    if num_lines > 14:
        lines[14] = str(ac_mode)
    return "\n".join(lines)


def _make_coordinator(hass: HomeAssistant) -> ZeversolarCoordinator:
    """Create a bare coordinator without going through async_setup_entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: MOCK_HOST})
    entry.add_to_hass(hass)
    return ZeversolarCoordinator(hass, entry)


async def test_probe_passes_with_valid_response(hass: HomeAssistant) -> None:
    """Probe returns True for a well-formed adv.cgi response."""
    coordinator = _make_coordinator(hass)

    with patch(
        "homeassistant.components.zeversolar.coordinator.async_get_clientsession",
        return_value=_make_session_mock(_adv_cgi_response()),
    ):
        result = await coordinator.async_probe_power_limit_api()

    assert result is True


async def test_probe_fails_on_connection_error(hass: HomeAssistant) -> None:
    """Probe returns False when adv.cgi cannot be reached."""
    coordinator = _make_coordinator(hass)

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(
        side_effect=Exception("refused")
    )

    with patch(
        "homeassistant.components.zeversolar.coordinator.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await coordinator.async_probe_power_limit_api()

    assert result is False


async def test_probe_fails_on_too_few_lines(hass: HomeAssistant) -> None:
    """Probe returns False when adv.cgi returns fewer than 15 lines."""
    coordinator = _make_coordinator(hass)

    with patch(
        "homeassistant.components.zeversolar.coordinator.async_get_clientsession",
        return_value=_make_session_mock(_adv_cgi_response(num_lines=10)),
    ):
        result = await coordinator.async_probe_power_limit_api()

    assert result is False


async def test_probe_fails_when_enlim_zero(hass: HomeAssistant) -> None:
    """Probe returns False when power limiting is disabled (enlim=0)."""
    coordinator = _make_coordinator(hass)

    with patch(
        "homeassistant.components.zeversolar.coordinator.async_get_clientsession",
        return_value=_make_session_mock(_adv_cgi_response(enlim=0)),
    ):
        result = await coordinator.async_probe_power_limit_api()

    assert result is False


async def test_probe_fails_when_enlim_negative(hass: HomeAssistant) -> None:
    """Probe returns False when enlim is negative."""
    coordinator = _make_coordinator(hass)

    with patch(
        "homeassistant.components.zeversolar.coordinator.async_get_clientsession",
        return_value=_make_session_mock(_adv_cgi_response(enlim=-1)),
    ):
        result = await coordinator.async_probe_power_limit_api()

    assert result is False


async def test_probe_fails_when_ac_mode_invalid(hass: HomeAssistant) -> None:
    """Probe returns False when ac_mode is not 0 or 1."""
    coordinator = _make_coordinator(hass)

    with patch(
        "homeassistant.components.zeversolar.coordinator.async_get_clientsession",
        return_value=_make_session_mock(_adv_cgi_response(ac_mode=2)),
    ):
        result = await coordinator.async_probe_power_limit_api()

    assert result is False


async def test_probe_fails_when_ac_value1_out_of_range(hass: HomeAssistant) -> None:
    """Probe returns False when ac_value1 is outside the valid 5–100 range."""
    coordinator = _make_coordinator(hass)

    with patch(
        "homeassistant.components.zeversolar.coordinator.async_get_clientsession",
        return_value=_make_session_mock(_adv_cgi_response(ac_value1=3)),
    ):
        result = await coordinator.async_probe_power_limit_api()

    assert result is False


async def test_probe_fails_when_fields_not_parseable(hass: HomeAssistant) -> None:
    """Probe returns False when adv.cgi fields cannot be parsed as integers."""
    coordinator = _make_coordinator(hass)

    lines = ["0"] * 15
    lines[8] = "not_a_number"
    response = "\n".join(lines)

    with patch(
        "homeassistant.components.zeversolar.coordinator.async_get_clientsession",
        return_value=_make_session_mock(response),
    ):
        result = await coordinator.async_probe_power_limit_api()

    assert result is False


async def test_fetch_power_limit_returns_current_limit(hass: HomeAssistant) -> None:
    """_fetch_power_limit reads the power limit percentage from field 11 of adv.cgi."""
    coordinator = _make_coordinator(hass)

    lines = ["0"] * 15
    lines[11] = "75.0"
    response = "\n".join(lines)

    with patch(
        "homeassistant.components.zeversolar.coordinator.async_get_clientsession",
        return_value=_make_session_mock(response),
    ):
        result = await coordinator._fetch_power_limit()

    assert result == 75


async def test_fetch_power_limit_raises_on_too_few_lines(hass: HomeAssistant) -> None:
    """_fetch_power_limit raises ValueError when adv.cgi returns fewer than 12 lines."""
    coordinator = _make_coordinator(hass)

    response = "\n".join(["0"] * 5)

    with (
        patch(
            "homeassistant.components.zeversolar.coordinator.async_get_clientsession",
            return_value=_make_session_mock(response),
        ),
        pytest.raises(ValueError),
    ):
        await coordinator._fetch_power_limit()


async def test_update_data_falls_back_to_cached_limit_when_fetch_fails(
    hass: HomeAssistant,
) -> None:
    """_async_update_data uses the cached power_limit when _fetch_power_limit raises."""
    entry = await init_integration(hass, power_limit_supported=True)
    coordinator = entry.runtime_data

    with (
        patch(
            "zeversolar.ZeverSolarClient.get_data",
            return_value=MOCK_ZEVERSOLAR_DATA,
        ),
        patch.object(
            coordinator,
            "_fetch_power_limit",
            side_effect=Exception("network error"),
        ),
    ):
        data = await coordinator._async_update_data()

    assert data["power_limit"] == 100
