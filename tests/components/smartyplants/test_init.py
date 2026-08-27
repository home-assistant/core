"""Test SmartyPlants setup, staleness, device churn and webhook pushes."""

import asyncio
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import hmac
import json
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pysmartyplants import SmartyPlantsConnectionError
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
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from .conftest import PLANT_WITHOUT_SENSOR, SENSOR_FIXTURE

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


def _fresh_sensor(timestamp: str) -> dict:
    """Return the fixture with a specific report time."""
    sensor = deepcopy(SENSOR_FIXTURE)
    sensor["lastDataReceived"] = timestamp
    return sensor


async def _setup(
    hass: HomeAssistant, sensors: list[dict], plants: list[dict] | None = None
) -> tuple[MockConfigEntry, AsyncMock]:
    """Set up the integration with a mocked client."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id="test")
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.smartyplants.SmartyPlantsClient", autospec=True
    ) as mock:
        client = mock.return_value
        client.async_get_sensors = AsyncMock(return_value=sensors)
        client.async_get_plants = AsyncMock(return_value=plants or [])
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry, client


async def test_entities_created_with_readings(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A fresh sensor produces readings, connectivity and health entities."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    assert hass.states.get("sensor.monstera_temperature").state == "22.5"
    assert hass.states.get("sensor.monstera_soil_moisture").state == "41"
    assert hass.states.get("sensor.monstera_health_score").state == "82"
    assert hass.states.get("sensor.monstera_fertilise_in").state == "21"
    assert hass.states.get("sensor.monstera_status").state == "ok"


async def test_readings_go_unavailable_when_stale(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Past the three-hour window, readings are withheld but diagnostics stay."""
    freezer.move_to("2026-08-19T14:01:00+00:00")  # 4h 1m after the reading
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    # Measurements are no longer trustworthy.
    assert hass.states.get("sensor.monstera_temperature").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.monstera_soil_moisture").state == STATE_UNAVAILABLE

    # Diagnostics must keep reporting so the user can see why.
    assert hass.states.get("sensor.monstera_status").state == "outdated"
    assert hass.states.get("sensor.monstera_battery").state == "87"


