"""Tests for SmartyPlants webhook pushes."""

import asyncio
from copy import deepcopy
from hashlib import sha256
import hmac
import json
from typing import Any
from unittest.mock import AsyncMock

from pysmartyplants import Sensor, SensorUpdate
import pytest

from homeassistant.components.smartyplants.const import CONF_WEBHOOK_SECRET, DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import WEBHOOK_ID, WEBHOOK_SECRET

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

MOISTURE = "sensor.monstera_soil_moisture"
TEMPERATURE = "sensor.monstera_temperature"


def _push(**changes: Any) -> dict[str, Any]:
    """Build a sensor_update push carrying only what it changes."""
    return {"event": "sensor_update", "sensor": {"id": "sensor-1"}, **changes}


def _moisture_push(
    sensor_payloads: list[dict[str, Any]], value: float
) -> dict[str, Any]:
    """Build a push reporting a new soil moisture reading."""
    readings = deepcopy(sensor_payloads[0]["readings"])
    readings["moisture"]["value"] = value
    return _push(readings=readings)


async def _post(
    hass_client_no_auth: ClientSessionGenerator,
    body: bytes,
    signature: str | None,
) -> int:
    """Post a raw webhook body and return the status code."""
    client = await hass_client_no_auth()
    headers = {} if signature is None else {"X-Smartyplants-Signature": signature}
    response = await client.post(
        f"/api/webhook/{WEBHOOK_ID}", data=body, headers=headers
    )
    return response.status


async def _post_signed(
    hass_client_no_auth: ClientSessionGenerator, payload: Any
) -> int:
    """Post a payload signed with the configured secret."""
    body = json.dumps(payload).encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), body, sha256).hexdigest()
    return await _post(hass_client_no_auth, body, signature)


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_push_updates_readings(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    sensor_payloads: list[dict[str, Any]],
) -> None:
    """Test a push is applied at once and keeps what it left out."""
    await setup_integration(hass, mock_config_entry)

    assert (
        await _post_signed(hass_client_no_auth, _moisture_push(sensor_payloads, 55))
        == 200
    )
    await hass.async_block_till_done()

    assert hass.states.get(MOISTURE).state == "55"
    # The push carried no battery or health, so the polled values survive.
    assert hass.states.get("sensor.monstera_battery").state == "87"
    assert hass.states.get("sensor.monstera_health_score").state == "82"


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_push_takes_sensor_offline(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an explicit offline flag in a push is applied."""
    await setup_integration(hass, mock_config_entry)

    payload = _push()
    payload["sensor"]["isOnline"] = False
    assert await _post_signed(hass_client_no_auth, payload) == 200
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            {"event": "sensor_update", "sensor": {"id": "sensor-unknown"}},
            id="unknown_sensor",
        ),
        pytest.param(
            {"event": "something_new", "sensor": {"id": "sensor-1"}},
            id="unknown_event",
        ),
    ],
)
@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_push_ignored(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    payload: dict[str, Any],
) -> None:
    """Test a push that names nothing we track is accepted and changes nothing."""
    await setup_integration(hass, mock_config_entry)

    assert await _post_signed(hass_client_no_auth, payload) == 200
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE).state == "22.5"


@pytest.mark.parametrize(
    "signature",
    [pytest.param(None, id="unsigned"), pytest.param("deadbeef", id="forged")],
)
@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_push_signature_refused(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    signature: str | None,
) -> None:
    """Test a push without a valid signature is refused."""
    await setup_integration(hass, mock_config_entry)

    body = json.dumps(_push()).encode()
    assert await _post(hass_client_no_auth, body, signature) == 401


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_push_refused_without_secret(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pushes are refused when no secret was configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            key: value
            for key, value in mock_config_entry.data.items()
            if key != CONF_WEBHOOK_SECRET
        },
        unique_id=mock_config_entry.unique_id,
    )
    await setup_integration(hass, entry)

    assert await _post_signed(hass_client_no_auth, _push()) == 401


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("just a string", id="string"),
        pytest.param([1, 2, 3], id="list"),
        pytest.param({"sensor": {"id": "sensor-1"}}, id="no_event"),
        pytest.param({"event": 42, "sensor": {"id": "sensor-1"}}, id="event_number"),
        pytest.param(
            {"event": ["sensor_update"], "sensor": {"id": "sensor-1"}}, id="event_list"
        ),
        pytest.param({"event": "sensor_update", "sensor": "sensor-1"}, id="sensor_str"),
        pytest.param({"event": "sensor_update", "sensor": {"id": 42}}, id="id_number"),
        pytest.param(
            {"event": "sensor_update", "sensor": {"id": ["sensor-1"]}}, id="id_list"
        ),
        pytest.param({"event": "sensor_update", "sensor": {}}, id="no_id"),
    ],
)
@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_malformed_payload_refused(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    payload: Any,
) -> None:
    """Test a malformed payload is refused before anything reads it."""
    await setup_integration(hass, mock_config_entry)

    assert await _post_signed(hass_client_no_auth, payload) == 400
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE).state == "22.5"


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_non_json_body_refused(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a signed body that is not JSON is refused."""
    await setup_integration(hass, mock_config_entry)

    body = b"not json"
    signature = hmac.new(WEBHOOK_SECRET.encode(), body, sha256).hexdigest()
    assert await _post(hass_client_no_auth, body, signature) == 400


@pytest.mark.parametrize(
    "timestamp",
    [
        pytest.param(123, id="number"),
        pytest.param(["2026-08-19"], id="list"),
        pytest.param({"at": "2026-08-19"}, id="object"),
    ],
)
@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_wrongly_typed_timestamp_ignored(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    sensor_payloads: list[dict[str, Any]],
    timestamp: Any,
) -> None:
    """Test a wrongly typed timestamp does not stop the readings being applied."""
    await setup_integration(hass, mock_config_entry)

    payload = _moisture_push(sensor_payloads, 55)
    payload["timestamp"] = timestamp
    assert await _post_signed(hass_client_no_auth, payload) == 200
    await hass.async_block_till_done()

    assert hass.states.get(MOISTURE).state == "55"


async def test_push_during_poll_not_reverted(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smartyplants_client: AsyncMock,
    sensor_payloads: list[dict[str, Any]],
) -> None:
    """Test a push that lands mid-poll survives the poll's older response."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    polled = mock_smartyplants_client.async_get_sensors.side_effect
    started = asyncio.Event()
    release = asyncio.Event()

    async def _slow_poll() -> list[Sensor]:
        started.set()
        await release.wait()
        return polled()

    mock_smartyplants_client.async_get_sensors.side_effect = _slow_poll
    poll = hass.async_create_task(coordinator.async_refresh())
    await started.wait()

    update = SensorUpdate.from_api(_moisture_push(sensor_payloads, 55))
    assert update is not None
    push = hass.async_create_task(coordinator.async_apply_update(update))
    await asyncio.sleep(0)

    release.set()
    await poll
    await push
    await hass.async_block_till_done()

    # The poll still reports 41; only serializing the two keeps the pushed 55.
    assert hass.states.get(MOISTURE).state == "55"
