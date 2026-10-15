"""Tests for the Wireless Sensor Tags sensor platform."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.sensor import SCAN_INTERVAL
from homeassistant.const import PERCENTAGE, STATE_UNAVAILABLE, UnitOfTemperature
from homeassistant.core import HomeAssistant, valid_entity_id
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed

UUID = "00000000-0000-0000-0000-000000000001"
ENTITY_ID = "sensor.wirelesstag_bedroom_temperature"

CONFIG = {
    "wirelesstag": {"username": "foo@bar.com", "password": "secret"},
    "sensor": {
        "platform": "wirelesstag",
        "monitored_conditions": ["temperature", "humidity"],
    },
}


def _mock_tag(name: str) -> MagicMock:
    """Return a mocked wirelesstagpy SensorTag exposing temperature and humidity."""
    tag = MagicMock()
    tag.uuid = UUID
    tag.tag_id = 1
    tag.tag_manager_mac = "ABCDEF012345"
    tag.name = name
    tag.allowed_sensor_types = ["temperature", "humidity"]
    tag.is_alive = True
    tag.battery_remaining = 0.85
    tag.battery_volts = 3.0
    tag.signal_strength = -60
    tag.is_in_range = True
    tag.power_consumption = 1.5

    def _sensor(sensor_type: str) -> MagicMock:
        sensor = MagicMock()
        if sensor_type == "temperature":
            sensor.value = 21.5
            sensor.unit = UnitOfTemperature.CELSIUS
        else:
            sensor.value = 45.0
            sensor.unit = PERCENTAGE
        return sensor

    tag.sensor.__getitem__.side_effect = _sensor
    return tag


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the platform poll the tag once."""
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _recover_by_poll(
    hass: HomeAssistant,
    tag: MagicMock,
    mock_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Make the tag available again through the polling path."""
    mock_api.load_tags.return_value = {tag.uuid: tag}
    await _poll(hass, freezer)


async def _recover_by_push(
    hass: HomeAssistant,
    tag: MagicMock,
    mock_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Make the tag available again through a push notification."""
    push_callback = mock_api.start_monitoring.call_args[0][0]
    # The library calls back from its own worker thread.
    await hass.async_add_executor_job(push_callback, {tag.uuid: tag}, {})


@pytest.mark.parametrize(
    ("tag_name", "expected_entity_id"),
    [
        pytest.param("Bedroom", ENTITY_ID, id="ascii_name"),
        pytest.param(
            "Küche",
            "sensor.wirelesstag_kuche_temperature",
            id="non_ascii_name",
        ),
    ],
)
async def test_sensor_entity_id_is_valid(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    tag_name: str,
    expected_entity_id: str,
) -> None:
    """Test sensors get a valid entity_id even for non-ASCII tag names.

    A tag named e.g. "Küche" previously produced the invalid entity_id
    "sensor.wirelesstag_küche_temperature", which is rejected by Home
    Assistant's entity ID validation.
    """
    tag = _mock_tag(tag_name)
    with patch("homeassistant.components.wirelesstag.WirelessTags") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.load_tags.return_value = {tag.uuid: tag}

        assert await async_setup_component(hass, "wirelesstag", CONFIG)
        await hass.async_block_till_done()
        assert await async_setup_component(hass, "sensor", CONFIG)
        await hass.async_block_till_done()

    state = hass.states.get(expected_entity_id)
    assert state is not None
    assert valid_entity_id(state.entity_id)
    assert "sets an invalid entity ID" not in caplog.text


@pytest.mark.parametrize(
    "recover",
    [
        pytest.param(_recover_by_poll, id="poll"),
        pytest.param(_recover_by_push, id="push"),
    ],
)
async def test_update_handles_tag_missing_from_reload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    recover: Callable[
        [HomeAssistant, MagicMock, MagicMock, FrozenDateTimeFactory], Awaitable[None]
    ],
) -> None:
    """Test an update where the tag is no longer returned is handled gracefully.

    If a reload no longer contains the entity's tag, the update must mark the
    entity unavailable instead of raising a KeyError or keeping a stale value.
    The entity recovers once the tag shows up again, by poll or by push.
    """
    tag = _mock_tag("Bedroom")
    with patch("homeassistant.components.wirelesstag.WirelessTags") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.load_tags.return_value = {tag.uuid: tag}

        assert await async_setup_component(hass, "wirelesstag", CONFIG)
        await hass.async_block_till_done()
        assert await async_setup_component(hass, "sensor", CONFIG)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == "21.5"

        # The tag is no longer returned by a reload.
        mock_api.load_tags.return_value = {}
        await _poll(hass, freezer)

        assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

        await recover(hass, tag, mock_api, freezer)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == "21.5"
