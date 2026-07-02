"""Tests for the Tasmota update platform."""

import copy
import json
from unittest.mock import AsyncMock, patch

from aiogithubapi import GitHubReleaseModel
import pytest

from homeassistant.components.tasmota.const import DEFAULT_PREFIX, DOMAIN
from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_URL,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import setup_tasmota_helper
from .test_common import DEFAULT_CONFIG

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


@pytest.fixture
def mock_github_latest_release(request: pytest.FixtureRequest):
    """Mock the GitHub release API to return a specific version."""
    tag_name: str = request.param

    mock_response = AsyncMock(
        data=GitHubReleaseModel(
            {
                "tag_name": tag_name,
                "name": f"Tasmota {tag_name.removeprefix('v')}",
                "html_url": f"https://github.com/arendst/Tasmota/releases/tag/{tag_name}",
                "body": """\
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./tools/logo/TASMOTA_FullLogo_Vector_White.svg">
  <img alt="Logo" src="./tools/logo/TASMOTA_FullLogo_Vector.svg" align="right" height="76">
</picture>

# RELEASE NOTES

...        """,
            }
        )
    )

    with patch(
        "aiogithubapi.namespaces.releases.GitHubReleasesNamespace.latest",
        new=AsyncMock(return_value=mock_response),
    ):
        yield tag_name


@pytest.mark.parametrize(
    ("mock_github_latest_release", "expected_update_state"),
    [
        ("v0.0.0", STATE_OFF),
        ("v" + DEFAULT_CONFIG["sw"], STATE_OFF),
        (
            "v" + ".".join(str(int(x) + 1) for x in DEFAULT_CONFIG["sw"].split(".")),
            STATE_ON,
        ),
    ],
    indirect=["mock_github_latest_release"],
)
async def test_device_update_entity(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    mock_github_latest_release: str,
    expected_update_state: str,
) -> None:
    """Test that an update entity is created and reports correct version state."""
    await setup_tasmota_helper(hass)

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
    assert device_entry is not None
    assert device_entry.sw_version == DEFAULT_CONFIG["sw"]

    entity_id = er.async_get(hass).async_get_entity_id(
        "update", DOMAIN, f"{device_entry.id}_update"
    )
    assert entity_id is not None, "Update entity should exist for each Tasmota device"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_INSTALLED_VERSION] == DEFAULT_CONFIG["sw"]
    assert state.attributes[
        ATTR_LATEST_VERSION
    ] == mock_github_latest_release.removeprefix("v")
    assert state.attributes[ATTR_RELEASE_URL]
    assert state.state == expected_update_state
