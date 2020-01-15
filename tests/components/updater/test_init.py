"""The tests for the Updater component."""
import asyncio
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest

from homeassistant.components import updater
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    MockDependency,
    async_fire_time_changed,
    mock_component,
    mock_coro,
)

NEW_VERSION = "10000.0"
MOCK_VERSION = "10.0"
MOCK_DEV_VERSION = "10.0.dev0"
MOCK_HUUID = "abcdefg"
MOCK_RESPONSE = {"version": "0.15", "release-notes": "https://home-assistant.io"}
MOCK_CONFIG = {updater.DOMAIN: {"reporting": True}}
RELEASE_NOTES = "test release notes"


@pytest.fixture(autouse=True)
def mock_distro():
    """Mock distro dep."""
    with MockDependency("distro"):
        yield


@pytest.fixture(name="mock_get_newest_version")
def mock_get_newest_version_fixture():
    """Fixture to mock get_newest_version."""
    with patch("homeassistant.components.updater.get_newest_version") as mock:
        yield mock


@pytest.fixture(name="mock_get_uuid")
def mock_get_uuid_fixture():
    """Fixture to mock get_uuid."""
    with patch("homeassistant.components.updater._load_uuid") as mock:
        yield mock


@pytest.fixture(name="mock_utcnow")
def mock_utcnow_fixture():
    """Fixture to mock utcnow."""
    with patch("homeassistant.components.updater.dt_util") as mock:
        yield mock.utcnow


async def test_new_version_shows_entity_startup(
    hass, mock_get_uuid, mock_get_newest_version
):
    """Test if binary sensor is unavailable at first."""
    mock_get_uuid.return_value = MOCK_HUUID
    mock_get_newest_version.return_value = mock_coro((NEW_VERSION, RELEASE_NOTES))

    res = await async_setup_component(hass, updater.DOMAIN, {updater.DOMAIN: {}})
    assert res, "Updater failed to set up"

    await hass.async_block_till_done()
    assert hass.states.is_state("binary_sensor.updater", "unavailable")
    assert "newest_version" not in hass.states.get("binary_sensor.updater").attributes
    assert "release_notes" not in hass.states.get("binary_sensor.updater").attributes


async def test_rename_entity(hass, mock_get_uuid, mock_get_newest_version, mock_utcnow):
    """Test if renaming the binary sensor works correctly."""
    mock_get_uuid.return_value = MOCK_HUUID
    mock_get_newest_version.return_value = mock_coro((NEW_VERSION, RELEASE_NOTES))

    now = dt_util.utcnow()
    later = now + timedelta(hours=1)
    mock_utcnow.return_value = now

    res = await async_setup_component(hass, updater.DOMAIN, {updater.DOMAIN: {}})
    assert res, "Updater failed to set up"

    await hass.async_block_till_done()
    assert hass.states.is_state("binary_sensor.updater", "unavailable")
    assert hass.states.get("binary_sensor.new_entity_id") is None

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    entity_registry.async_update_entity(
        "binary_sensor.updater", new_entity_id="binary_sensor.new_entity_id"
    )

    await hass.async_block_till_done()
    assert hass.states.is_state("binary_sensor.new_entity_id", "unavailable")
    assert hass.states.get("binary_sensor.updater") is None

    with patch("homeassistant.components.updater.current_version", MOCK_VERSION):
        async_fire_time_changed(hass, later)
        await hass.async_block_till_done()

    assert hass.states.is_state("binary_sensor.new_entity_id", "on")
    assert hass.states.get("binary_sensor.updater") is None


async def test_new_version_shows_entity_true(
    hass, mock_get_uuid, mock_get_newest_version, mock_utcnow
):
    """Test if sensor is true if new version is available."""
    mock_get_uuid.return_value = MOCK_HUUID
    mock_get_newest_version.return_value = mock_coro((NEW_VERSION, RELEASE_NOTES))

    now = dt_util.utcnow()
    later = now + timedelta(hours=1)
    mock_utcnow.return_value = now

    res = await async_setup_component(hass, updater.DOMAIN, {updater.DOMAIN: {}})
    assert res, "Updater failed to set up"

    await hass.async_block_till_done()
    with patch("homeassistant.components.updater.current_version", MOCK_VERSION):
        async_fire_time_changed(hass, later)
        await hass.async_block_till_done()

    assert hass.states.is_state("binary_sensor.updater", "on")
    assert (
        hass.states.get("binary_sensor.updater").attributes["newest_version"]
        == NEW_VERSION
    )
    assert (
        hass.states.get("binary_sensor.updater").attributes["release_notes"]
        == RELEASE_NOTES
    )


async def test_same_version_shows_entity_false(
    hass, mock_get_uuid, mock_get_newest_version, mock_utcnow
):
    """Test if sensor is false if no new version is available."""
    mock_get_uuid.return_value = MOCK_HUUID
    mock_get_newest_version.return_value = mock_coro((MOCK_VERSION, ""))

    now = dt_util.utcnow()
    later = now + timedelta(hours=1)
    mock_utcnow.return_value = now

    res = await async_setup_component(hass, updater.DOMAIN, {updater.DOMAIN: {}})
    assert res, "Updater failed to set up"

    await hass.async_block_till_done()
    with patch("homeassistant.components.updater.current_version", MOCK_VERSION):
        async_fire_time_changed(hass, later)
        await hass.async_block_till_done()

    assert hass.states.is_state("binary_sensor.updater", "off")
    assert (
        hass.states.get("binary_sensor.updater").attributes["newest_version"]
        == MOCK_VERSION
    )
    assert "release_notes" not in hass.states.get("binary_sensor.updater").attributes


