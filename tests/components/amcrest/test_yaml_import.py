"""Test Amcrest YAML import."""

from typing import Any
from unittest.mock import MagicMock, patch

from amcrest import AmcrestError, LoginError
import pytest

from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_USERNAME,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import (
    TEST_HOST,
    TEST_PASSWORD,
    TEST_PORT,
    TEST_SERIAL,
    TEST_USERNAME,
    mock_async_property,
    patch_amcrest_checker,
)


def _yaml_camera(
    *,
    host: str = TEST_HOST,
    port: int = TEST_PORT,
    name: str = "Front Door",
    username: str = TEST_USERNAME,
    password: str = TEST_PASSWORD,
    binary_sensors: list[str] | None = None,
    sensors: list[str] | None = None,
    switches: list[str] | None = None,
) -> dict[str, Any]:
    """Build a single YAML camera configuration."""
    config: dict[str, Any] = {
        CONF_HOST: host,
        CONF_PORT: port,
        CONF_USERNAME: username,
        CONF_PASSWORD: password,
        CONF_NAME: name,
    }
    if binary_sensors is not None:
        config[CONF_BINARY_SENSORS] = binary_sensors
    if sensors is not None:
        config[CONF_SENSORS] = sensors
    if switches is not None:
        config[CONF_SWITCHES] = switches
    return config


def _entity_slug(name: str) -> str:
    """Return the entity_id object slug for a camera name."""
    return name.lower().replace(" ", "_")


def _configure_checker_mock(
    mock_class: MagicMock,
    *,
    current_time_side_effect: type[BaseException] | BaseException | None = None,
    serial_number: str | None = TEST_SERIAL,
) -> None:
    """Configure AmcrestChecker mock to fail during connection validation."""
    api = MagicMock()
    api.get_base_url.return_value = f"http://{TEST_HOST}:{TEST_PORT}"
    mock_async_property(
        api,
        "async_current_time",
        return_value=None,
        side_effect=current_time_side_effect,
    )
    mock_async_property(api, "async_serial_number", return_value=serial_number)
    mock_class.return_value = api


