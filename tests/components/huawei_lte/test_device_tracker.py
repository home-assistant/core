"""Tests for the Huawei LTE device tracker."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.huawei_lte.const import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import magic_client

TRACKER_ENTITY_ID = "device_tracker.testdevice2"


@pytest.mark.parametrize(
    ("new_hostname", "expected_device_name"),
    [
        pytest.param("Renamed", "Renamed", id="renamed"),
        # The device keeps its name instead of falling back to the MAC address
        pytest.param(None, "TestDevice2", id="hostname_removed"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_hostname_updated(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    new_hostname: str | None,
    expected_device_name: str,
) -> None:
    """Test the tracker is named by its device and a hostname change renames it."""
    huawei_lte = MockConfigEntry(domain=DOMAIN, data={CONF_URL: "http://huawei-lte"})
    huawei_lte.add_to_hass(hass)
    client = magic_client()
    with (
        patch("homeassistant.components.huawei_lte.Connection", MagicMock()),
        patch("homeassistant.components.huawei_lte.Client", return_value=client),
    ):
        await hass.config_entries.async_setup(huawei_lte.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(TRACKER_ENTITY_ID)
        assert state is not None
        assert state.attributes["friendly_name"] == "TestDevice2"
        registry_entry = entity_registry.async_get(TRACKER_ENTITY_ID)
        assert registry_entry is not None
        assert registry_entry.original_name is None

        hosts = client.lan.host_info.return_value["Hosts"]["Host"]
        hosts[1]["HostName"] = new_hostname
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(TRACKER_ENTITY_ID)
    assert state is not None
    assert state.attributes["friendly_name"] == expected_device_name
    device = device_registry.async_get(registry_entry.device_id)
    assert device is not None
    assert device.name == expected_device_name
