"""Tests for the Tasmota update platform."""

import copy
import json

from aiogithubapi import GitHubReleaseModel
import pytest

from homeassistant.components.tasmota.const import DEFAULT_PREFIX
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .test_common import DEFAULT_CONFIG

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


@pytest.mark.parametrize(
    ("candidate_version", "update_available"),
    [
        ("0.0.0", False),
        (".".join(str(int(x) + 1) for x in DEFAULT_CONFIG["sw"].split(".")), True),
    ],
)
async def test_update_state(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    setup_tasmota,
    candidate_version: str,
    update_available: bool,
) -> None:
    """Test setting up a device."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )

    # TODO mock coordinator.client.repos.releases.latest("arendst/Tasmota") to return this
    data = GitHubReleaseModel(
        tag_name=f"v{candidate_version}",
        name=f"Tasmota v{candidate_version} Foo",
        html_url=f"https://github.com/arendst/Tasmota/releases/tag/v{candidate_version}",
        body="""\
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./tools/logo/TASMOTA_FullLogo_Vector_White.svg">
  <img alt="Logo" src="./tools/logo/TASMOTA_FullLogo_Vector.svg" align="right" height="76">
</picture>

# RELEASE NOTES

...        """,
    )

    # TODO update_available test, device_entry.sw_version has the current version
