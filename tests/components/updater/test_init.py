"""The tests for the Updater component."""
from unittest.mock import patch

import pytest

from homeassistant.components import updater
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.setup import async_setup_component

from tests.common import mock_component

NEW_VERSION = "10000.0"
MOCK_VERSION = "10.0"
MOCK_DEV_VERSION = "10.0.dev0"
MOCK_HUUID = "abcdefg"
MOCK_RESPONSE = {"version": "0.15", "release-notes": "https://home-assistant.io"}
MOCK_CONFIG = {updater.DOMAIN: {"reporting": True}}
RELEASE_NOTES = "test release notes"


@pytest.fixture(autouse=True)
def mock_version():
    """Mock current version."""
    with patch("homeassistant.components.updater.current_version", MOCK_VERSION):
        yield


@pytest.fixture(name="mock_get_newest_version")
def mock_get_newest_version_fixture():
    """Fixture to mock get_newest_version."""
    with patch(
        "homeassistant.components.updater.get_newest_version",
        return_value=(NEW_VERSION, RELEASE_NOTES),
    ) as mock:
        yield mock


@pytest.fixture(name="mock_get_uuid", autouse=True)
def mock_get_uuid_fixture():
    """Fixture to mock get_uuid."""
    with patch("homeassistant.helpers.instance_id.async_get") as mock:
        yield mock


async def test_new_version_shows_entity_true(
    hass, mock_get_uuid, mock_get_newest_version
):
    """Test if sensor is true if new version is available."""
    mock_get_uuid.return_value = MOCK_HUUID

    assert await async_setup_component(hass, updater.DOMAIN, {updater.DOMAIN: {}})

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
    hass, mock_get_uuid, mock_get_newest_version
):
    """Test if sensor is false if no new version is available."""
    mock_get_uuid.return_value = MOCK_HUUID
    mock_get_newest_version.return_value = (MOCK_VERSION, "")

    assert await async_setup_component(hass, updater.DOMAIN, {updater.DOMAIN: {}})

    await hass.async_block_till_done()

    assert hass.states.is_state("binary_sensor.updater", "off")
    assert (
        hass.states.get("binary_sensor.updater").attributes["newest_version"]
        == MOCK_VERSION
    )
    assert "release_notes" not in hass.states.get("binary_sensor.updater").attributes


async def test_disable_reporting(hass, mock_get_uuid, mock_get_newest_version):
    """Test we do not gather analytics when disable reporting is active."""
    mock_get_uuid.return_value = MOCK_HUUID
    mock_get_newest_version.return_value = (MOCK_VERSION, "")

    assert await async_setup_component(
        hass, updater.DOMAIN, {updater.DOMAIN: {"reporting": False}}
    )
    await hass.async_block_till_done()

    assert hass.states.is_state("binary_sensor.updater", "off")
    await updater.get_newest_version(hass, MOCK_HUUID, MOCK_CONFIG)
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
        return_value={"fake": "bla"},
    ):
        res = await updater.get_newest_version(hass, MOCK_HUUID, False)
        assert res == (MOCK_RESPONSE["version"], MOCK_RESPONSE["release-notes"])


async def test_error_fetching_new_version_bad_json(hass, aioclient_mock):
    """Test we handle json error while fetching new version."""
    aioclient_mock.post(updater.UPDATER_URL, text="not json")

    with patch(
        "homeassistant.helpers.system_info.async_get_system_info",
        return_value={"fake": "bla"},
    ), pytest.raises(UpdateFailed):
        await updater.get_newest_version(hass, MOCK_HUUID, False)


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
        return_value={"fake": "bla"},
    ), pytest.raises(UpdateFailed):
        await updater.get_newest_version(hass, MOCK_HUUID, False)


async def test_new_version_shows_entity_after_hour_hassio(
    hass, mock_get_uuid, mock_get_newest_version
):
    """Test if binary sensor gets updated if new version is available / Hass.io."""
    mock_get_uuid.return_value = MOCK_HUUID
    mock_component(hass, "hassio")
    hass.data["hassio_core_info"] = {"version_latest": "999.0"}

    assert await async_setup_component(hass, updater.DOMAIN, {updater.DOMAIN: {}})

    await hass.async_block_till_done()

    assert hass.states.is_state("binary_sensor.updater", "on")
    assert (
        hass.states.get("binary_sensor.updater").attributes["newest_version"] == "999.0"
    )
    assert (
        hass.states.get("binary_sensor.updater").attributes["release_notes"]
        == RELEASE_NOTES
    )