async def test_offline_sensor_hides_readings(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A backend-reported offline sensor also withholds its readings."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    offline = _fresh_sensor("2026-08-19T10:00:00.000Z")
    offline["isOnline"] = False
    await _setup(hass, [offline])

    assert hass.states.get("sensor.monstera_temperature").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.monstera_status").state == "offline"


async def test_new_sensor_appears_without_restart(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A plant added in the app shows up on the next poll."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    first = _fresh_sensor("2026-08-19T10:00:00.000Z")
    _, client = await _setup(hass, [first])

    assert hass.states.get("sensor.fiddle_leaf_fig_temperature") is None

    second = _fresh_sensor("2026-08-19T10:00:00.000Z")
    second["id"] = "sensor-2"
    second["identifier"] = "device-99999"
    second["plant"] = {**second["plant"], "id": "plant-2", "name": "Fiddle Leaf Fig"}
    client.async_get_sensors.return_value = [first, second]

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.fiddle_leaf_fig_temperature").state == "22.5"


async def test_deleted_sensor_removes_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A plant deleted in the app has its device and entities removed."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    entry, client = await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert {(DOMAIN, "sensor-1")} in [d.identifiers for d in devices]

    client.async_get_sensors.return_value = []
    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert dr.async_entries_for_config_entry(device_registry, entry.entry_id) == []
    assert hass.states.get("sensor.monstera_temperature") is None


async def test_webhook_push_updates_state(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A correctly signed push updates entities without waiting for a poll."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])
    assert hass.states.get("sensor.monstera_temperature").state == "22.5"

    payload = {
        "event": "sensor_update",
        "sensor": {
            "id": "sensor-1",
            "identifier": "device-12345",
            "name": "Sensor-device-12345",
            "plantId": "plant-1",
            "plantName": "Monstera",
            "isOnline": True,
            "batteryPercentage": 86,
        },
        "health": {"score": 90, "isHealthy": True, "needsAttentionCount": 0},
        "readings": {
            **deepcopy(SENSOR_FIXTURE["readings"]),
            "temperature": {
                "value": 25.5,
                "unit": "°C",
                "status": "OK",
                "optimalRange": {"low": 18, "high": 26},
                "min": 0,
                "max": 50,
                "isCalculating": False,
            },
        },
        "timestamp": "2026-08-19T10:29:00.000Z",
    }
    body = json.dumps(payload).encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), body, sha256).hexdigest()

    client = await hass_client_no_auth()
    response = await client.post(
        f"/api/webhook/{WEBHOOK_ID}",
        data=body,
        headers={"X-Smartyplants-Signature": signature},
    )

    assert response.status == 200
    await hass.async_block_till_done()
    assert hass.states.get("sensor.monstera_temperature").state == "25.5"
    assert hass.states.get("sensor.monstera_health_score").state == "90"


async def test_webhook_rejects_bad_signature(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An unsigned or wrongly signed push is refused and changes nothing."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    payload = {"event": "sensor_update", "sensor": {"id": "sensor-1"}}
    body = json.dumps(payload).encode()

    client = await hass_client_no_auth()
    response = await client.post(
        f"/api/webhook/{WEBHOOK_ID}",
        data=body,
        headers={"X-Smartyplants-Signature": "not-the-right-signature"},
    )

    assert response.status == 401
    await hass.async_block_till_done()
    assert hass.states.get("sensor.monstera_temperature").state == "22.5"


async def _post_event(client, payload: dict, secret: str = WEBHOOK_SECRET) -> int:
    """Send a signed webhook payload and return the status code."""
    body = json.dumps(payload).encode()
    signature = hmac.new(secret.encode(), body, sha256).hexdigest()
    response = await client.post(
        f"/api/webhook/{WEBHOOK_ID}",
        data=body,
        headers={"X-Smartyplants-Signature": signature},
    )
    return response.status


async def test_webhook_sensor_added_creates_entities(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A sensor_added push creates the new plant without waiting for a poll."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])
    assert hass.states.get("sensor.fiddle_leaf_fig_temperature") is None

    client = await hass_client_no_auth()
    status = await _post_event(
        client,
        {
            "event": "sensor_added",
            "sensor": {
                "id": "sensor-2",
                "identifier": "device-99999",
                "name": "Sensor-device-99999",
                "plantId": "plant-2",
                "plantName": "Fiddle Leaf Fig",
                "isOnline": True,
                "batteryPercentage": 91,
            },
            "health": {"score": 75, "isHealthy": True, "needsAttentionCount": 0},
            "readings": deepcopy(SENSOR_FIXTURE["readings"]),
            "timestamp": "2026-08-19T10:29:00.000Z",
        },
    )

    assert status == 200
    await hass.async_block_till_done()
    assert hass.states.get("sensor.fiddle_leaf_fig_temperature").state == "22.5"
    assert hass.states.get("sensor.fiddle_leaf_fig_health_score").state == "75"


async def test_webhook_sensor_removed_drops_device(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A sensor_removed push deletes the device and its entities at once."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    entry, _ = await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])
    assert hass.states.get("sensor.monstera_temperature") is not None

    client = await hass_client_no_auth()
    status = await _post_event(
        client,
        {
            "event": "sensor_removed",
            "sensor": {"id": "sensor-1"},
            "timestamp": "2026-08-19T10:29:00.000Z",
        },
    )

    assert status == 200
    await hass.async_block_till_done()
    assert dr.async_entries_for_config_entry(device_registry, entry.entry_id) == []
    assert hass.states.get("sensor.monstera_temperature") is None


async def test_unknown_event_is_ignored(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An unrecognised event is accepted and changes nothing.

    The events beyond sensor_update are optional, so a backend that sends
    something this version does not know about must not break it.
    """
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    client = await hass_client_no_auth()
    status = await _post_event(
        client, {"event": "something_new", "sensor": {"id": "sensor-1"}}
    )

    assert status == 200
    await hass.async_block_till_done()
    assert hass.states.get("sensor.monstera_temperature").state == "22.5"


async def test_removal_still_works_without_push_events(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Polling alone reaches the same result when no push events are sent."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    entry, client = await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    client.async_get_sensors.return_value = []
    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert dr.async_entries_for_config_entry(device_registry, entry.entry_id) == []


async def test_device_uses_environment_as_area(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """The plant's environment becomes the Home Assistant area."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    entry, _ = await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])
    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]
    area = area_registry.async_get_area(device.area_id)

    assert device.name == "Monstera"
    assert area.name == "Living Room"


async def test_rename_and_move_are_synced(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Renaming a plant in the app updates the device on the next poll."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    entry, client = await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    renamed = _fresh_sensor("2026-08-19T10:00:00.000Z")
    renamed["plant"] = {**renamed["plant"], "name": "Big Monstera"}
    client.async_get_sensors.return_value = [renamed]

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]
    assert device.name == "Big Monstera"


async def test_user_chosen_area_is_not_overridden(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """An area the user picked survives a change of environment in the app."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    entry, client = await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])
    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    chosen = area_registry.async_get_or_create("Study")
    device_registry.async_update_device(device.id, area_id=chosen.id)

    moved = _fresh_sensor("2026-08-19T10:00:00.000Z")
    moved["plant"] = {**moved["plant"], "environment": "Balcony"}
    client.async_get_sensors.return_value = [moved]

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]
    assert device.area_id == chosen.id


async def test_unassigned_plant_falls_back_to_sensor_name(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Deleting a plant unassigns the sensor; the device keeps working."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    entry, client = await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    unassigned = _fresh_sensor("2026-08-19T10:00:00.000Z")
    unassigned["plant"] = None
    client.async_get_sensors.return_value = [unassigned]

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]
    assert device.name == "Sensor-device-12345"


async def test_plant_without_sensor_asks_for_one(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A sensorless plant appears with no data and a prompt to add a sensor."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [], [PLANT_WITHOUT_SENSOR])

    # The device carries the prompt and nothing else: with no sensor attached
    # there is no measurement to show, so no reading entities are created.
    assert hass.states.get("sensor.new_fern_status").state == "no_sensor"

    assert hass.states.get("sensor.new_fern_temperature") is None
    assert hass.states.get("sensor.new_fern_soil_moisture") is None
    assert hass.states.get("sensor.new_fern_battery") is None


async def test_sensor_without_plant_asks_for_one(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An unassigned sensor reports that a plant still needs adding."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    orphan = _fresh_sensor("2026-08-19T10:00:00.000Z")
    orphan["plant"] = None
    await _setup(hass, [orphan])

    assert hass.states.get("sensor.sensor_device_12345_status").state == "no_plant"
    assert (
        hass.states.get("sensor.sensor_device_12345_temperature").state
        == STATE_UNAVAILABLE
    )

    # The sensor itself is real, so its own diagnostics keep reporting.
    assert hass.states.get("sensor.sensor_device_12345_battery").state == "87"


async def test_status_reports_paired_sensor_as_ok(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A properly paired, fresh sensor reports no outstanding setup."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    assert hass.states.get("sensor.monstera_status").state == "ok"


async def test_status_reports_outdated_readings(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Past the staleness window the status says so, and stays available."""
    freezer.move_to("2026-08-19T14:01:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    assert hass.states.get("sensor.monstera_status").state == "outdated"


async def test_attaching_a_sensor_replaces_the_plant_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Once a sensor is attached, the plant-only placeholder gives way to it."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    entry, client = await _setup(hass, [], [PLANT_WITHOUT_SENSOR])
    assert hass.states.get("sensor.new_fern_status").state == "no_sensor"

    attached = _fresh_sensor("2026-08-19T10:00:00.000Z")
    attached["plant"] = {**attached["plant"], "id": "plant-9", "name": "New Fern"}
    client.async_get_sensors.return_value = [attached]
    client.async_get_plants.return_value = [
        {**PLANT_WITHOUT_SENSOR, "sensor": {"id": "sensor-1"}}
    ]

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert [d.identifiers for d in devices] == [{(DOMAIN, "sensor-1")}]


async def test_repair_raised_for_plant_without_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """An unpaired plant raises a repair that clears once a sensor is added."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    _, client = await _setup(hass, [], [PLANT_WITHOUT_SENSOR])
    issue = issue_registry.async_get_issue(DOMAIN, "no_sensor_plant:plant-9")
    assert issue is not None
    assert issue.translation_key == "plant_without_sensor"
    assert issue.translation_placeholders == {"name": "New Fern"}

    attached = _fresh_sensor("2026-08-19T10:00:00.000Z")
    attached["plant"] = {**attached["plant"], "id": "plant-9", "name": "New Fern"}
    client.async_get_sensors.return_value = [attached]
    client.async_get_plants.return_value = [
        {**PLANT_WITHOUT_SENSOR, "sensor": {"id": "sensor-1"}}
    ]

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, "no_sensor_plant:plant-9") is None


async def test_repair_raised_for_sensor_without_plant(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """An unassigned sensor raises its own repair."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    orphan = _fresh_sensor("2026-08-19T10:00:00.000Z")
    orphan["plant"] = None
    await _setup(hass, [orphan])

    issue = issue_registry.async_get_issue(DOMAIN, "no_plant_sensor-1")
    assert issue is not None
    assert issue.translation_key == "sensor_without_plant"
    assert issue.translation_placeholders == {"name": "Sensor-device-12345"}


async def test_no_repair_when_everything_is_paired(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A healthy account raises nothing."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    assert not [
        issue for issue in issue_registry.issues.values() if issue.domain == DOMAIN
    ]


async def test_connection_failure_marks_entities_unavailable(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A transport failure makes entities unavailable rather than wrong."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    _, client = await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    client.async_get_sensors.side_effect = SmartyPlantsConnectionError("down")
    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.monstera_temperature").state == STATE_UNAVAILABLE


async def test_unload_entry(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Unloading removes the entities and leaves the entry unloaded."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    entry, _ = await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_webhook_rejects_malformed_body(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A correctly signed body that is not JSON is refused."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    body = b"not json at all"
    signature = hmac.new(WEBHOOK_SECRET.encode(), body, sha256).hexdigest()

    client = await hass_client_no_auth()
    response = await client.post(
        f"/api/webhook/{WEBHOOK_ID}",
        data=body,
        headers={"X-Smartyplants-Signature": signature},
    )
    assert response.status == 400


async def test_webhook_rejects_non_object_payload(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Valid JSON that is not an object is refused."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    client = await hass_client_no_auth()
    assert await _post_event(client, ["not", "an", "object"]) == 400


async def test_webhook_rejects_missing_signature(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A push with no signature header at all is refused."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    client = await hass_client_no_auth()
    response = await client.post(f"/api/webhook/{WEBHOOK_ID}", data=b"{}")
    assert response.status == 401


async def test_webhook_without_secret_refuses_pushes(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """With no secret stored, a push cannot be proven genuine, so it is refused."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="nosecret",
        data={k: v for k, v in ENTRY_DATA.items() if k != CONF_WEBHOOK_SECRET},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.smartyplants.SmartyPlantsClient", autospec=True
    ) as mock:
        mock.return_value.async_get_sensors = AsyncMock(
            return_value=[_fresh_sensor("2026-08-19T10:00:00.000Z")]
        )
        mock.return_value.async_get_plants = AsyncMock(return_value=[])
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_client_no_auth()
    response = await client.post(f"/api/webhook/{WEBHOOK_ID}", data=b"{}")
    assert response.status == 401


async def test_webhook_removed_event_for_unknown_sensor_is_ignored(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Removing something we never had changes nothing."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    client = await hass_client_no_auth()
    status = await _post_event(
        client, {"event": "sensor_removed", "sensor": {"id": "does-not-exist"}}
    )

    assert status == 200
    await hass.async_block_till_done()
    assert hass.states.get("sensor.monstera_temperature").state == "22.5"


async def test_webhook_update_without_sensor_id_is_ignored(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A push with no sensor id cannot be applied to anything."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    client = await hass_client_no_auth()
    status = await _post_event(client, {"event": "sensor_update", "sensor": {}})

    assert status == 200
    await hass.async_block_till_done()
    assert hass.states.get("sensor.monstera_temperature").state == "22.5"


async def test_repaired_sensor_gets_entities_back(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A sensor removed and later re-paired is rebuilt, not silently skipped."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    sensor = _fresh_sensor("2026-08-19T10:00:00.000Z")
    _, client = await _setup(hass, [sensor])
    assert hass.states.get("sensor.monstera_temperature") is not None

    client.async_get_sensors.return_value = []
    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.monstera_temperature") is None

    client.async_get_sensors.return_value = [sensor]
    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.monstera_temperature").state == "22.5"


async def test_push_without_timestamp_keeps_readings_fresh(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A push with no timestamp must not blank the one already known."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    client = await hass_client_no_auth()
    status = await _post_event(
        client,
        {
            "event": "sensor_update",
            "sensor": {"id": "sensor-1", "plantId": "plant-1", "plantName": "Monstera"},
            "readings": deepcopy(SENSOR_FIXTURE["readings"]),
        },
    )

    assert status == 200
    await hass.async_block_till_done()
    assert hass.states.get("sensor.monstera_temperature").state == "22.5"
    assert hass.states.get("sensor.monstera_status").state == "ok"


async def test_push_for_unpaired_sensor_does_not_fake_a_plant(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Merging a push must not invent a plant that does not exist."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    orphan = _fresh_sensor("2026-08-19T10:00:00.000Z")
    orphan["plant"] = None
    await _setup(hass, [orphan])
    assert hass.states.get("sensor.sensor_device_12345_status").state == "no_plant"

    client = await hass_client_no_auth()
    status = await _post_event(
        client,
        {
            "event": "sensor_update",
            "sensor": {"id": "sensor-1"},
            "readings": deepcopy(SENSOR_FIXTURE["readings"]),
            "timestamp": "2026-08-19T10:29:00.000Z",
        },
    )

    assert status == 200
    await hass.async_block_till_done()
    assert hass.states.get("sensor.sensor_device_12345_status").state == "no_plant"


async def test_push_with_malformed_readings_is_not_applied(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A push whose readings are the wrong shape must not poison the cache."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    client = await hass_client_no_auth()
    status = await _post_event(
        client,
        {
            "event": "sensor_update",
            "sensor": {"id": "sensor-1", "plantId": "plant-1", "plantName": "Monstera"},
            "readings": "not-a-mapping",
            "health": ["also", "wrong"],
            "timestamp": "2026-08-19T10:29:00.000Z",
        },
    )

    assert status == 200
    await hass.async_block_till_done()
    # The previous good readings survive rather than being replaced by junk.
    assert hass.states.get("sensor.monstera_temperature").state == "22.5"
    assert hass.states.get("sensor.monstera_health_score").state == "82"


async def test_optimal_range_attributes_are_exposed(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Entities whose readings block is named differently still get attributes."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    temperature = hass.states.get("sensor.monstera_temperature")
    assert temperature.attributes["optimal_low"] == 18
    assert temperature.attributes["optimal_high"] == 26

    # These two are backed by lightQuality and fertiliser respectively.
    light_quality = hass.states.get("sensor.monstera_light_quality")
    assert light_quality.attributes["status"] == "OPTIMAL"
    assert light_quality.attributes["optimal_low"] == 40

    assert hass.states.get("sensor.monstera_fertilise_in").attributes["status"] == "OK"


async def test_non_numeric_readings_become_unknown(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A placeholder such as "-" must not crash the sensor platform.

    Home Assistant refuses a non-numeric state on a measurement entity and
    raises when writing it, taking the whole coordinator update down with it.
    """
    freezer.move_to("2026-08-19T10:30:00+00:00")
    sensor = _fresh_sensor("2026-08-19T10:00:00.000Z")
    readings = sensor["readings"]
    readings["lightQuality"] = {**readings["lightQuality"], "value": "-"}
    readings["temperature"] = {**readings["temperature"], "value": "not a number"}
    readings["battery"] = {**readings["battery"], "value": "-"}
    sensor["health"] = {**sensor["health"], "score": "-"}
    sensor["readings"]["fertiliser"] = {
        **readings["fertiliser"],
        "daysUntilFertilise": "-",
    }

    await _setup(hass, [sensor])

    for entity_id in (
        "sensor.monstera_light_quality",
        "sensor.monstera_temperature",
        "sensor.monstera_health_score",
        "sensor.monstera_fertilise_in",
        "sensor.monstera_battery",
    ):
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} was not created"
        assert state.state == STATE_UNKNOWN, f"{entity_id} was {state.state}"


async def test_numeric_strings_are_accepted(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A number sent as a string is still a number."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    sensor = _fresh_sensor("2026-08-19T10:00:00.000Z")
    sensor["readings"]["temperature"] = {
        **sensor["readings"]["temperature"],
        "value": "22.5",
    }
    await _setup(hass, [sensor])

    assert hass.states.get("sensor.monstera_temperature").state == "22.5"


async def test_display_precision_is_registered(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Readings are rounded for display rather than shown at full float width.

    The backend sends values such as 94.57999542229342 for soil moisture, which
    is accurate but unreadable on a card.
    """
    freezer.move_to("2026-08-19T10:30:00+00:00")
    sensor = _fresh_sensor("2026-08-19T10:00:00.000Z")
    sensor["readings"]["moisture"] = {
        **sensor["readings"]["moisture"],
        "value": 94.57999542229342,
    }
    await _setup(hass, [sensor])
    entry = entity_registry.async_get("sensor.monstera_soil_moisture")
    assert entry is not None
    assert entry.options["sensor"]["suggested_display_precision"] == 0

    # The stored state keeps the underlying value, so history and automations
    # are unaffected by the rounding shown on a card.
    state = hass.states.get("sensor.monstera_soil_moisture")
    assert float(state.state) == pytest.approx(94.57999542229342)


async def test_push_without_online_flag_keeps_cached_state(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A partial push must not silently bring an offline sensor back online.

    Every other omitted field keeps its previous value, so defaulting this one
    to online would expose cached readings for a sensor that is not reporting.
    """
    freezer.move_to("2026-08-19T10:30:00+00:00")
    offline = _fresh_sensor("2026-08-19T10:00:00.000Z")
    offline["isOnline"] = False
    await _setup(hass, [offline])
    assert hass.states.get("sensor.monstera_status").state == "offline"

    client = await hass_client_no_auth()
    status = await _post_event(
        client,
        {
            "event": "sensor_update",
            "sensor": {"id": "sensor-1", "plantId": "plant-1", "plantName": "Monstera"},
            "readings": deepcopy(SENSOR_FIXTURE["readings"]),
            "timestamp": "2026-08-19T10:29:00.000Z",
        },
    )

    assert status == 200
    await hass.async_block_till_done()
    assert hass.states.get("sensor.monstera_status").state == "offline"
    assert hass.states.get("sensor.monstera_temperature").state == STATE_UNAVAILABLE


async def test_webhook_rejects_malformed_event_and_sensor(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Signed payloads of the wrong shape are refused rather than raising."""
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])
    client = await hass_client_no_auth()

    # An unhashable event would raise on the set membership test.
    assert await _post_event(client, {"event": [], "sensor": {"id": "sensor-1"}}) == 400
    # A string sensor has no .get().
    assert (
        await _post_event(client, {"event": "sensor_update", "sensor": "nope"}) == 400
    )
    # An unhashable id would raise when used as a dictionary key.
    assert (
        await _post_event(client, {"event": "sensor_update", "sensor": {"id": []}})
        == 400
    )
    assert (
        await _post_event(client, {"event": "sensor_removed", "sensor": {"id": {}}})
        == 400
    )

    await hass.async_block_till_done()
    assert hass.states.get("sensor.monstera_temperature").state == "22.5"


async def test_non_string_timestamp_is_treated_as_missing(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A pushed timestamp of the wrong type must not raise on entity updates.

    The value is cached as it arrives, so anything that is not a string or a
    datetime would reach .tzinfo and fail while writing state.
    """
    freezer.move_to("2026-08-19T10:30:00+00:00")
    await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])

    client = await hass_client_no_auth()
    status = await _post_event(
        client,
        {
            "event": "sensor_update",
            "sensor": {"id": "sensor-1", "plantId": "plant-1", "plantName": "Monstera"},
            "readings": deepcopy(SENSOR_FIXTURE["readings"]),
            "timestamp": 1234567890,
        },
    )

    assert status == 200
    await hass.async_block_till_done()
    # Treated as no timestamp at all, so the readings read as outdated rather
    # than bringing the whole update down.
    assert hass.states.get("sensor.monstera_status").state == "outdated"


async def test_poll_in_flight_does_not_revert_a_push(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A push that lands mid-poll survives the poll completing.

    The poll fetched its snapshot before the push arrived, so assigning it
    afterwards would roll the pushed reading back until the next poll.
    """
    freezer.move_to("2026-08-19T10:30:00+00:00")
    _, client = await _setup(hass, [_fresh_sensor("2026-08-19T10:00:00.000Z")])
    assert hass.states.get("sensor.monstera_temperature").state == "22.5"

    pushed = asyncio.Event()

    async def _slow_fetch() -> list[dict]:
        # Let the push land while this poll is still awaiting its response.
        await pushed.wait()
        return [_fresh_sensor("2026-08-19T10:00:00.000Z")]

    client.async_get_sensors.side_effect = _slow_fetch

    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await asyncio.sleep(0)

    webhook_client = await hass_client_no_auth()
    readings = deepcopy(SENSOR_FIXTURE["readings"])
    readings["temperature"] = {**readings["temperature"], "value": 30.5}
    assert (
        await _post_event(
            webhook_client,
            {
                "event": "sensor_update",
                "sensor": {
                    "id": "sensor-1",
                    "plantId": "plant-1",
                    "plantName": "Monstera",
                },
                "readings": readings,
                "timestamp": "2026-08-19T10:29:00.000Z",
            },
        )
        == 200
    )
    pushed.set()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.monstera_temperature").state == "30.5"