async def test_yaml_import_success(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import creates a config entry and deprecation issue."""
    with (
        patch_amcrest_checker(),
        patch("homeassistant.components.amcrest._start_event_monitor"),
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: [_yaml_camera()]},
        )
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_IMPORT
    assert entries[0].title == "Front Door"
    assert entries[0].unique_id == TEST_SERIAL

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_yaml_import_full_config(hass: HomeAssistant) -> None:
    """Test YAML import with all platform keys creates the configured entities."""
    binary_sensors = [
        "audio_detected",
        "crossline_detected",
        "motion_detected",
        "online",
    ]
    sensors = ["ptz_preset", "sdcard"]
    switches = ["privacy_mode"]

    with (
        patch_amcrest_checker(),
        patch("homeassistant.components.amcrest._start_event_monitor"),
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: [
                    _yaml_camera(
                        binary_sensors=binary_sensors,
                        sensors=sensors,
                        switches=switches,
                    )
                ]
            },
        )
        await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.options[CONF_BINARY_SENSORS] == binary_sensors
    assert entry.options[CONF_SENSORS] == sensors
    assert entry.options[CONF_SWITCHES] == switches

    slug = _entity_slug("Front Door")
    entity_ids = hass.states.async_entity_ids()
    assert f"binary_sensor.{slug}_audio_detected" in entity_ids
    assert f"binary_sensor.{slug}_crossline_detected" in entity_ids
    assert f"binary_sensor.{slug}_motion_detected" in entity_ids
    assert f"binary_sensor.{slug}_online" in entity_ids
    assert f"sensor.{slug}_ptz_preset" in entity_ids
    assert f"sensor.{slug}_sd_used" in entity_ids
    assert f"switch.{slug}_privacy_mode" in entity_ids
    assert f"camera.{slug}" in entity_ids
    assert (
        len([eid for eid in entity_ids if eid.startswith(f"binary_sensor.{slug}")]) == 4
    )
    assert len([eid for eid in entity_ids if eid.startswith(f"sensor.{slug}")]) == 2
    assert len([eid for eid in entity_ids if eid.startswith(f"switch.{slug}")]) == 1


async def test_yaml_import_entity_subset(hass: HomeAssistant) -> None:
    """Test YAML import honors configured entity subsets."""
    with (
        patch_amcrest_checker(),
        patch("homeassistant.components.amcrest._start_event_monitor"),
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: [
                    _yaml_camera(
                        binary_sensors=["motion_detected_polled"],
                        sensors=["sdcard"],
                        switches=["privacy_mode"],
                    )
                ]
            },
        )
        await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids()
    assert "binary_sensor.front_door_motion_detected" in entity_ids
    assert "sensor.front_door_sd_used" in entity_ids
    assert "switch.front_door_privacy_mode" in entity_ids
    assert "camera.front_door" in entity_ids
    assert (
        len([eid for eid in entity_ids if eid.startswith("binary_sensor.front_door")])
        == 1
    )
    assert len([eid for eid in entity_ids if eid.startswith("sensor.front_door")]) == 1
    assert len([eid for eid in entity_ids if eid.startswith("switch.front_door")]) == 1


@pytest.mark.parametrize(
    "camera_config",
    [
        pytest.param(_yaml_camera(), id="omitted_keys"),
        pytest.param(
            _yaml_camera(binary_sensors=[], sensors=[], switches=[]),
            id="empty_lists",
        ),
    ],
)
async def test_yaml_import_without_optional_platforms(
    hass: HomeAssistant,
    camera_config: dict[str, Any],
) -> None:
    """Test YAML import without optional platforms creates only the camera."""
    with (
        patch_amcrest_checker(),
        patch("homeassistant.components.amcrest._start_event_monitor"),
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: [camera_config]},
        )
        await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids()
    front_door_entities = [
        entity_id
        for entity_id in entity_ids
        if entity_id.split(".", 1)[-1].startswith("front_door")
    ]
    assert front_door_entities == ["camera.front_door"]


async def test_yaml_import_no_serial_number(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test failed YAML import creates a repair issue when serial is missing."""
    with patch_amcrest_checker() as mock_checker:
        _configure_checker_mock(mock_checker, serial_number="")
        assert await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: [_yaml_camera()]},
        )
        await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    issue = issue_registry.async_get_issue(
        DOMAIN,
        f"deprecated_yaml_import_issue_{TEST_HOST}_{TEST_PORT}_no_serial_number",
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml_import_issue_no_serial_number"


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (LoginError, "invalid_auth"),
        (AmcrestError, "cannot_connect"),
    ],
)
async def test_yaml_import_failure_reasons(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    side_effect: type[BaseException],
    reason: str,
) -> None:
    """Test failed YAML import creates repair issues for connection errors."""
    with patch_amcrest_checker() as mock_checker:
        _configure_checker_mock(mock_checker, current_time_side_effect=side_effect)
        assert await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: [_yaml_camera()]},
        )
        await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    issue = issue_registry.async_get_issue(
        DOMAIN,
        f"deprecated_yaml_import_issue_{TEST_HOST}_{TEST_PORT}_{reason}",
    )
    assert issue is not None
    assert issue.translation_key == f"deprecated_yaml_import_issue_{reason}"
    assert (
        issue_registry.async_get_issue(
            HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
        )
        is None
    )


async def test_yaml_import_continue_on_failure(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test one failed camera import does not block others."""
    good_host = "192.168.1.101"
    good_serial = "67890"

    def _factory(
        _hass: HomeAssistant,
        _name: str,
        host: str,
        _port: int,
        _username: str,
        _password: str,
    ) -> MagicMock:
        api = MagicMock()
        api.get_base_url.return_value = f"http://{host}:{TEST_PORT}"
        if host == TEST_HOST:
            mock_async_property(api, "async_current_time", side_effect=LoginError)
            mock_async_property(api, "async_serial_number", return_value=TEST_SERIAL)
        else:
            mock_async_property(api, "async_current_time", return_value=None)
            mock_async_property(api, "async_serial_number", return_value=good_serial)
        return api

    with (
        patch_amcrest_checker(side_effect=_factory),
        patch("homeassistant.components.amcrest._start_event_monitor"),
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: [
                    _yaml_camera(host=TEST_HOST, name="Bad Camera"),
                    _yaml_camera(host=good_host, name="Good Camera"),
                ]
            },
        )
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_HOST] == good_host
    assert entries[0].title == "Good Camera"

    assert (
        issue_registry.async_get_issue(
            DOMAIN,
            f"deprecated_yaml_import_issue_{TEST_HOST}_{TEST_PORT}_invalid_auth",
        )
        is not None
    )
    assert (
        issue_registry.async_get_issue(
            HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
        )
        is not None
    )


async def test_services_without_yaml(hass: HomeAssistant) -> None:
    """Test services are registered even without YAML configuration."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "enable_recording")
