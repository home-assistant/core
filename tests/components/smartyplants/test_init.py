"""Test SmartyPlants setup, availability and webhook pushes."""

import asyncio
from copy import deepcopy
from hashlib import sha256
import hmac
import json
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pysmartyplants import Sensor, SmartyPlantsConnectionError
import pytest

from homeassistant.components.smartyplants.const import (
    CONF_WEBHOOK_SECRET,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_WEBHOOK_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import SENSOR_FIXTURE

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import ClientSessionGenerator

WEBHOOK_ID = "smartyplants_test_webhook"
WEBHOOK_SECRET = "top-secret"

ENTRY_DATA = {
    CONF_HOST: "https://api.smartyplants.test",
    CONF_API_KEY: "sp_test_key_12345678",
    CONF_WEBHOOK_ID: WEBHOOK_ID,
    CONF_WEBHOOK_SECRET: WEBHOOK_SECRET,
}


def _sensor(**overrides: Any) -> Sensor:
    """Return the fixture sensor, with the given wire fields replaced."""
    payload = deepcopy(SENSOR_FIXTURE)
    payload.update(overrides)
    return Sensor.from_api(payload)


async def _setup(
    hass: HomeAssistant, sensors: list[Sensor] | None = None
) -> tuple[MockConfigEntry, AsyncMock]:
    """Set up the integration with a mocked client."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id="test")
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.smartyplants.SmartyPlantsClient", autospec=True
    ) as mock:
        client = mock.return_value
        client.async_get_sensors = AsyncMock(
            return_value=[_sensor()] if sensors is None else sensors
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry, client


def _push_body(**changes: Any) -> dict[str, Any]:
    """Build a sensor_update push carrying only what it changes."""
    payload: dict[str, Any] = {
        "event": "sensor_update",
        "sensor": {"id": "sensor-1"},
    }
    payload.update(changes)
    return payload


async def _post(
    hass_client_no_auth: ClientSessionGenerator,
    payload: Any,
    *,
    secret: str | None = WEBHOOK_SECRET,
    signature: str | None = None,
) -> int:
    """Post a webhook body and return the status code."""
    client = await hass_client_no_auth()
    body = json.dumps(payload).encode()

    headers = {}
    if signature is not None:
        headers["X-Smartyplants-Signature"] = signature
    elif secret is not None:
        headers["X-Smartyplants-Signature"] = hmac.new(
            secret.encode(), body, sha256
        ).hexdigest()

    response = await client.post(
        f"/api/webhook/{WEBHOOK_ID}", data=body, headers=headers
    )
    return response.status


async def test_entities_are_created_from_the_first_poll(hass: HomeAssistant) -> None:
    """Every reading on the fixture sensor becomes an entity."""
    await _setup(hass)

    assert hass.states.get("sensor.monstera_temperature").state == "22.5"
    assert hass.states.get("sensor.monstera_humidity").state == "55"
    assert hass.states.get("sensor.monstera_soil_moisture").state == "41"
    assert hass.states.get("sensor.monstera_light_quality").state == "78"
    assert hass.states.get("sensor.monstera_health_score").state == "82"
    assert hass.states.get("sensor.monstera_fertilise_in").state == "21"
    assert hass.states.get("sensor.monstera_battery").state == "87"


async def test_device_is_named_after_the_plant(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """The device carries the plant's name and the sensor's serial number."""
    entry, _ = await _setup(hass)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "sensor-1"), entry.entry_id
    )
    assert device is not None
    assert device.name == "Monstera"
    assert device.serial_number == "device-12345"
    assert device.manufacturer == "SmartyPlants"


async def test_offline_sensor_is_unavailable(hass: HomeAssistant) -> None:
    """A sensor the backend reports as offline stops reporting."""
    await _setup(hass, [_sensor(isOnline=False)])

    assert hass.states.get("sensor.monstera_temperature").state == STATE_UNAVAILABLE


async def test_sensor_dropped_from_the_payload_is_unavailable(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A sensor that disappears from the account stops reporting."""
    _, client = await _setup(hass)
    assert hass.states.get("sensor.monstera_temperature").state == "22.5"

    client.async_get_sensors.return_value = []
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.monstera_temperature").state == STATE_UNAVAILABLE


async def test_connection_failure_marks_entities_unavailable(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A backend outage is surfaced rather than leaving stale values on show."""
    _, client = await _setup(hass)

    client.async_get_sensors.side_effect = SmartyPlantsConnectionError("boom")
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.monstera_temperature").state == STATE_UNAVAILABLE


async def test_missing_readings_report_unknown(hass: HomeAssistant) -> None:
    """A sensor that has never reported has entities but no values."""
    await _setup(hass, [_sensor(readings=None)])

    assert hass.states.get("sensor.monstera_temperature").state == STATE_UNKNOWN


async def test_placeholder_reading_reports_unknown(hass: HomeAssistant) -> None:
    """The backend sends "-" for a metric it could not compute."""
    readings = deepcopy(SENSOR_FIXTURE["readings"])
    readings["moisture"]["value"] = "-"
    await _setup(hass, [_sensor(readings=readings)])

    assert hass.states.get("sensor.monstera_soil_moisture").state == STATE_UNKNOWN


async def test_numeric_string_reading_is_accepted(hass: HomeAssistant) -> None:
    """A number sent as a string is still a reading."""
    readings = deepcopy(SENSOR_FIXTURE["readings"])
    readings["moisture"]["value"] = "41"
    await _setup(hass, [_sensor(readings=readings)])

    assert hass.states.get("sensor.monstera_soil_moisture").state == "41.0"


async def test_calculating_metric_reports_unknown(hass: HomeAssistant) -> None:
    """A metric still being worked out is withheld."""
    readings = deepcopy(SENSOR_FIXTURE["readings"])
    readings["fertiliser"]["isCalculating"] = True
    await _setup(hass, [_sensor(readings=readings)])

    assert hass.states.get("sensor.monstera_fertilise_in").state == STATE_UNKNOWN


async def test_temperature_follows_the_backend_unit(hass: HomeAssistant) -> None:
    """A reading sent in Fahrenheit is read as Fahrenheit.

    Home Assistant then converts it for display, which is what proves the
    backend's unit was picked up: read as Celsius, 72.5 would have stayed
    72.5 instead of converting to 22.5.
    """
    readings = deepcopy(SENSOR_FIXTURE["readings"])
    readings["temperature"]["unit"] = "°F"
    readings["temperature"]["value"] = 72.5
    await _setup(hass, [_sensor(readings=readings)])

    state = hass.states.get("sensor.monstera_temperature")
    assert state.state == "22.5"
    assert state.attributes["unit_of_measurement"] == "°C"


async def test_display_precision_is_registered(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Readings are rounded for display rather than shown raw."""
    await _setup(hass)

    entry = entity_registry.async_get("sensor.monstera_temperature")
    assert entry.options["sensor"]["suggested_display_precision"] == 1


async def test_unload_entry(hass: HomeAssistant) -> None:
    """The entry unloads cleanly."""
    entry, _ = await _setup(hass)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_push_updates_state(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """A signed push is applied without waiting for the next poll."""
    await _setup(hass)
    assert hass.states.get("sensor.monstera_soil_moisture").state == "41"

    readings = deepcopy(SENSOR_FIXTURE["readings"])
    readings["moisture"]["value"] = 55
    assert await _post(hass_client_no_auth, _push_body(readings=readings)) == 200
    await hass.async_block_till_done()

    assert hass.states.get("sensor.monstera_soil_moisture").state == "55"


async def test_push_keeps_what_it_left_out(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """A push is flatter than a poll and must not blank the rest."""
    await _setup(hass)

    readings = deepcopy(SENSOR_FIXTURE["readings"])
    readings["moisture"]["value"] = 55
    assert await _post(hass_client_no_auth, _push_body(readings=readings)) == 200
    await hass.async_block_till_done()

    # The push carried no online flag, battery or health, so those survive.
    assert hass.states.get("sensor.monstera_soil_moisture").state == "55"
    assert hass.states.get("sensor.monstera_battery").state == "87"
    assert hass.states.get("sensor.monstera_health_score").state == "82"


async def test_push_can_take_a_sensor_offline(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """An explicit offline flag is a real change, not a missing field."""
    await _setup(hass)

    body = _push_body()
    body["sensor"]["isOnline"] = False
    assert await _post(hass_client_no_auth, body) == 200
    await hass.async_block_till_done()

    assert hass.states.get("sensor.monstera_temperature").state == STATE_UNAVAILABLE


async def test_push_for_an_unknown_sensor_is_ignored(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """A push naming a sensor we have no entities for changes nothing."""
    await _setup(hass)

    body = _push_body()
    body["sensor"]["id"] = "sensor-unknown"
    assert await _post(hass_client_no_auth, body) == 200
    await hass.async_block_till_done()

    assert hass.states.get("sensor.monstera_temperature").state == "22.5"


async def test_unknown_event_is_accepted_and_ignored(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """A new backend event type must not break an older integration."""
    await _setup(hass)

    body = _push_body()
    body["event"] = "something_new"
    assert await _post(hass_client_no_auth, body) == 200
    await hass.async_block_till_done()

    assert hass.states.get("sensor.monstera_temperature").state == "22.5"


async def test_push_without_a_signature_is_refused(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """An unsigned post is not trusted."""
    await _setup(hass)
    assert await _post(hass_client_no_auth, _push_body(), secret=None) == 401


async def test_push_with_a_wrong_signature_is_refused(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """A forged signature is rejected."""
    await _setup(hass)
    assert await _post(hass_client_no_auth, _push_body(), signature="deadbeef") == 401


async def test_pushes_are_refused_without_a_configured_secret(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Without a secret there is no way to prove who sent the push."""
    data = {
        key: value for key, value in ENTRY_DATA.items() if key != CONF_WEBHOOK_SECRET
    }
    entry = MockConfigEntry(domain=DOMAIN, data=data, unique_id="test")
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.smartyplants.SmartyPlantsClient", autospec=True
    ) as mock:
        mock.return_value.async_get_sensors = AsyncMock(return_value=[_sensor()])
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert await _post(hass_client_no_auth, _push_body(), secret="anything") == 401


async def test_malformed_body_is_refused(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """A body that is not JSON is rejected before anything reads it."""
    await _setup(hass)

    client = await hass_client_no_auth()
    body = b"not json"
    signature = hmac.new(WEBHOOK_SECRET.encode(), body, sha256).hexdigest()
    response = await client.post(
        f"/api/webhook/{WEBHOOK_ID}",
        data=body,
        headers={"X-Smartyplants-Signature": signature},
    )
    assert response.status == 400


@pytest.mark.parametrize(
    "payload",
    [
        "just a string",
        [1, 2, 3],
        {"sensor": {"id": "sensor-1"}},
        {"event": 42, "sensor": {"id": "sensor-1"}},
        {"event": ["sensor_update"], "sensor": {"id": "sensor-1"}},
        {"event": "sensor_update", "sensor": "sensor-1"},
        {"event": "sensor_update", "sensor": {"id": 42}},
        {"event": "sensor_update", "sensor": {"id": ["sensor-1"]}},
        {"event": "sensor_update", "sensor": {}},
    ],
)
async def test_malformed_payloads_are_refused(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    payload: Any,
) -> None:
    """Every field arrives from the internet and is checked before use."""
    await _setup(hass)
    assert await _post(hass_client_no_auth, payload) == 400
    await hass.async_block_till_done()

    assert hass.states.get("sensor.monstera_temperature").state == "22.5"


@pytest.mark.parametrize("timestamp", [123, ["2026-08-19"], {"at": "2026-08-19"}])
async def test_wrongly_typed_timestamp_does_not_break_the_update(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    timestamp: Any,
) -> None:
    """A non-string timestamp is dropped instead of reaching date handling."""
    await _setup(hass)

    readings = deepcopy(SENSOR_FIXTURE["readings"])
    readings["moisture"]["value"] = 55
    body = _push_body(readings=readings)
    body["timestamp"] = timestamp

    assert await _post(hass_client_no_auth, body) == 200
    await hass.async_block_till_done()

    assert hass.states.get("sensor.monstera_soil_moisture").state == "55"


async def test_push_during_a_poll_is_not_reverted(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A push that lands mid-poll survives the response the poll is storing.

    Both write the cached sensors, so without serialising them the poll would
    finish last and put its older readings back.
    """
    _, client = await _setup(hass)

    release = asyncio.Event()

    async def _slow_poll() -> list[Sensor]:
        await release.wait()
        return [_sensor()]  # still reporting the original 41% moisture

    client.async_get_sensors = AsyncMock(side_effect=_slow_poll)

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await asyncio.sleep(0)

    readings = deepcopy(SENSOR_FIXTURE["readings"])
    readings["moisture"]["value"] = 55
    push = hass.async_create_task(
        _post(hass_client_no_auth, _push_body(readings=readings))
    )
    await asyncio.sleep(0)

    release.set()
    assert await push == 200
    await hass.async_block_till_done()

    assert hass.states.get("sensor.monstera_soil_moisture").state == "55"
