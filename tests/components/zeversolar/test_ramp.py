"""Unit tests for the Zeversolar ramp controller."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.zeversolar.const import MINIMUM_LIMIT
from homeassistant.components.zeversolar.ramp import async_ramp
from homeassistant.core import HomeAssistant


def _adv_cgi_response(current: int) -> str:
    """Build a minimal adv.cgi response with the given power limit at line 11."""
    lines = ["0"] * 15
    lines[11] = str(float(current))
    return "\n".join(lines)


def _make_session_mock(response_text: str) -> MagicMock:
    """Return a mocked aiohttp ClientSession whose GET returns response_text."""
    mock_resp = AsyncMock()
    mock_resp.text.return_value = response_text

    # session.get() is not a coroutine — it returns an async context manager directly.
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_resp

    mock_session = MagicMock()
    mock_session.get.return_value = mock_cm
    return mock_session


async def test_ramp_down_writes_correct_steps(hass: HomeAssistant) -> None:
    """Ramping down writes each intermediate step in order."""
    with (
        patch(
            "homeassistant.components.zeversolar.ramp.async_get_clientsession",
            return_value=_make_session_mock(_adv_cgi_response(100)),
        ),
        patch(
            "homeassistant.components.zeversolar.ramp._async_write_limit",
            new_callable=AsyncMock,
        ) as mock_write,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await async_ramp(hass, "192.168.1.1", 80)

    written = [call.args[2] for call in mock_write.call_args_list]
    assert written == [90, 80]


async def test_ramp_up_writes_correct_steps(hass: HomeAssistant) -> None:
    """Ramping up writes each intermediate step in order."""
    with (
        patch(
            "homeassistant.components.zeversolar.ramp.async_get_clientsession",
            return_value=_make_session_mock(_adv_cgi_response(50)),
        ),
        patch(
            "homeassistant.components.zeversolar.ramp._async_write_limit",
            new_callable=AsyncMock,
        ) as mock_write,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await async_ramp(hass, "192.168.1.1", 70)

    written = [call.args[2] for call in mock_write.call_args_list]
    assert written == [60, 70]


async def test_ramp_calls_on_step_after_each_write(hass: HomeAssistant) -> None:
    """on_step callback is called once per step with the new value."""
    step_values: list[int] = []

    async def on_step(v: int) -> None:
        step_values.append(v)

    with (
        patch(
            "homeassistant.components.zeversolar.ramp.async_get_clientsession",
            return_value=_make_session_mock(_adv_cgi_response(100)),
        ),
        patch(
            "homeassistant.components.zeversolar.ramp._async_write_limit",
            new_callable=AsyncMock,
        ),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await async_ramp(hass, "192.168.1.1", 80, on_step)

    assert step_values == [90, 80]


async def test_ramp_does_nothing_when_already_at_target(hass: HomeAssistant) -> None:
    """No writes occur when current equals target."""
    with (
        patch(
            "homeassistant.components.zeversolar.ramp.async_get_clientsession",
            return_value=_make_session_mock(_adv_cgi_response(100)),
        ),
        patch(
            "homeassistant.components.zeversolar.ramp._async_write_limit",
            new_callable=AsyncMock,
        ) as mock_write,
    ):
        await async_ramp(hass, "192.168.1.1", 100)

    mock_write.assert_not_called()


async def test_ramp_clamps_target_to_minimum(hass: HomeAssistant) -> None:
    """A target below MINIMUM_LIMIT is clamped; the final write is exactly MINIMUM_LIMIT."""
    with (
        patch(
            "homeassistant.components.zeversolar.ramp.async_get_clientsession",
            return_value=_make_session_mock(_adv_cgi_response(20)),
        ),
        patch(
            "homeassistant.components.zeversolar.ramp._async_write_limit",
            new_callable=AsyncMock,
        ) as mock_write,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await async_ramp(hass, "192.168.1.1", 0)  # 0 is below minimum

    written = [call.args[2] for call in mock_write.call_args_list]
    assert len(written) > 0
    assert all(v >= MINIMUM_LIMIT for v in written)
    assert written[-1] == MINIMUM_LIMIT


async def test_ramp_aborts_on_read_failure(hass: HomeAssistant) -> None:
    """If adv.cgi cannot be read, the ramp aborts without writing anything."""
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__ = AsyncMock(
        side_effect=Exception("connection refused")
    )

    with (
        patch(
            "homeassistant.components.zeversolar.ramp.async_get_clientsession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.zeversolar.ramp._async_write_limit",
            new_callable=AsyncMock,
        ) as mock_write,
    ):
        await async_ramp(hass, "192.168.1.1", 50)

    mock_write.assert_not_called()
