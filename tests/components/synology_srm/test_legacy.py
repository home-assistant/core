"""Test the unchanged YAML scanner and the manual migration notice."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from homeassistant.components.synology_srm.const import CONF_TRACKED_DEVICES, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import STATE_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .conftest import CLIENT, CONFIG, MAC

OTHER_MAC = "11:22:33:44:55:66"


@pytest.fixture
def mock_legacy_client() -> Generator[MagicMock]:
    """Mock the existing synchronous scanner client."""
    with patch(
        "homeassistant.components.synology_srm.device_tracker.synology_srm.Client"
    ) as mock:
        mock.return_value.core.get_network_nsm_device.return_value = [
            CLIENT,
            {**CLIENT, "mac": OTHER_MAC, "hostname": "Unassigned"},
        ]
        yield mock.return_value


@pytest.fixture
def legacy_config(hass: HomeAssistant, tmp_path: Path) -> ConfigType:
    """Set up legacy files with both assigned and unassigned tracked devices."""
    hass.config.config_dir = str(tmp_path)
    config = {"device_tracker": [{"platform": DOMAIN, **CONFIG}]}
    (tmp_path / "configuration.yaml").write_text(yaml.safe_dump(config))
    (tmp_path / "known_devices.yaml").write_text(
        yaml.safe_dump(
            {
                "phone": {"name": "Phone", "mac": MAC, "track": True},
                "unassigned": {"name": "Unassigned", "mac": OTHER_MAC, "track": True},
            }
        )
    )
    return config


async def test_legacy_scanner_keeps_working(
    hass: HomeAssistant,
    tmp_path: Path,
    legacy_config: ConfigType,
    mock_legacy_client: MagicMock,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Raise a notice without importing, disabling, or rewriting existing trackers."""
    original_config = (tmp_path / "configuration.yaml").read_bytes()
    original_known = (tmp_path / "known_devices.yaml").read_bytes()
    assert await async_setup_component(
        hass,
        "person",
        {
            "person": [
                {
                    "id": "test_user",
                    "name": "Test User",
                    "device_trackers": ["device_tracker.phone"],
                }
            ]
        },
    )
    assert await async_setup_component(hass, "device_tracker", legacy_config)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.phone").state == STATE_HOME
    assert hass.states.get("device_tracker.unassigned").state == STATE_HOME
    assert hass.states.get("person.test_user").state == STATE_HOME
    assert hass.states.get("person.test_user").attributes["device_trackers"] == [
        "device_tracker.phone"
    ]
    assert not hass.config_entries.async_entries(DOMAIN)
    assert entity_registry.async_get("device_tracker.phone") is None
    assert entity_registry.async_get("device_tracker.unassigned") is None
    assert (tmp_path / "configuration.yaml").read_bytes() == original_config
    assert (tmp_path / "known_devices.yaml").read_bytes() == original_known
    mock_legacy_client.core.get_network_nsm_device.assert_called_with(
        {"is_online": True}
    )
    mock_legacy_client.http.disable_https_verify.assert_called_once()
    issue = issue_registry.async_get_issue(DOMAIN, f"deprecated_yaml_{CONFIG['host']}")
    assert issue is not None
    assert issue.breaks_in_ha_version == "2027.5.0"
    assert issue.translation_key == "deprecated_yaml"
    assert issue.translation_placeholders == {"host": CONFIG["host"]}
    assert not issue.is_fixable


@pytest.mark.usefixtures("mock_legacy_client", "mock_client")
async def test_ui_setup_does_not_claim_active_legacy_id(
    hass: HomeAssistant,
    legacy_config: ConfigType,
    entity_registry: er.EntityRegistry,
) -> None:
    """A premature UI setup cannot rename over an active legacy tracker."""
    assert await async_setup_component(hass, "device_tracker", legacy_config)
    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.phone").state == STATE_HOME
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_TRACKED_DEVICES: [MAC]}
    )
    await hass.async_block_till_done()
    assert (
        entity_registry.async_get_entity_id("device_tracker", DOMAIN, MAC)
        == "device_tracker.phone_2"
    )
    assert entity_registry.async_get("device_tracker.phone") is None
    assert hass.states.get("device_tracker.phone").state == STATE_HOME
    assert hass.states.get("device_tracker.phone_2").state == STATE_HOME
    assert hass.states.get("device_tracker.unassigned").state == STATE_HOME
