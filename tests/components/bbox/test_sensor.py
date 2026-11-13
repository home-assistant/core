"""Tests for the Bbox sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.bbox.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_VERIFY_SSL,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .const import ALL_SENSORS, PASSWORD, UPTIME

SENSOR_PLATFORM_CONFIG = {
    "platform": "bbox",
    "monitored_variables": ALL_SENSORS,
}

EXPECTED_STATES = {
    "sensor.bbox_maximum_download_bandwidth": "1000.0",
    "sensor.bbox_maximum_upload_bandwidth": "1000.0",
    "sensor.bbox_currently_used_download_bandwidth": "17.95",
    "sensor.bbox_currently_used_upload_bandwidth": "3.46",
    "sensor.bbox_number_of_reboot": "40",
}


async def test_sensors(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the entry exposes the WAN stats and device info sensors."""
    freezer.move_to("2026-11-11T15:00:00+00:00")
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_NAME: "Bbox",
            CONF_MONITORED_VARIABLES: ALL_SENSORS,
        },
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    expected_uptime = (utcnow() - timedelta(seconds=UPTIME)).isoformat()
    for entity_id, state in EXPECTED_STATES.items():
        assert hass.states.get(entity_id).state == state, entity_id
    assert hass.states.get("sensor.bbox_uptime").state == expected_uptime


async def test_sensors_monitored_variables_subset(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test only the monitored variables become entities."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_MONITORED_VARIABLES: ["uptime"]},
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.bbox_uptime") is not None
    assert hass.states.get("sensor.bbox_number_of_reboot") is None


async def test_yaml_import(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the legacy sensor YAML platform is imported into a config entry."""
    assert await async_setup_component(
        hass, "sensor", {"sensor": SENSOR_PLATFORM_CONFIG}
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.data[CONF_HOST] == "mabbox.bytel.fr"
    assert entry.data[CONF_MONITORED_VARIABLES] == ALL_SENSORS
    assert entry.data[CONF_PASSWORD] == ""
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_keeps_connection_options(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test host/password/verify_ssl in the sensor YAML import into the entry."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "bbox",
                "monitored_variables": ALL_SENSORS,
                CONF_HOST: "192.168.1.1",
                CONF_PASSWORD: PASSWORD,
                CONF_VERIFY_SSL: False,
            }
        },
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.unique_id == "192.168.1.1"
    assert entry.data[CONF_HOST] == "192.168.1.1"
    assert entry.data[CONF_PASSWORD] == PASSWORD
    assert entry.data[CONF_VERIFY_SSL] is False
