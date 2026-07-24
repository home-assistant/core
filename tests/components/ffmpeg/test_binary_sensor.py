"""The tests for Home Assistant ffmpeg binary sensor."""

from unittest.mock import AsyncMock, patch

from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component

CONFIG_NOISE = {
    "binary_sensor": {"platform": "ffmpeg_noise", "input": "testinputvideo"}
}
CONFIG_MOTION = {
    "binary_sensor": {"platform": "ffmpeg_motion", "input": "testinputvideo"}
}


# -- ffmpeg noise binary_sensor --


async def test_noise_setup_component(hass: HomeAssistant) -> None:
    """Set up ffmpeg component."""
    with assert_setup_component(1, "binary_sensor"):
        await async_setup_component(hass, "binary_sensor", CONFIG_NOISE)
    await hass.async_block_till_done()

    assert hass.data["ffmpeg"].binary == "ffmpeg"
    assert hass.states.get("binary_sensor.ffmpeg_noise") is not None


@patch("haffmpeg.sensor.SensorNoise.open_sensor", side_effect=AsyncMock())
async def test_noise_setup_component_start(mock_start, hass: HomeAssistant) -> None:
    """Set up ffmpeg component."""
    with assert_setup_component(1, "binary_sensor"):
        await async_setup_component(hass, "binary_sensor", CONFIG_NOISE)
    await hass.async_block_till_done()

    assert hass.data["ffmpeg"].binary == "ffmpeg"
    assert hass.states.get("binary_sensor.ffmpeg_noise") is not None

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert mock_start.called

    entity = hass.states.get("binary_sensor.ffmpeg_noise")
    assert entity.state == "unavailable"


@patch("haffmpeg.sensor.SensorNoise")
async def test_noise_setup_component_start_callback(
    mock_ffmpeg, hass: HomeAssistant
) -> None:
    """Set up ffmpeg component."""
    mock_ffmpeg().open_sensor.side_effect = AsyncMock()
    mock_ffmpeg().close = AsyncMock()
    with assert_setup_component(1, "binary_sensor"):
        await async_setup_component(hass, "binary_sensor", CONFIG_NOISE)
    await hass.async_block_till_done()

    assert hass.data["ffmpeg"].binary == "ffmpeg"
    assert hass.states.get("binary_sensor.ffmpeg_noise") is not None

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    entity = hass.states.get("binary_sensor.ffmpeg_noise")
    assert entity.state == "off"

    mock_ffmpeg.call_args[0][1](True)
    await hass.async_block_till_done()

    entity = hass.states.get("binary_sensor.ffmpeg_noise")
    assert entity.state == "on"


# -- ffmpeg motion binary_sensor --


async def test_motion_setup_component(hass: HomeAssistant) -> None:
    """Set up ffmpeg component."""
    with assert_setup_component(1, "binary_sensor"):
        await async_setup_component(hass, "binary_sensor", CONFIG_MOTION)
    await hass.async_block_till_done()

    assert hass.data["ffmpeg"].binary == "ffmpeg"
    assert hass.states.get("binary_sensor.ffmpeg_motion") is not None


@patch("haffmpeg.sensor.SensorMotion.open_sensor", side_effect=AsyncMock())
async def test_motion_setup_component_start(mock_start, hass: HomeAssistant) -> None:
    """Set up ffmpeg component."""
    with assert_setup_component(1, "binary_sensor"):
        await async_setup_component(hass, "binary_sensor", CONFIG_MOTION)
    await hass.async_block_till_done()

    assert hass.data["ffmpeg"].binary == "ffmpeg"
    assert hass.states.get("binary_sensor.ffmpeg_motion") is not None

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert mock_start.called

    entity = hass.states.get("binary_sensor.ffmpeg_motion")
    assert entity.state == "unavailable"


@patch("haffmpeg.sensor.SensorMotion")
async def test_motion_setup_component_start_callback(
    mock_ffmpeg, hass: HomeAssistant
) -> None:
    """Set up ffmpeg component."""
    mock_ffmpeg().open_sensor.side_effect = AsyncMock()
    mock_ffmpeg().close = AsyncMock()
    with assert_setup_component(1, "binary_sensor"):
        await async_setup_component(hass, "binary_sensor", CONFIG_MOTION)
    await hass.async_block_till_done()

    assert hass.data["ffmpeg"].binary == "ffmpeg"
    assert hass.states.get("binary_sensor.ffmpeg_motion") is not None

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    entity = hass.states.get("binary_sensor.ffmpeg_motion")
    assert entity.state == "off"

    mock_ffmpeg.call_args[0][1](True)
    await hass.async_block_till_done()

    entity = hass.states.get("binary_sensor.ffmpeg_motion")
    assert entity.state == "on"
