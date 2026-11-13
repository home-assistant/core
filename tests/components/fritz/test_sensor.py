"""Tests for Fritz!Tools sensor platform."""

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from fritzconnection.core.exceptions import FritzConnectionException
from fritzconnection.lib.fritzhosts import FritzHosts
from fritzconnection.lib.fritzstatus import FritzStatus
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from requests.exceptions import RequestException
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fritz.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    MOCK_FB_SERVICES,
    MOCK_HOST_ATTRIBUTES_DATA,
    MOCK_HOST_PHONE,
    MOCK_MESH_DATA,
    MOCK_USER_DATA,
    MOCK_WLAN_DEVICE_NODE,
)

PHONE_LINK_SENSORS = (
    "sensor.phone_signal_strength",
    "sensor.phone_download_link_rate",
    "sensor.phone_upload_link_rate",
    "sensor.phone_max_download_link_rate",
    "sensor.phone_max_upload_link_rate",
)


def _add_wlan_device(fh_class_mock: type[FritzHosts]) -> dict[str, Any]:
    """Add a WLAN connected device to the mocked hosts and return its node link."""
    mesh_data = deepcopy(MOCK_MESH_DATA)
    wlan_device_node = deepcopy(MOCK_WLAN_DEVICE_NODE)
    mesh_data["nodes"].append(wlan_device_node)
    fh_class_mock.get_mesh_topology.return_value = mesh_data
    fh_class_mock.get_hosts_attributes.return_value = [
        *MOCK_HOST_ATTRIBUTES_DATA,
        MOCK_HOST_PHONE,
    ]
    return wlan_device_node["node_interfaces"][0]["node_links"][0]


@pytest.fixture
def wlan_device_link(fh_class_mock: type[FritzHosts]) -> dict[str, Any]:
    """Fixture that adds a WLAN connected device to the mocked hosts."""
    return _add_wlan_device(fh_class_mock)


