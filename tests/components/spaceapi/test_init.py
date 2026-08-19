"""The tests for the Home Assistant SpaceAPI component."""

from http import HTTPStatus

from aiohttp.test_utils import TestClient
import pytest

from homeassistant.components.spaceapi import SPACEAPI_COMPATIBILITY, URL_API_SPACEAPI
from homeassistant.components.spaceapi.const import ATTR_API_SENSOR_LOCATION
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, PERCENTAGE, UnitOfTemperature
from homeassistant.core import Context, HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

SENSOR_OUTPUT = {
    "temperature": [
        {
            "name": "temp1",
            "unit": UnitOfTemperature.CELSIUS,
            "value": 25.0,
        },
        {
            "location": "outside",
            "name": "temp2",
            "unit": UnitOfTemperature.CELSIUS,
            "value": 23.0,
        },
        # temp3 has state "foo" (non-numeric) — skipped rather than emitting invalid data
    ],
    "humidity": [{"name": "hum1", "unit": PERCENTAGE, "value": 88.0}],
}


@pytest.fixture
async def mock_client(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> TestClient:
    """Start the Home Assistant HTTP component."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        "test.temp1",
        25,
        attributes={ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    hass.states.async_set(
        "test.temp2",
        23,
        attributes={
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            ATTR_API_SENSOR_LOCATION: "outside",
        },
    )
    hass.states.async_set(
        "test.temp3",
        "foo",
        attributes={ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    hass.states.async_set(
        "test.hum1", 88, attributes={ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE}
    )

    return await hass_client()


async def test_spaceapi_get(hass: HomeAssistant, mock_client: TestClient) -> None:
    """Test response after start-up Home Assistant."""
    resp = await mock_client.get(URL_API_SPACEAPI)
    assert resp.status == HTTPStatus.OK

    data = await resp.json()

    assert data["api_compatibility"] == SPACEAPI_COMPATIBILITY
    assert data["space"] == "Home"
    assert data["contact"]["email"] == "hello@home-assistant.io"
    assert data["location"]["lat"] == 32.87336
    assert data["location"]["lon"] == -117.22743
    assert data["state"]["open"] is False
    assert data["state"]["icon"]["open"] == "https://home-assistant.io/open.png"
    assert data["state"]["icon"]["closed"] == "https://home-assistant.io/close.png"
    assert data["spacefed"]["spacenet"] is True
    assert data["spacefed"]["spacesaml"] is False
    assert "spacephone" not in data["spacefed"]
    assert data["cam"][0] == "https://home-assistant.io/cam1"
    assert data["cam"][1] == "https://home-assistant.io/cam2"
    assert "stream" not in data
    assert data["feeds"]["blog"]["url"] == "https://home-assistant.io/blog"
    assert data["feeds"]["wiki"]["type"] == "rss"
    assert data["feeds"]["wiki"]["url"] == "https://home-assistant.io/wiki"
    assert data["feeds"]["calendar"]["type"] == "ical"
    assert data["feeds"]["calendar"]["url"] == "https://home-assistant.io/calendar"
    assert (
        data["feeds"]["flickr"]["url"] == "https://www.flickr.com/photos/home-assistant"
    )
    assert "cache" not in data
    assert data["projects"][0] == "https://home-assistant.io/projects/1"
    assert data["projects"][1] == "https://home-assistant.io/projects/2"
    assert data["projects"][2] == "https://home-assistant.io/projects/3"
    assert "radio_show" not in data
    assert "issue_report_channels" not in data


async def test_spaceapi_state_get(hass: HomeAssistant, mock_client: TestClient) -> None:
    """Test response if the state entity was set."""
    hass.states.async_set("test.test_door", "on")

    resp = await mock_client.get(URL_API_SPACEAPI)
    assert resp.status == HTTPStatus.OK

    data = await resp.json()
    assert data["state"]["open"] is True


async def test_spaceapi_sensors_get(
    hass: HomeAssistant, mock_client: TestClient
) -> None:
    """Test the response for the sensors."""
    resp = await mock_client.get(URL_API_SPACEAPI)
    assert resp.status == HTTPStatus.OK

    data = await resp.json()
    sensors = data["sensors"]

    for entries in sensors.values():
        for entry in entries:
            assert isinstance(entry["lastchange"], int)

    # Strip lastchange for static comparison
    stripped = {
        sensor_type: [
            {k: v for k, v in e.items() if k != "lastchange"} for e in entries
        ]
        for sensor_type, entries in sensors.items()
    }
    assert stripped == SENSOR_OUTPUT


async def test_spaceapi_no_auth_required(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test SpaceAPI is accessible without authentication."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client_no_auth()
    resp = await client.get(URL_API_SPACEAPI)
    assert resp.status == HTTPStatus.OK

    data = await resp.json()
    assert data["space"] == "Home"


async def test_spaceapi_cors_headers(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test CORS headers are present on SpaceAPI responses."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client_no_auth()
    resp = await client.options(
        URL_API_SPACEAPI,
        headers={
            "origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers["Access-Control-Allow-Origin"] == "http://example.com"
    assert "GET" in resp.headers["Access-Control-Allow-Methods"]


async def test_spaceapi_door_locked_boolean(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test door_locked sensor emits a boolean value."""
    new_options = dict(mock_config_entry.options)
    new_options["sensors"] = {"door_locked": ["test.door1", "test.door2"]}
    hass.config_entries.async_update_entry(mock_config_entry, options=new_options)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("test.door1", "locked")
    hass.states.async_set("test.door2", "on")

    client = await hass_client()
    resp = await client.get(URL_API_SPACEAPI)
    data = await resp.json()

    door_sensors = data["sensors"]["door_locked"]
    assert door_sensors[0]["value"] is True
    assert door_sensors[1]["value"] is True
    assert "unit" not in door_sensors[0]


async def test_spaceapi_sensor_non_numeric_skipped(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that sensors with non-numeric states are silently skipped."""
    new_options = dict(mock_config_entry.options)
    new_options["sensors"] = {"temperature": ["test.temp_bad"]}
    hass.config_entries.async_update_entry(mock_config_entry, options=new_options)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("test.temp_bad", "unavailable")

    client = await hass_client()
    resp = await client.get(URL_API_SPACEAPI)
    data = await resp.json()

    # The only configured sensor type resolves to nothing, so it is omitted
    # entirely rather than emitting an empty array.
    assert "sensors" not in data


async def test_spaceapi_sensor_default_unit(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a sensor without unit_of_measurement gets the default unit."""

    new_options = dict(mock_config_entry.options)
    new_options["sensors"] = {"temperature": ["test.temp_no_unit"]}
    hass.config_entries.async_update_entry(mock_config_entry, options=new_options)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("test.temp_no_unit", 22)

    client = await hass_client()
    resp = await client.get(URL_API_SPACEAPI)
    data = await resp.json()

    temp_sensors = data["sensors"]["temperature"]
    assert len(temp_sensors) == 1
    assert temp_sensors[0]["value"] == 22.0
    assert temp_sensors[0]["unit"] == "°C"


async def test_spaceapi_state_lock_entity(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a lock entity maps locked→closed, unlocked→open."""
    new_options = dict(mock_config_entry.options)
    hass.config_entries.async_update_entry(mock_config_entry, options=new_options)
    new_data = dict(mock_config_entry.data)
    new_data["state"] = {"entity_id": "lock.front_door"}
    hass.config_entries.async_update_entry(mock_config_entry, data=new_data)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client()

    hass.states.async_set("lock.front_door", "locked")
    resp = await client.get(URL_API_SPACEAPI)
    data = await resp.json()
    assert data["state"]["open"] is False

    hass.states.async_set("lock.front_door", "unlocked")
    resp = await client.get(URL_API_SPACEAPI)
    data = await resp.json()
    assert data["state"]["open"] is True


async def test_spaceapi_state_cover_entity(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a cover entity maps open→open, closed→closed."""
    new_data = dict(mock_config_entry.data)
    new_data["state"] = {"entity_id": "cover.garage"}
    hass.config_entries.async_update_entry(mock_config_entry, data=new_data)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client()

    hass.states.async_set("cover.garage", "open")
    resp = await client.get(URL_API_SPACEAPI)
    data = await resp.json()
    assert data["state"]["open"] is True

    hass.states.async_set("cover.garage", "closed")
    resp = await client.get(URL_API_SPACEAPI)
    data = await resp.json()
    assert data["state"]["open"] is False


async def test_spaceapi_location_extras(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that timezone, country_code and hint appear in the location block."""
    new_options = dict(mock_config_entry.options)
    new_options["location"] = {
        "address": "Testgasse 1",
        "timezone": "Europe/Vienna",
        "country_code": "AT",
        "hint": "Ring the bell",
    }
    hass.config_entries.async_update_entry(mock_config_entry, options=new_options)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client()
    resp = await client.get(URL_API_SPACEAPI)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    loc = data["location"]
    assert loc["address"] == "Testgasse 1"
    assert loc["timezone"] == "Europe/Vienna"
    assert loc["country_code"] == "AT"
    assert loc["hint"] == "Ring the bell"


async def test_spaceapi_state_message_entity(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the state message entity's state appears in the output."""
    new_options = dict(mock_config_entry.options)
    new_options["state"] = {
        **new_options.get("state", {}),
        "message": "input_text.status_msg",
    }
    hass.config_entries.async_update_entry(mock_config_entry, options=new_options)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("input_text.status_msg", "Open for business!")

    client = await hass_client()
    resp = await client.get(URL_API_SPACEAPI)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["state"]["message"] == "Open for business!"


async def test_spaceapi_sensor_no_unit_field_when_type_has_no_default(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor types without a default unit omit the unit field rather than being skipped."""
    new_options = dict(mock_config_entry.options)
    new_options["sensors"] = {"people_now_present": ["test.headcount"]}
    hass.config_entries.async_update_entry(mock_config_entry, options=new_options)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # people_now_present is not in SENSOR_DEFAULT_UNITS and has no unit attribute
    hass.states.async_set("test.headcount", 5)

    client = await hass_client()
    resp = await client.get(URL_API_SPACEAPI)
    data = await resp.json()

    sensors = data["sensors"]["people_now_present"]
    assert len(sensors) == 1
    assert sensors[0]["value"] == 5.0
    assert "unit" not in sensors[0]


async def test_spaceapi_entry_not_found_returns_404(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the endpoint returns 404 when the config entry is removed."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Remove the entry so the view can no longer find it
    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client_no_auth()
    resp = await client.get(URL_API_SPACEAPI)
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_spaceapi_state_trigger_person(
    hass: HomeAssistant,
    mock_client: TestClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test trigger_person is set when the space-state context matches a person entity."""
    # Register a person whose user_id matches the context we will set
    hass.states.async_set(
        "person.alice",
        "home",
        attributes={"user_id": "test-user-abc", "friendly_name": "Alice"},
    )

    context = Context(user_id="test-user-abc")
    hass.states.async_set("test.test_door", "on", context=context)

    resp = await mock_client.get(URL_API_SPACEAPI)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["state"]["trigger_person"] == "Alice"


async def test_spaceapi_state_trigger_person_absent_when_no_context(
    hass: HomeAssistant,
    mock_client: TestClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test trigger_person is absent when the space-state context has no user_id."""
    hass.states.async_set("test.test_door", "on")

    resp = await mock_client.get(URL_API_SPACEAPI)
    data = await resp.json()

    assert "trigger_person" not in data["state"]


async def test_options_contact_email_from_options(
    hass: HomeAssistant,
    mock_client: TestClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Contact email is sourced from options; clearing options removes it from output."""
    resp = await mock_client.get(URL_API_SPACEAPI)
    data = await resp.json()
    assert data["contact"]["email"] == "hello@home-assistant.io"

    # Remove contact from options entirely — email must disappear from output
    new_options = {k: v for k, v in mock_config_entry.options.items() if k != "contact"}
    hass.config_entries.async_update_entry(mock_config_entry, options=new_options)
    await hass.async_block_till_done()

    resp = await mock_client.get(URL_API_SPACEAPI)
    data = await resp.json()
    assert "contact" not in data or "email" not in data.get("contact", {})


async def test_spaceapi_state_icon_partial(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a partial icon config (only one side set) emits only that key."""
    new_options = dict(mock_config_entry.options)
    new_options["state"] = {"icon_open": "https://example.com/open.png"}
    hass.config_entries.async_update_entry(mock_config_entry, options=new_options)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("test.test_door", "on")
    client = await hass_client()
    resp = await client.get(URL_API_SPACEAPI)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    icon = data["state"]["icon"]
    assert icon == {"open": "https://example.com/open.png"}
    assert "closed" not in icon


async def test_spaceapi_state_message_entity_missing(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a missing message entity silently omits the message field."""
    new_options = dict(mock_config_entry.options)
    new_options["state"] = {
        **new_options.get("state", {}),
        "message": "input_text.nonexistent",
    }
    hass.config_entries.async_update_entry(mock_config_entry, options=new_options)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client()
    resp = await client.get(URL_API_SPACEAPI)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert "message" not in data["state"]


async def test_spaceapi_merge_config_semantics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _merge_config: options dicts are shallow-merged with data dicts."""
    # state is in data (entity_id) and also in options (icon_open/icon_closed).
    # After merge, state should contain all three keys.
    new_options = dict(mock_config_entry.options)
    new_options["state"] = {
        "icon_open": "https://example.com/open.png",
        "icon_closed": "https://example.com/closed.png",
    }
    hass.config_entries.async_update_entry(mock_config_entry, options=new_options)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("test.test_door", "on")
    client = await hass_client()
    resp = await client.get(URL_API_SPACEAPI)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    # entity_id from data and icons from options both present in merged output
    assert data["state"]["open"] is True
    assert data["state"]["icon"]["open"] == "https://example.com/open.png"
    assert data["state"]["icon"]["closed"] == "https://example.com/closed.png"
