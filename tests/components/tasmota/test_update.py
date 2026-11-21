"""Tests for the Tasmota update platform."""

import asyncio
import copy
from datetime import timedelta
import json
from unittest.mock import AsyncMock, patch

from aiogithubapi import (
    GitHubConnectionException,
    GitHubRatelimitException,
    GitHubReleaseModel,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_fire_time_changed,
)
from pytest_homeassistant.typing import MqttMockHAClient

from homeassistant.components.tasmota.const import (
    CONF_DISCOVERY_PREFIX,
    DEFAULT_PREFIX,
    DOMAIN,
)
from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_URL,
    DATA_COMPONENT,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import setup_tasmota_helper
from .test_common import DEFAULT_CONFIG, DEFAULT_VERSION, NEWER_VERSION, OLDER_VERSION


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
        ("v" + OLDER_VERSION, STATE_OFF),
        ("v" + DEFAULT_VERSION, STATE_OFF),
        ("v" + NEWER_VERSION, STATE_ON),
    ],
    indirect=["mock_github_latest_release"],
)
async def test_device_update_entity(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
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

    device_entry = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, mac),
        hass.config_entries.async_entries("tasmota")[0].entry_id,
    )
    assert device_entry is not None
    assert device_entry.sw_version == DEFAULT_VERSION

    entity_id = entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, dr.format_mac(mac)
    )
    assert entity_id is not None, "Update entity should exist for each Tasmota device"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_INSTALLED_VERSION] == DEFAULT_VERSION
    assert state.attributes[
        ATTR_LATEST_VERSION
    ] == mock_github_latest_release.removeprefix("v")
    assert state.attributes[ATTR_RELEASE_URL]
    assert state.state == expected_update_state

    update_entity = hass.data[DATA_COMPONENT].get_entity(entity_id)
    assert update_entity is not None
    result = await update_entity.async_release_notes()
    assert result
    assert "<picture>" not in result
    assert "# RELEASE NOTES" in result


async def test_device_update_entity_rediscovered(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the update entity is recreated when a device is rediscovered."""
    await setup_tasmota_helper(hass)

    config = copy.deepcopy(DEFAULT_CONFIG)
    mac = config["mac"]
    config_topic = f"{DEFAULT_PREFIX}/{mac}/config"

    async_fire_mqtt_message(hass, config_topic, json.dumps(config))
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(Platform.UPDATE, DOMAIN, dr.format_mac(mac))
        is not None
    )

    # Empty config removes the device and its update entity
    async_fire_mqtt_message(hass, config_topic, "")
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(Platform.UPDATE, DOMAIN, dr.format_mac(mac))
        is None
    )

    # Rediscovery creates a new update entity
    async_fire_mqtt_message(hass, config_topic, json.dumps(config))
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, dr.format_mac(mac)
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == DEFAULT_VERSION
    assert state.attributes[ATTR_LATEST_VERSION] == NEWER_VERSION


@pytest.fixture
def mock_github_latest_release_failure(request: pytest.FixtureRequest) -> AsyncMock:
    """Mock the GitHub release API to fail or return an empty response."""
    mock: AsyncMock = AsyncMock(**request.param)

    with patch(
        "aiogithubapi.namespaces.releases.GitHubReleasesNamespace.latest",
        new=mock,
    ):
        yield mock


@pytest.mark.parametrize(
    "mock_github_latest_release_failure",
    [
        pytest.param(
            {"side_effect": GitHubConnectionException("Unable to connect")},
            id="connection_error",
        ),
        pytest.param(
            {"side_effect": GitHubRatelimitException("Rate limit exceeded")},
            id="ratelimit_error",
        ),
        pytest.param({"return_value": AsyncMock(data=None)}, id="empty_response"),
    ],
    indirect=["mock_github_latest_release_failure"],
)
async def test_device_update_entity_github_failure(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_github_latest_release_failure: AsyncMock,
) -> None:
    """Test the update entity handles GitHub outages, rate limits and empty responses."""
    await setup_tasmota_helper(hass)

    config = copy.deepcopy(DEFAULT_CONFIG)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, dr.format_mac(mac)
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # When the API recovers, the entity becomes available again
    mock_github_latest_release_failure.side_effect = None
    mock_github_latest_release_failure.return_value = AsyncMock(
        data=GitHubReleaseModel(
            {
                "tag_name": f"v{NEWER_VERSION}",
                "name": f"Tasmota {NEWER_VERSION}",
                "html_url": f"https://github.com/arendst/Tasmota/releases/tag/v{NEWER_VERSION}",
                "body": "",
            }
        )
    )
    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == DEFAULT_VERSION
    assert state.attributes[ATTR_LATEST_VERSION] == NEWER_VERSION
    assert state.attributes[ATTR_RELEASE_URL] == (
        f"https://github.com/arendst/Tasmota/releases/tag/v{NEWER_VERSION}"
    )


async def test_device_update_entity_refreshes_on_firmware_change(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the update entity reflects firmware changes reported by the device."""
    await setup_tasmota_helper(hass)

    config = copy.deepcopy(DEFAULT_CONFIG)
    mac = config["mac"]
    config_topic = f"{DEFAULT_PREFIX}/{mac}/config"

    async_fire_mqtt_message(hass, config_topic, json.dumps(config))
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, dr.format_mac(mac)
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == DEFAULT_VERSION

    # Device reports a newer firmware version over MQTT
    updated_config = copy.deepcopy(config)
    updated_config["sw"] = NEWER_VERSION
    async_fire_mqtt_message(hass, config_topic, json.dumps(updated_config))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_INSTALLED_VERSION] == NEWER_VERSION
    assert state.state == STATE_OFF


async def test_setup_not_blocked_by_slow_github_refresh(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test integration setup is not delayed by a slow GitHub refresh."""

    refresh_started = asyncio.Event()
    refresh_proceed = asyncio.Event()

    async def slow_latest(*_args: object, **_kwargs: object) -> AsyncMock:
        refresh_started.set()
        await refresh_proceed.wait()
        return AsyncMock(
            data=GitHubReleaseModel(
                {
                    "tag_name": f"v{NEWER_VERSION}",
                    "name": f"Tasmota {NEWER_VERSION}",
                    "html_url": f"https://github.com/arendst/Tasmota/releases/tag/v{NEWER_VERSION}",
                    "body": "",
                }
            )
        )

    with patch(
        "aiogithubapi.namespaces.releases.GitHubReleasesNamespace.latest",
        new=AsyncMock(side_effect=slow_latest),
    ):
        hass.config.components.add("tasmota")

        entry = MockConfigEntry(
            data={CONF_DISCOVERY_PREFIX: DEFAULT_PREFIX},
            domain=DOMAIN,
            title="Tasmota",
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)

        assert not refresh_proceed.is_set()
        await asyncio.wait_for(refresh_started.wait(), timeout=10)

        refresh_proceed.set()
        await hass.async_block_till_done()

        config = copy.deepcopy(DEFAULT_CONFIG)
        mac = config["mac"]
        async_fire_mqtt_message(
            hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config)
        )
        await hass.async_block_till_done()

        entity_id = entity_registry.async_get_entity_id(
            Platform.UPDATE, DOMAIN, dr.format_mac(mac)
        )
        assert entity_id is not None

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes[ATTR_INSTALLED_VERSION] == DEFAULT_VERSION
        assert state.attributes[ATTR_LATEST_VERSION] == NEWER_VERSION