@pytest.mark.freeze_time(datetime(2024, 9, 1, 20, tzinfo=UTC))
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "wlan_device_link")
async def test_sensor_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup of Fritz!Tools sensors."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch("homeassistant.components.fritz.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_sensor_update_fail(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test failed update of Fritz!Tools sensors."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    fc_class_mock().call_action_side_effect(FritzConnectionException("Boom"))

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Error while updating the data: Boom" in caplog.text

    sensors = hass.states.async_all(SENSOR_DOMAIN)
    for sensor in sensors:
        assert sensor.state == STATE_UNAVAILABLE


@pytest.mark.freeze_time("2026-02-14T09:30:00+00:00")
async def test_sensor_uptime_spike(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test handling of uptime spikes in Fritz!Tools sensors."""

    entity_id = "sensor.mock_title_uptime"

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == "2026-01-16T06:00:21+00:00"

    # Simulate uptime spike by setting uptime to a value that shifts
    # the resulting timestamp only by 1 second.
    base_uptime = MOCK_FB_SERVICES["DeviceInfo1"]["GetInfo"]["NewUpTime"]
    update_uptime = {
        "DeviceInfo1": {
            "GetInfo": {
                "NewUpTime": base_uptime + SCAN_INTERVAL + 1,
            },
        },
    }
    fc_class_mock().override_services({**MOCK_FB_SERVICES, **update_uptime})

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (new_state := hass.states.get(entity_id))
    assert new_state.state == "2026-01-16T06:00:21+00:00"


@pytest.mark.freeze_time(datetime(2024, 9, 1, 20, tzinfo=UTC))
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("side_effect", "return_values"),
    [
        (RequestException("boom"), None),
        (None, [0, 0, 0]),
        (None, []),
        (FritzConnectionException("boom"), None),
    ],
)
async def test_sensor_cpu_temp_not_supported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    side_effect,
    return_values,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup of Fritz!Tools sensors."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.fritz.PLATFORMS", [Platform.SENSOR]),
        patch(
            "homeassistant.components.fritz.coordinator.FritzStatus", fs_class_mock
        ) as mock_status,
    ):
        mock_status.get_cpu_temperatures.side_effect = side_effect
        mock_status.get_cpu_temperatures.return_value = return_values
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
        assert not entity_registry.async_is_registered(
            "sensor.mock_title_cpu_temperature"
        )


@pytest.mark.freeze_time(datetime(2024, 9, 1, 20, tzinfo=UTC))
async def test_sensor_cpu_temp_unknown_on_request_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test the CPU temperature sensor turns unknown when reading it raises."""
    entity_id = "sensor.mock_title_cpu_temperature"

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == "42"

    with patch.object(
        FritzStatus, "get_cpu_temperatures", side_effect=RequestException("boom")
    ):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "fc_data",
    [
        {
            **MOCK_FB_SERVICES,
            "WANCommonIFC1": {
                **MOCK_FB_SERVICES["WANCommonIFC1"],
                "GetAddonInfos": FritzConnectionException("Not available Action"),
            },
        }
    ],
)
@pytest.mark.usefixtures("fc_class_mock", "fh_class_mock", "fs_class_mock")
async def test_sensor_addon_infos_not_supported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test transmission rate and traffic sensors are not created when not supported."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch("homeassistant.components.fritz.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    for entity_id in (
        "sensor.mock_title_upload_throughput",
        "sensor.mock_title_download_throughput",
        "sensor.mock_title_gb_sent",
        "sensor.mock_title_gb_received",
    ):
        assert not entity_registry.async_is_registered(entity_id)
    assert "Error adding entity" not in caplog.text


@pytest.mark.usefixtures(
    "fc_class_mock", "fh_class_mock", "fs_class_mock", "wlan_device_link"
)
async def test_link_sensors_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test link sensors of connected devices are disabled by default."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch("homeassistant.components.fritz.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    for entity_id in (*PHONE_LINK_SENSORS, "sensor.printer_max_download_link_rate"):
        assert (entity_entry := entity_registry.async_get(entity_id))
        assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default",
    "fc_class_mock",
    "fh_class_mock",
    "fs_class_mock",
)
async def test_link_sensors_wlan_only(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test signal strength and link rate sensors are not created for LAN devices."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch("homeassistant.components.fritz.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entity_registry.async_is_registered("sensor.printer_max_upload_link_rate")
    for entity_id in (
        "sensor.printer_signal_strength",
        "sensor.printer_download_link_rate",
        "sensor.printer_upload_link_rate",
    ):
        assert not entity_registry.async_is_registered(entity_id)


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "fc_class_mock", "fs_class_mock"
)
async def test_link_sensors_new_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fh_class_mock: type[FritzHosts],
) -> None:
    """Test link sensors are created for a device connecting at runtime."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch("homeassistant.components.fritz.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    for entity_id in PHONE_LINK_SENSORS:
        assert hass.states.get(entity_id) is None

    _add_wlan_device(fh_class_mock)

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for entity_id in PHONE_LINK_SENSORS:
        assert (state := hass.states.get(entity_id))
        assert state.state != STATE_UNKNOWN


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default",
    "fc_class_mock",
    "fh_class_mock",
    "fs_class_mock",
)
async def test_link_sensors_disconnected(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    wlan_device_link: dict[str, Any],
) -> None:
    """Test link sensors become unknown when the device disconnects."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch("homeassistant.components.fritz.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    for entity_id in PHONE_LINK_SENSORS:
        assert (state := hass.states.get(entity_id))
        assert state.state != STATE_UNKNOWN

    wlan_device_link["state"] = "DISCONNECTED"

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for entity_id in PHONE_LINK_SENSORS:
        assert (state := hass.states.get(entity_id))
        assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default",
    "fc_class_mock",
    "fh_class_mock",
    "fs_class_mock",
)
async def test_link_sensor_signal_strength_not_available(
    hass: HomeAssistant,
    wlan_device_link: dict[str, Any],
) -> None:
    """Test signal strength is unknown when the FRITZ!Box does not report it."""
    wlan_device_link["rx_rcpi"] = 255

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch("homeassistant.components.fritz.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.phone_signal_strength"))
    assert state.state == STATE_UNKNOWN
