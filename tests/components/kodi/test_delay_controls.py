"""Tests for Kodi playback delay controls."""

from unittest.mock import AsyncMock, MagicMock

from jsonrpc_base.jsonrpc import ProtocolError, TransportError
import pytest

from homeassistant.components.kodi.button import DELAY_BUTTONS, KodiPlaybackDelayButton
from homeassistant.components.kodi.coordinator import KodiPlaybackCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


@pytest.fixture
def coordinator(hass: HomeAssistant) -> KodiPlaybackCoordinator:
    """Create a coordinator whose transport supports delay readback."""
    kodi = MagicMock()
    kodi.get_players = AsyncMock(return_value=[{"playerid": 1, "type": "video"}])
    kodi.get_player_properties = AsyncMock(return_value={})
    kodi.call_method = AsyncMock(return_value={})
    entry = MockConfigEntry(domain="kodi", data={"name": "Kodi"})
    return KodiPlaybackCoordinator(hass, entry, MagicMock(connected=True), kodi)


def mock_delay_transport(
    coordinator: KodiPlaybackCoordinator,
    *,
    audio: float = 0.2,
    subtitle: float = 0.3,
    step: float = 0.1,
    legacy: bool = False,
    ignore_after_first: bool = False,
) -> dict[str, float]:
    """Model Kodi's external delay state and relative actions."""
    delays = {"audio": audio, "subtitle": subtitle}
    actions = 0

    async def call_method(method: str, **kwargs: object) -> object:
        nonlocal actions
        if method == "Settings.GetSettingValue":
            return {"value": 80}
        if method == "Player.GetViewMode":
            return {}
        if method == "XBMC.GetInfoLabels":
            return {
                "Player.AudioDelay": f"{delays['audio']:.3f} s",
                "Player.SubtitleDelay": f"{delays['subtitle']:.3f} s",
            }
        if method == "Player.SetAudioDelay":
            if legacy:
                raise ProtocolError(-32601, "Unsupported method", None)
            assert kwargs["playerid"] == 1
            offset = kwargs["offset"]
            if offset == "increment":
                delays["audio"] += step
            elif offset == "decrement":
                delays["audio"] -= step
            else:
                assert offset == 0
                delays["audio"] = 0
            return {"offset": delays["audio"]}
        assert method == "Input.ExecuteAction"
        actions += 1
        if ignore_after_first and actions > 1:
            return "OK"
        action = kwargs["action"]
        kind, adjustment = {
            "audiodelayplus": ("audio", step),
            "audiodelayminus": ("audio", -step),
            "subtitledelayplus": ("subtitle", step),
            "subtitledelayminus": ("subtitle", -step),
        }[action]
        delays[kind] += adjustment
        return "OK"

    coordinator.kodi.call_method.side_effect = call_method
    return delays


@pytest.mark.parametrize(
    "legacy", [pytest.param(False, id="native"), pytest.param(True, id="legacy")]
)
@pytest.mark.parametrize(
    ("key", "kind", "expected"),
    [
        pytest.param("increase_audio_delay", "audio", 0.3, id="audio-increase"),
        pytest.param("decrease_audio_delay", "audio", 0.1, id="audio-decrease"),
        pytest.param("reset_audio_delay", "audio", 0, id="audio-reset"),
        pytest.param(
            "increase_subtitle_delay", "subtitle", 0.4, id="subtitle-increase"
        ),
        pytest.param(
            "decrease_subtitle_delay", "subtitle", 0.2, id="subtitle-decrease"
        ),
        pytest.param("reset_subtitle_delay", "subtitle", 0, id="subtitle-reset"),
    ],
)
async def test_delay_actions(
    coordinator: KodiPlaybackCoordinator,
    legacy: bool,
    key: str,
    kind: str,
    expected: float,
) -> None:
    """All delay controls change the device offset and read back the result."""
    delays = mock_delay_transport(coordinator, legacy=legacy)
    await coordinator.async_refresh()
    description = next(item for item in DELAY_BUTTONS if item.key == key)
    await KodiPlaybackDelayButton(coordinator, description).async_press()
    assert delays[kind] == pytest.approx(expected)
    assert coordinator.data[f"{kind}_delay"] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("initial", "step"),
    [
        pytest.param(0, 0.1, id="already-zero"),
        pytest.param(0.3, 0.1, id="positive"),
        pytest.param(-0.3, 0.1, id="negative"),
        pytest.param(0.15, 0.05, id="custom-step"),
    ],
)
async def test_subtitle_reset(
    coordinator: KodiPlaybackCoordinator, initial: float, step: float
) -> None:
    """Reset offsets of either sign using Kodi's configured relative step."""
    delays = mock_delay_transport(coordinator, subtitle=initial, step=step)
    await coordinator.async_refresh()
    await KodiPlaybackDelayButton(coordinator, DELAY_BUTTONS[5]).async_press()
    assert delays["subtitle"] == pytest.approx(0)
    assert coordinator.data["subtitle_delay"] == pytest.approx(0)


async def test_unrepresentable_reset(coordinator: KodiPlaybackCoordinator) -> None:
    """Restore the original offset when relative steps cannot reach zero."""
    delays = mock_delay_transport(coordinator, subtitle=0.15)
    await coordinator.async_refresh()
    with pytest.raises(HomeAssistantError) as exc:
        await KodiPlaybackDelayButton(coordinator, DELAY_BUTTONS[5]).async_press()
    assert exc.value.translation_key == "delay_reset_failed"
    assert delays["subtitle"] == pytest.approx(0.15)


async def test_reset_requires_zero_readback(
    coordinator: KodiPlaybackCoordinator,
) -> None:
    """An acknowledged action must not silently leave the delay nonzero."""
    delays = mock_delay_transport(coordinator, ignore_after_first=True)
    await coordinator.async_refresh()
    with pytest.raises(HomeAssistantError) as exc:
        await KodiPlaybackDelayButton(coordinator, DELAY_BUTTONS[5]).async_press()
    assert exc.value.translation_key == "delay_reset_failed"
    assert delays["subtitle"] == pytest.approx(0.2)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TransportError("Offline"), id="transport"),
        pytest.param(ProtocolError(-32100, "Rejected", None), id="rejected"),
    ],
)
async def test_delay_command_failure(
    coordinator: KodiPlaybackCoordinator, error: Exception
) -> None:
    """Surface command failures without changing the reported delay."""
    delays = mock_delay_transport(coordinator)
    original = coordinator.kodi.call_method.side_effect

    async def call_method(method: str, **kwargs: object) -> object:
        if method == "Input.ExecuteAction":
            raise error
        return await original(method, **kwargs)

    coordinator.kodi.call_method.side_effect = call_method
    await coordinator.async_refresh()
    with pytest.raises(HomeAssistantError) as exc:
        await KodiPlaybackDelayButton(coordinator, DELAY_BUTTONS[3]).async_press()
    assert exc.value.translation_key == "delay_change_failed"
    assert delays["subtitle"] == pytest.approx(0.3)


async def test_delay_unavailable_when_playback_stops(
    coordinator: KodiPlaybackCoordinator,
) -> None:
    """Reject a previously available delay control after playback ends."""
    mock_delay_transport(coordinator)
    await coordinator.async_refresh()
    button = KodiPlaybackDelayButton(coordinator, DELAY_BUTTONS[0])
    assert button.available
    coordinator.kodi.get_players.return_value = []
    with pytest.raises(HomeAssistantError) as exc:
        await button.async_press()
    assert exc.value.translation_key == "playback_unavailable"
    assert not button.available
