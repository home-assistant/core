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
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
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

from tests.common import MockConfigEntry


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


async def test_yaml_import_entity_subset(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
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

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    entity_ids = {entity.entity_id for entity in entities}

    assert "binary_sensor.front_door_motion_detected" in entity_ids
    assert "sensor.front_door_sd_used" in entity_ids
    assert "switch.front_door_privacy_mode" in entity_ids
    assert "camera.front_door" in entity_ids
    assert len([eid for eid in entity_ids if eid.startswith("binary_sensor.")]) == 1
    assert len([eid for eid in entity_ids if eid.startswith("sensor.")]) == 1
    assert len([eid for eid in entity_ids if eid.startswith("switch.")]) == 1


async def test_yaml_import_omitted_optional_platforms(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test YAML import with omitted platform keys creates only the camera."""
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

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    platforms = {entity.entity_id.split(".")[0] for entity in entities}
    assert platforms == {Platform.CAMERA}


async def test_yaml_import_no_optional_platforms(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test YAML import with empty platform lists creates only the camera."""
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
                        binary_sensors=[],
                        sensors=[],
                        switches=[],
                    )
                ]
            },
        )
        await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    platforms = {entity.entity_id.split(".")[0] for entity in entities}
    assert platforms == {Platform.CAMERA}


async def test_yaml_import_failure_creates_repair_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test failed YAML import creates a per-camera repair issue."""
    with patch_amcrest_checker() as mock_checker:
        _configure_checker_mock(mock_checker, current_time_side_effect=LoginError)
        assert await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: [_yaml_camera()]},
        )
        await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    issue = issue_registry.async_get_issue(
        DOMAIN,
        f"deprecated_yaml_import_issue_{TEST_HOST}_{TEST_PORT}_invalid_auth",
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml_import_issue_invalid_auth"
    assert (
        issue_registry.async_get_issue(
            HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
        )
        is None
    )


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

    issue = issue_registry.async_get_issue(
        DOMAIN,
        f"deprecated_yaml_import_issue_{TEST_HOST}_{TEST_PORT}_{reason}",
    )
    assert issue is not None
    assert issue.translation_key == f"deprecated_yaml_import_issue_{reason}"


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


async def test_ui_entry_uses_default_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test UI-created entries use default entity sets when options omit platform keys."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch_amcrest_checker(),
        patch("homeassistant.components.amcrest._start_event_monitor"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    platforms = {entity.entity_id.split(".")[0] for entity in entities}
    assert platforms == {
        Platform.BINARY_SENSOR,
        Platform.CAMERA,
        Platform.SENSOR,
        Platform.SWITCH,
    }

    unique_ids = {entity.unique_id for entity in entities}
    assert f"{TEST_SERIAL}-audio_detected-0" in unique_ids
    assert f"{TEST_SERIAL}-motion_detected-0" in unique_ids
    assert f"{TEST_SERIAL}-crossline_detected-0" in unique_ids
    assert f"{TEST_SERIAL}-online-0" in unique_ids
