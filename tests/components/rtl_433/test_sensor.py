"""Test the rtl_433 sensor platform."""

from unittest.mock import MagicMock, patch

from pyrtl_433.normalizer import NormalizedEvent
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rtl_433.const import (
    CONF_SECURE,
    DEVICE_FIELDS,
    DOMAIN,
    MINOR_VERSION,
    VERSION,
)
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_MODEL,
    CONF_PATH,
    CONF_PORT,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import emit_event, setup_integration
from .conftest import MOCK_HOST, MOCK_PATH, MOCK_PORT, MOCK_UNIQUE_ID

from tests.common import MockConfigEntry, snapshot_platform

TEMPERATURE_ENTITY_ID = "sensor.acurite_606tx_temperature_c"
DEVICE_KEY = "Acurite-606TX-42"

# A later frame from the same device carrying a field the first one did not.
HUMIDITY_EVENT = NormalizedEvent(
    device_key=DEVICE_KEY,
    model="Acurite-606TX",
    identity={"model": "Acurite-606TX", "id": 42},
    fields={"humidity": 55},
)


async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rtl433_client: MagicMock,
    mock_event: NormalizedEvent,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test one sensor entity is created per measurement field of a device."""
    with patch("homeassistant.components.rtl_433.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

        # No entities exist until the device first transmits.
        assert not er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )

        await emit_event(hass, mock_rtl433_client, mock_event)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_value_updates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rtl433_client: MagicMock,
    mock_event: NormalizedEvent,
) -> None:
    """Test a subsequent event updates the sensor's native value."""
    await setup_integration(hass, mock_config_entry)
    await emit_event(hass, mock_rtl433_client, mock_event)

    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "21.5"

    await emit_event(
        hass,
        mock_rtl433_client,
        NormalizedEvent(
            device_key="Acurite-606TX-42",
            model="Acurite-606TX",
            identity={"model": "Acurite-606TX", "id": 42},
            fields={"temperature_C": 19.0, "battery_ok": 1},
        ),
    )

    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == "19.0"


async def test_sensors_restored_from_entry_devices(
    hass: HomeAssistant,
    mock_rtl433_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities for known devices exist before the device next transmits.

    An RF device announces itself only by transmitting, so a device recorded on
    the config entry has to be rebuilt from that record at startup rather than
    waiting an unbounded time for the next event.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"rtl_433 ({MOCK_HOST})",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PATH: MOCK_PATH,
            CONF_SECURE: False,
            CONF_DEVICES: {
                "Acurite-606TX-42": {
                    CONF_MODEL: "Acurite-606TX",
                    DEVICE_FIELDS: ["temperature_C"],
                }
            },
        },
        unique_id=MOCK_UNIQUE_ID,
        version=VERSION,
        minor_version=MINOR_VERSION,
    )

    await setup_integration(hass, entry)

    entity_entry = entity_registry.async_get(TEMPERATURE_ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.unique_id == f"{entry.entry_id}:Acurite-606TX-42:temperature_C"
    # It has never transmitted in this session, so it reads unavailable.
    assert hass.states.get(TEMPERATURE_ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("extra_events", "expected_fields"),
    [
        pytest.param([], ["battery_ok", "temperature_C"], id="first_sighting"),
        pytest.param(
            [HUMIDITY_EVENT],
            ["battery_ok", "humidity", "temperature_C"],
            id="new_field_unioned",
        ),
    ],
)
async def test_discovered_devices_persisted(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rtl433_client: MagicMock,
    mock_event: NormalizedEvent,
    extra_events: list[NormalizedEvent],
    expected_fields: list[str],
) -> None:
    """Test discovered devices and fields are recorded on the config entry."""
    await setup_integration(hass, mock_config_entry)
    assert CONF_DEVICES not in mock_config_entry.data

    for event in (mock_event, *extra_events):
        await emit_event(hass, mock_rtl433_client, event)

    assert mock_config_entry.data[CONF_DEVICES] == {
        DEVICE_KEY: {
            CONF_MODEL: "Acurite-606TX",
            DEVICE_FIELDS: expected_fields,
        }
    }


async def test_repeated_event_does_not_rewrite_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rtl433_client: MagicMock,
    mock_event: NormalizedEvent,
) -> None:
    """Test a device transmitting again leaves the stored record untouched.

    RF devices retransmit every few seconds, so an unconditional write would
    churn the config entry for the life of the process.
    """
    await setup_integration(hass, mock_config_entry)
    await emit_event(hass, mock_rtl433_client, mock_event)

    with patch.object(
        hass.config_entries,
        "async_update_entry",
        wraps=hass.config_entries.async_update_entry,
    ) as mock_update_entry:
        await emit_event(hass, mock_rtl433_client, mock_event)

    mock_update_entry.assert_not_called()
