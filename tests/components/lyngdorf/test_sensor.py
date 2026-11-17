"""Tests for the Lyngdorf sensor platform."""

from unittest.mock import MagicMock

from lyngdorf import NumericRange
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lyngdorf.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import _steppable, notify_receiver_update


@pytest.fixture
def platforms() -> list[Platform]:
    """Only load the sensor platform."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("mock_receiver", "entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_sensor_none_values(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test a sensor shows unknown when the device reports nothing."""
    mock_receiver.audio_information_reading.value = None
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.mock_lyngdorf_audio_information").state == STATE_UNKNOWN
    )


async def test_enum_sensor_ignores_unknown_device_value(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test an input the library could not name is reported as unknown."""
    mock_receiver.audio_input_reading.options = ["optical"]
    mock_receiver.audio_input_reading.value = "audio-37"

    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.mock_lyngdorf_audio_input").state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("entity_id", "attribute", "value"),
    [
        pytest.param(
            "sensor.mock_lyngdorf_video_input",
            "video_input_reading",
            ["DP"],
            id="video",
        ),
        pytest.param(
            "sensor.mock_lyngdorf_streaming_source",
            "streaming_source_reading",
            ["Spotify"],
            id="stream",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_sensor_options_follow_the_reading(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    entity_id: str,
    attribute: str,
    value: list[str],
) -> None:
    """Test the options come from the reading."""
    getattr(mock_receiver, attribute).options = value
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).attributes["options"] == value


@pytest.mark.usefixtures("init_integration")
async def test_zone_b_sensors_read_the_zone_readings(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test the Zone B sensors follow the zone's readings."""
    mock_receiver.zone_b.audio_input_reading.value = "optical"
    mock_receiver.zone_b.streaming_source_reading.value = "AirPlay"
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.mock_lyngdorf_zone_b_audio_input").state == "optical"
    assert (
        hass.states.get("sensor.mock_lyngdorf_zone_b_streaming_source").state
        == "AirPlay"
    )


@pytest.mark.usefixtures("init_integration")
async def test_enum_options_follow_the_device(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
) -> None:
    """Test enum options track the lists the device reports."""
    mock_receiver.audio_input_reading.options = ["HDMI", "optical"]
    mock_receiver.audio_input_reading.value = "HDMI"
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.mock_lyngdorf_audio_input")
    assert state.attributes["options"] == ["HDMI", "optical"]

    mock_receiver.audio_input_reading.options = ["HDMI", "optical", "ARC"]
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.mock_lyngdorf_audio_input")
    assert state.attributes["options"] == ["HDMI", "optical", "ARC"]


async def test_maximum_volume_is_disabled_by_default(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the ceiling sensor exists but is off by default."""
    entry = entity_registry.async_get("sensor.mock_lyngdorf_maximum_volume")

    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get("sensor.mock_lyngdorf_maximum_volume") is None


async def test_maximum_volume_follows_the_device(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the ceiling sensor reports what the device says, once enabled."""
    entity_id = "sensor.mock_lyngdorf_maximum_volume"
    mock_receiver.volume.maximum_volume = 0.0

    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "0.0"

    # The ceiling changes from the device's front panel, so it must not be
    # read once and cached.
    mock_receiver.volume.maximum_volume = -20.0
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "-20.0"


async def test_no_maximum_volume_sensor_without_a_volume_control(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a model that reports no ceiling does not get the sensor."""
    mock_config_entry.add_to_hass(hass)
    mock_receiver.volume = _steppable(-40.0, NumericRange(-99.9, 24.0, 0.1))

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get("sensor.mock_lyngdorf_maximum_volume") is None
    assert hass.states.get("sensor.mock_lyngdorf_audio_information") is not None


READING_KEYS = (
    "audio_information",
    "video_information",
    "audio_input",
    "video_input",
    "streaming_source",
)
READING_ENTITY_IDS = tuple(f"sensor.mock_lyngdorf_{key}" for key in READING_KEYS)


def _register_reading_sensors(
    entity_registry: er.EntityRegistry, config_entry: MockConfigEntry
) -> None:
    for key in READING_KEYS:
        entity_registry.async_get_or_create(
            Platform.SENSOR,
            DOMAIN,
            f"{config_entry.unique_id}_{key}",
            config_entry=config_entry,
            suggested_object_id=f"mock_lyngdorf_{key}",
        )


@pytest.mark.usefixtures("receiver_without_optional_features", "init_integration")
async def test_reading_sensors_not_created_without_reading(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a model without the readings gets none of their sensors."""
    for entity_id in READING_ENTITY_IDS:
        assert entity_registry.async_get(entity_id) is None
        assert hass.states.get(entity_id) is None
    assert hass.states.get("sensor.mock_lyngdorf_zone_b_audio_input") is not None


@pytest.mark.usefixtures("receiver_without_optional_features")
async def test_stale_reading_entities_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test reading sensors a model can never fill are removed from the registry."""
    mock_config_entry.add_to_hass(hass)
    _register_reading_sensors(entity_registry, mock_config_entry)
    for entity_id in READING_ENTITY_IDS:
        assert entity_registry.async_get(entity_id) is not None

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for entity_id in READING_ENTITY_IDS:
        assert entity_registry.async_get(entity_id) is None
        assert hass.states.get(entity_id) is None


@pytest.mark.usefixtures("mock_receiver")
async def test_reading_entities_kept_when_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test reading sensors a model supports survive setup and have state."""
    mock_config_entry.add_to_hass(hass)
    _register_reading_sensors(entity_registry, mock_config_entry)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for entity_id in READING_ENTITY_IDS:
        assert entity_registry.async_get(entity_id) is not None
        assert hass.states.get(entity_id).state != STATE_UNKNOWN