async def test_disable_reporting(
    hass, mock_get_uuid, mock_get_newest_version, mock_utcnow
):
    """Test we do not gather analytics when disable reporting is active."""
    mock_get_uuid.return_value = MOCK_HUUID
    mock_get_newest_version.return_value = mock_coro((MOCK_VERSION, ""))

    now = dt_util.utcnow()
    later = now + timedelta(hours=1)
    mock_utcnow.return_value = now

    res = await async_setup_component(
        hass, updater.DOMAIN, {updater.DOMAIN: {"reporting": False}}
    )
    assert res, "Updater failed to set up"

    await hass.async_block_till_done()
    with patch("homeassistant.components.updater.current_version", MOCK_VERSION):
        async_fire_time_changed(hass, later)
        await hass.async_block_till_done()

    assert hass.states.is_state("binary_sensor.updater", "off")
    res = await updater.get_newest_version(hass, MOCK_HUUID, MOCK_CONFIG)
    call = mock_get_newest_version.mock_calls[0][1]
    assert call[0] is hass
    assert call[1] is None


async def test_get_newest_version_no_analytics_when_no_huuid(hass, aioclient_mock):
    """Test we do not gather analytics when no huuid is passed in."""
    aioclient_mock.post(updater.UPDATER_URL, json=MOCK_RESPONSE)

    with patch(
        "homeassistant.helpers.system_info.async_get_system_info", side_effect=Exception
    ):
        res = await updater.get_newest_version(hass, None, False)
        assert res == (MOCK_RESPONSE["version"], MOCK_RESPONSE["release-notes"])


async def test_get_newest_version_analytics_when_huuid(hass, aioclient_mock):
    """Test we gather analytics when huuid is passed in."""
    aioclient_mock.post(updater.UPDATER_URL, json=MOCK_RESPONSE)

    with patch(
        "homeassistant.helpers.system_info.async_get_system_info",
        Mock(return_value=mock_coro({"fake": "bla"})),
    ):
        res = await updater.get_newest_version(hass, MOCK_HUUID, False)
        assert res == (MOCK_RESPONSE["version"], MOCK_RESPONSE["release-notes"])


async def test_error_fetching_new_version_timeout(hass):
    """Test we handle timeout error while fetching new version."""
    with patch(
        "homeassistant.helpers.system_info.async_get_system_info",
        Mock(return_value=mock_coro({"fake": "bla"})),
    ), patch("async_timeout.timeout", side_effect=asyncio.TimeoutError):
        res = await updater.get_newest_version(hass, MOCK_HUUID, False)
        assert res is None


async def test_error_fetching_new_version_bad_json(hass, aioclient_mock):
    """Test we handle json error while fetching new version."""
    aioclient_mock.post(updater.UPDATER_URL, text="not json")

    with patch(
        "homeassistant.helpers.system_info.async_get_system_info",
        Mock(return_value=mock_coro({"fake": "bla"})),
    ):
        res = await updater.get_newest_version(hass, MOCK_HUUID, False)
        assert res is None


async def test_error_fetching_new_version_invalid_response(hass, aioclient_mock):
    """Test we handle response error while fetching new version."""
    aioclient_mock.post(
        updater.UPDATER_URL,
        json={
            "version": "0.15"
            # 'release-notes' is missing
        },
    )

    with patch(
        "homeassistant.helpers.system_info.async_get_system_info",
        Mock(return_value=mock_coro({"fake": "bla"})),
    ):
        res = await updater.get_newest_version(hass, MOCK_HUUID, False)
        assert res is None


async def test_new_version_shows_entity_after_hour_hassio(
    hass, mock_get_uuid, mock_get_newest_version, mock_utcnow
):
    """Test if binary sensor gets updated if new version is available / Hass.io."""
    mock_get_uuid.return_value = MOCK_HUUID
    mock_get_newest_version.return_value = mock_coro((NEW_VERSION, RELEASE_NOTES))
    mock_component(hass, "hassio")
    hass.data["hassio_hass_version"] = "999.0"

    now = dt_util.utcnow()
    later = now + timedelta(hours=1)
    mock_utcnow.return_value = now

    res = await async_setup_component(hass, updater.DOMAIN, {updater.DOMAIN: {}})
    assert res, "Updater failed to set up"

    await hass.async_block_till_done()
    with patch("homeassistant.components.updater.current_version", MOCK_VERSION):
        async_fire_time_changed(hass, later)
        await hass.async_block_till_done()

    assert hass.states.is_state("binary_sensor.updater", "on")
    assert (
        hass.states.get("binary_sensor.updater").attributes["newest_version"] == "999.0"
    )
    assert (
        hass.states.get("binary_sensor.updater").attributes["release_notes"]
        == RELEASE_NOTES
    )
