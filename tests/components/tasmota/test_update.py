"""Tests for the Tasmota update platform."""

import asyncio
from collections.abc import Callable
import copy
from datetime import timedelta
import json
import logging
from typing import Any
from unittest.mock import AsyncMock, patch

from aiogithubapi import (
    GitHubConnectionException,
    GitHubRatelimitException,
    GitHubReleaseModel,
)
from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from hatasmota.update import TasmotaUpdate
from hatasmota.utils import get_topic_command, get_topic_stat, get_topic_tele
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_fire_time_changed,
)
from pytest_homeassistant.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from pytest_homeassistant.typing import MqttMockHAClient

from homeassistant.components.tasmota.const import (
    CONF_DISCOVERY_PREFIX,
    DEFAULT_PREFIX,
    DOMAIN,
)
from homeassistant.components.tasmota.update import INSTALL_TIMEOUT
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_URL,
    DATA_COMPONENT,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    UpdateEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from .conftest import setup_tasmota_helper
from .test_common import DEFAULT_CONFIG, DEFAULT_VERSION, NEWER_VERSION, OLDER_VERSION


@pytest.fixture
def update_entity_mqtt_disabled() -> bool:
    """Enable MQTT for the firmware update entity."""
    return False


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


# Firmware install tests. DEFAULT_CONFIG uses FullTopic "%topic%/%prefix%/"
DEVICE_TOPIC = DEFAULT_CONFIG["t"]
INSTALLED_VERSION = "15.2.0"
RELEASE_VERSION = "16.0.0"
ESP8266_OTA_URL = "http://ota.tasmota.com/tasmota/release/tasmota.bin.gz"
SOLO1_OTA_URL = "http://ota.tasmota.com/tasmota32/release/tasmota32solo1.bin"
CUSTOM_OTA_URL = "http://192.168.15.2/tasmota.bin.gz"


def _status2(version: str, hardware: str) -> str:
    """Return a STATUS2 payload."""
    return json.dumps(
        {
            "StatusFWR": {
                "Version": version,
                "BuildDateTime": "2026-10-16T07:42:00",
                "Core": "2_7_8",
                "SDK": "2.2.2-dev(38a443e)",
                "CpuFrequency": 80,
                "Hardware": hardware,
                "CR": "377/699",
            }
        }
    )


class FakeTasmota:
    """Answer the commands of the update entity like a Tasmota device does.

    The topics follow the device's discovery config, which tests may change.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        mqtt_mock: MqttMockHAClient,
        config: dict[str, Any],
        *,
        version: str = f"{INSTALLED_VERSION}(release-tasmota)",
        hardware: str = "ESP8266EX",
        ota_url: str = CUSTOM_OTA_URL,
        default_ota_url: str = ESP8266_OTA_URL,
        mqtt_response: bool = False,
    ) -> None:
        """Initialize.

        With mqtt_response, command results go to stat/<COMMAND> like with
        SetOption4 instead of stat/RESULT.
        """
        self.hass = hass
        self.config = config
        self.version = version
        self.hardware = hardware
        self.ota_url = ota_url
        self.default_ota_url = default_ota_url
        self.mqtt_response = mqtt_response
        # OtaUrl payloads the device does not answer
        self.ignore_ota_url: set[str] = set()
        self.upgrade_url: str | None = None
        # Commands whose publishing fails, e.g. MQTT disconnected
        self.fail_publish: set[tuple[str, str]] = set()
        self.on_upgrade: Callable[[], None] | None = None
        self.published: list[tuple[str, str]] = []
        mqtt_mock.async_publish.side_effect = self._async_publish

    @property
    def cmnd(self) -> str:
        """Return the command topic."""
        return get_topic_command(self.config)

    @property
    def commands(self) -> list[tuple[str, str]]:
        """Return the commands sent to the device, except STATUS polls."""
        return [
            (topic.removeprefix(self.cmnd), payload)
            for topic, payload in self.published
            if topic.startswith(self.cmnd) and topic != f"{self.cmnd}STATUS"
        ]

    async def _async_publish(
        self, topic: str, payload: str, qos: int, retain: bool, **kwargs: Any
    ) -> None:
        """Record a published message and answer it."""
        if (topic.removeprefix(self.cmnd), payload) in self.fail_publish:
            raise HomeAssistantError("Cannot publish to MQTT")
        self.published.append((topic, payload))
        if topic == f"{self.cmnd}STATUS" and payload == "2":
            self.fire("stat/STATUS2", _status2(self.version, self.hardware))
        elif topic == f"{self.cmnd}OtaUrl":
            if payload in self.ignore_ota_url:
                return
            if payload == "1":
                self.ota_url = self.default_ota_url
            elif payload:
                self.ota_url = payload
            self.respond("OtaUrl", self.ota_url)
        elif topic == f"{self.cmnd}Upgrade" and payload == "1":
            url = self.upgrade_url or self.ota_url
            self.respond("Upgrade", f"Version {self.version.split('(')[0]} from {url}")
            if self.on_upgrade:
                self.on_upgrade()

    def respond(self, command: str, value: str) -> None:
        """Publish a command result."""
        subtopic = f"stat/{command.upper()}" if self.mqtt_response else "stat/RESULT"
        self.fire(subtopic, json.dumps({command: value}))

    def fire(self, subtopic: str, payload: str, retain: bool = False) -> None:
        """Publish a message from the device, e.g. on "stat/RESULT"."""
        prefix, name = subtopic.split("/")
        base = (
            get_topic_stat(self.config)
            if prefix == "stat"
            else get_topic_tele(self.config)
        )
        async_fire_mqtt_message(self.hass, f"{base}{name}", payload, retain=retain)

    def info1(self, retain: bool = False) -> None:
        """Publish INFO1, which Tasmota sends once after it has booted."""
        info = {
            "Info1": {
                "Module": "Sonoff Basic",
                "Version": self.version,
                "FallbackTopic": "cmnd/DVES_49A3BC_fb/",
                "GroupTopic": "cmnd/tasmotas/",
            }
        }
        self.fire("tele/INFO1", json.dumps(info), retain=retain)

    def restart(self, version: str | None = None) -> None:
        """Boot the device, with new firmware if version is given."""
        if version is not None:
            self.version = version
        self.fire("tele/LWT", "Online")
        self.info1()


async def _setup_device(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    config_update: dict[str, Any] | None = None,
    **fake_kwargs: Any,
) -> tuple[str, FakeTasmota, dict[str, Any]]:
    """Set up Tasmota with one device and return its update entity and fake."""
    await setup_tasmota_helper(hass)
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["sw"] = INSTALLED_VERSION
    config.update(config_update or {})
    fake = FakeTasmota(hass, mqtt_mock, config, **fake_kwargs)
    _discover(hass, config)
    await hass.async_block_till_done()
    entity_id = entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, dr.format_mac(config["mac"])
    )
    assert entity_id is not None
    return entity_id, fake, config


def _discover(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Publish the discovery message of a device."""
    async_fire_mqtt_message(
        hass, f"{DEFAULT_PREFIX}/{config['mac']}/config", json.dumps(config)
    )


def _features(hass: HomeAssistant, entity_id: str) -> UpdateEntityFeature:
    """Return the supported features of the entity."""
    state = hass.states.get(entity_id)
    assert state is not None
    return UpdateEntityFeature(state.attributes[ATTR_SUPPORTED_FEATURES])


def _in_progress(hass: HomeAssistant, entity_id: str) -> bool:
    """Return the in_progress attribute of the entity."""
    state = hass.states.get(entity_id)
    assert state is not None
    return state.attributes[ATTR_IN_PROGRESS]


async def _install(hass: HomeAssistant, entity_id: str) -> None:
    """Call the install action."""
    await hass.services.async_call(
        UPDATE_DOMAIN, SERVICE_INSTALL, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )


def _start_install(hass: HomeAssistant, entity_id: str) -> asyncio.Task[None]:
    """Start the install action without waiting for it."""
    return hass.async_create_background_task(_install(hass, entity_id), "install")


async def _settle(hass: HomeAssistant) -> None:
    """Let pending callbacks run without waiting for a running install."""
    for _ in range(10):
        await asyncio.sleep(0)


async def _online(hass: HomeAssistant, fake: FakeTasmota) -> None:
    """Report the device online and wait for the STATUS2 poll it triggers."""
    fake.restart()
    await _settle(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("version", "hardware", "install_supported"),
    [
        ("15.2.0(release-tasmota)", "ESP8266EX", True),
        ("15.2.0(release-sensors)", "ESP8285N08", True),
        ("15.2.0(release-tasmota32)", "ESP32-C3", True),
        ("15.2.0(release-tasmota32)", "ESP8685", True),
        ("15.2.0(release-solo1)single-core", "ESP32-S0WD", True),
        ("14.0.0(release-lvgl-haspmota)", "ESP32-S3", True),
        ("15.2.0(tasmota)", "ESP8266EX", False),
        ("16.0.0.5(85cff52-tasmota)", "ESP8266EX", False),
        ("8.5.1(tasmota)", "ESP8266EX", False),
        ("13.4.0(tasmota)", "ESP8266EX", False),
        ("15.2.0(release-minimal)", "ESP8266EX", False),
        ("15.2.0(release-safeboot)", "ESP32-D0WD-V3", False),
        ("15.2.0(release-tasmota)", "ESP32-D0WD-V3", False),
    ],
)
@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_supported(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    mock_github_latest_release: str,
    version: str,
    hardware: str,
    install_supported: bool,
) -> None:
    """Test install is only offered for official release builds."""
    entity_id, fake, _ = await _setup_device(
        hass, mqtt_mock, entity_registry, version=version, hardware=hardware
    )
    # Firmware details are unknown until the device is online
    assert UpdateEntityFeature.INSTALL not in _features(hass, entity_id)
    assert hass.states.get(entity_id).state == STATE_ON

    await _online(hass, fake)

    assert (f"{DEVICE_TOPIC}/cmnd/STATUS", "2") in fake.published
    assert (UpdateEntityFeature.INSTALL in _features(hass, entity_id)) is (
        install_supported
    )
    assert UpdateEntityFeature.RELEASE_NOTES in _features(hass, entity_id)
    # The entity reports in_progress itself
    assert UpdateEntityFeature.PROGRESS in _features(hass, entity_id)
    assert fake.commands == []


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_feature_follows_firmware(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    mock_github_latest_release: str,
) -> None:
    """Test install is withdrawn when the device reports a custom build."""
    entity_id, fake, _ = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)
    assert UpdateEntityFeature.INSTALL in _features(hass, entity_id)

    fake.fire("stat/STATUS2", _status2("15.2.0(tasmota)", "ESP8266EX"))
    await hass.async_block_till_done()
    assert UpdateEntityFeature.INSTALL not in _features(hass, entity_id)

    # A boot announcement updates the firmware details too
    fake.version = f"{INSTALLED_VERSION}(release-tasmota)"
    fake.info1()
    await hass.async_block_till_done()
    assert UpdateEntityFeature.INSTALL in _features(hass, entity_id)

    # Messages without firmware details are ignored
    fake.fire("stat/STATUS2", "not json")
    fake.fire("tele/INFO1", json.dumps({"Info1": {"Version": "garbage"}}))
    fake.fire("tele/INFO1", json.dumps({"Info2": {}}))
    fake.fire("stat/RESULT", "not json")
    fake.fire("stat/RESULT", '["OtaUrl"]')
    await hass.async_block_till_done()
    assert UpdateEntityFeature.INSTALL in _features(hass, entity_id)


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_not_offered_with_deep_sleep(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    mock_github_latest_release: str,
) -> None:
    """Test install is not offered for a device with deep sleep."""
    entity_id, fake, _ = await _setup_device(
        hass, mqtt_mock, entity_registry, config_update={"dslp": 1}
    )
    fake.fire("stat/STATUS2", _status2("15.2.0(release-tasmota)", "ESP8266EX"))
    await hass.async_block_till_done()

    assert UpdateEntityFeature.INSTALL not in _features(hass, entity_id)
    update_entity = hass.data[DATA_COMPONENT].get_entity(entity_id)
    with pytest.raises(ServiceValidationError) as exc_info:
        await update_entity.async_install(None, False)
    assert exc_info.value.translation_key == "install_not_supported"
    assert fake.commands == []


@pytest.mark.parametrize(
    ("version", "hardware", "default_ota_url", "mqtt_response"),
    [
        ("15.2.0(release-tasmota)", "ESP8266EX", ESP8266_OTA_URL, False),
        ("15.2.0(release-tasmota)", "ESP8266EX", ESP8266_OTA_URL, True),
        (
            "15.2.0(release-tasmota)",
            "ESP8266EX",
            "http://ota.tasmota.com/tasmota/release/tasmota-DE.bin.gz",
            False,
        ),
        ("15.2.0(release-solo1)single-core", "ESP32-S0WD", SOLO1_OTA_URL, False),
        (
            "15.2.0(release-tasmota32)",
            "ESP32-C3",
            "http://ota.tasmota.com/tasmota32/release/tasmota32c3.bin",
            False,
        ),
    ],
)
@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    mock_github_latest_release: str,
    version: str,
    hardware: str,
    default_ota_url: str,
    mqtt_response: bool,
) -> None:
    """Test the device installs the image of its own variant."""
    aioclient_mock.head(default_ota_url, status=200)
    entity_id, fake, config = await _setup_device(
        hass,
        mqtt_mock,
        entity_registry,
        version=version,
        hardware=hardware,
        default_ota_url=default_ota_url,
        mqtt_response=mqtt_response,
    )
    await _online(hass, fake)
    assert UpdateEntityFeature.INSTALL in _features(hass, entity_id)

    in_progress: list[bool] = []

    def upgrade() -> None:
        in_progress.append(_in_progress(hass, entity_id))
        fake.fire("stat/UPGRADE", json.dumps({"Upgrade": "Successful. Restarting"}))
        fake.restart(version.replace(INSTALLED_VERSION, RELEASE_VERSION))
        config["sw"] = RELEASE_VERSION
        _discover(hass, config)

    fake.on_upgrade = upgrade
    await _install(hass, entity_id)
    await hass.async_block_till_done()

    assert fake.commands == [("OtaUrl", ""), ("OtaUrl", "1"), ("Upgrade", "1")]
    assert not [topic for topic, _ in fake.published if "tasmotas" in topic]
    assert aioclient_mock.mock_calls[-1][0] == "HEAD"
    assert str(aioclient_mock.mock_calls[-1][1]) == default_ota_url
    assert in_progress == [True]
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_INSTALLED_VERSION] == RELEASE_VERSION
    assert state.state == STATE_OFF
    assert UpdateEntityFeature.INSTALL in _features(hass, entity_id)


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_finished_by_device_registry(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    mock_github_latest_release: str,
) -> None:
    """Test the install finishes when the device registry reports a new version."""
    aioclient_mock.head(ESP8266_OTA_URL, status=200)
    entity_id, fake, config = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)

    def upgrade() -> None:
        config["sw"] = RELEASE_VERSION
        _discover(hass, config)

    fake.on_upgrade = upgrade
    await _install(hass, entity_id)

    assert hass.states.get(entity_id).attributes[ATTR_INSTALLED_VERSION] == (
        RELEASE_VERSION
    )


@pytest.mark.parametrize(
    ("hardware", "default_ota_url", "intermediate_versions"),
    [
        # ESP8266 with too little flash: tasmota-minimal of the new release
        (
            "ESP8266EX",
            ESP8266_OTA_URL,
            [f"{RELEASE_VERSION}(release-minimal)"],
        ),
        # ESP32 with a single OTA partition: safeboot from the factory flash,
        # which can have any version
        (
            "ESP32-S0WD",
            SOLO1_OTA_URL,
            ["14.3.0(release-safeboot)", f"{INSTALLED_VERSION}(release-safeboot)"],
        ),
    ],
)
@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_intermediate_image(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    mock_github_latest_release: str,
    hardware: str,
    default_ota_url: str,
    intermediate_versions: list[str],
) -> None:
    """Test a minimal or safeboot image during the device's upgrade is no result."""
    image = "solo1" if hardware.startswith("ESP32") else "tasmota"
    aioclient_mock.head(default_ota_url, status=200)
    entity_id, fake, _ = await _setup_device(
        hass,
        mqtt_mock,
        entity_registry,
        version=f"{INSTALLED_VERSION}(release-{image})",
        hardware=hardware,
        default_ota_url=default_ota_url,
    )
    await _online(hass, fake)

    task = _start_install(hass, entity_id)
    await _settle(hass)
    assert fake.commands[-1] == ("Upgrade", "1")

    for intermediate_version in intermediate_versions:
        # Booted into the intermediate image, which answers the STATUS2 poll
        fake.restart(intermediate_version)
        await _settle(hass)
        assert not task.done()
        assert _in_progress(hass, entity_id) is True
        assert UpdateEntityFeature.INSTALL in _features(hass, entity_id)

    fake.restart(f"{RELEASE_VERSION}(release-{image})")
    await task
    assert UpdateEntityFeature.INSTALL in _features(hass, entity_id)
    # The device registry shows the new version before discovery confirms it
    assert hass.states.get(entity_id).attributes[ATTR_INSTALLED_VERSION] == (
        RELEASE_VERSION
    )


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_same_version_after_restart(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    mock_github_latest_release: str,
) -> None:
    """Test an error when the device boots with the same version."""
    aioclient_mock.head(ESP8266_OTA_URL, status=200)
    entity_id, fake, _ = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)

    task = _start_install(hass, entity_id)
    await _settle(hass)
    # Neither a MQTT reconnect (LWT, STATUS2 with the old version) nor a
    # retained INFO1 is a restart
    fake.fire("tele/LWT", "Online")
    fake.fire("tele/LWT", "Online", retain=True)
    fake.fire("stat/STATUS2", _status2(fake.version, fake.hardware))
    fake.info1(retain=True)
    await _settle(hass)
    assert not task.done()

    fake.restart()
    with pytest.raises(HomeAssistantError) as exc_info:
        await task
    assert exc_info.value.translation_key == "same_version"
    assert exc_info.value.translation_placeholders == {"version": INSTALLED_VERSION}
    assert _in_progress(hass, entity_id) is False
    # The OtaUrl the device had is restored
    assert fake.commands[-1] == ("OtaUrl", CUSTOM_OTA_URL)
    assert fake.ota_url == CUSTOM_OTA_URL


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_timeout(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    mock_github_latest_release: str,
) -> None:
    """Test an error when the device does not come back with a new version."""
    aioclient_mock.head(ESP8266_OTA_URL, status=200)
    entity_id, fake, _ = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)

    task = _start_install(hass, entity_id)
    await _settle(hass)
    assert _in_progress(hass, entity_id) is True
    fake.fire("tele/LWT", "Offline")
    await _settle(hass)
    # The entity's availability does not follow the device during the update
    assert hass.states.get(entity_id).state == STATE_ON

    freezer.tick(INSTALL_TIMEOUT)
    async_fire_time_changed(hass)
    with pytest.raises(HomeAssistantError) as exc_info:
        await task
    assert exc_info.value.translation_key == "install_timeout"
    assert exc_info.value.translation_placeholders == {"minutes": "10"}
    assert _in_progress(hass, entity_id) is False


@pytest.mark.parametrize(
    "message",
    ["Failed Not Enough Space", "1 or >15.2.0 to upgrade"],
)
@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_upgrade_failed(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    mock_github_latest_release: str,
    message: str,
) -> None:
    """Test an error when the device reports a failed upgrade."""
    aioclient_mock.head(ESP8266_OTA_URL, status=200)
    entity_id, fake, _ = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)
    # Upgrade results outside of an install are ignored
    fake.fire("stat/UPGRADE", json.dumps({"Upgrade": message}))
    await hass.async_block_till_done()

    fake.on_upgrade = lambda: fake.fire(
        "stat/UPGRADE", json.dumps({"Upgrade": message})
    )
    with pytest.raises(HomeAssistantError) as exc_info:
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == "upgrade_failed"
    assert exc_info.value.translation_placeholders == {"message": message}
    assert fake.commands == [
        ("OtaUrl", ""),
        ("OtaUrl", "1"),
        ("Upgrade", "1"),
        ("OtaUrl", CUSTOM_OTA_URL),
    ]


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_upgrade_url_mismatch(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    mock_github_latest_release: str,
) -> None:
    """Test an error when the device downloads from another URL than checked."""
    aioclient_mock.head(ESP8266_OTA_URL, status=200)
    entity_id, fake, config = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)
    # A removed device stays in the discovery data, without config
    other = {**config, "mac": "00000049A3BD", "t": "other_plug"}
    _discover(hass, other)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{other['mac']}/config", "")
    await hass.async_block_till_done()
    fake.upgrade_url = CUSTOM_OTA_URL

    with pytest.raises(HomeAssistantError) as exc_info:
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == "upgrade_url_mismatch"
    assert exc_info.value.translation_placeholders == {"url": CUSTOM_OTA_URL}


@pytest.mark.parametrize(
    ("ignored", "commands"),
    [
        # No answer at all, the OtaUrl of the device is unknown
        ({"", "1"}, [("OtaUrl", "")]),
        # No answer to OtaUrl 1, which the device may still have acted on
        ({"1"}, [("OtaUrl", ""), ("OtaUrl", "1"), ("OtaUrl", CUSTOM_OTA_URL)]),
    ],
)
@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_no_ota_url_response(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    mock_github_latest_release: str,
    ignored: set[str],
    commands: list[tuple[str, str]],
) -> None:
    """Test an error when the device does not answer OtaUrl."""
    entity_id, fake, _ = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)
    fake.ignore_ota_url = ignored

    with (
        patch("homeassistant.components.tasmota.update.COMMAND_TIMEOUT", 0.01),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == "no_response"
    assert fake.commands == commands


@pytest.mark.parametrize(
    ("ota_url", "default_ota_url"),
    [
        # Typo in the OTA_URL of the official tasmota-AD build
        (CUSTOM_OTA_URL, "http://ota.tasmota.com/tasmota/release/tasmot-AD.bin.gz"),
        # ESP32 image for an ESP8266
        (CUSTOM_OTA_URL, "http://ota.tasmota.com/tasmota32/release/tasmota32.bin"),
        # Image of another variant
        (
            CUSTOM_OTA_URL,
            "http://ota.tasmota.com/tasmota/release/tasmota-sensors.bin.gz",
        ),
        (CUSTOM_OTA_URL, "http://example.com/tasmota/release/tasmota.bin.gz"),
        ("", "http://example.com/tasmota/release/tasmota.bin.gz"),
    ],
)
@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_unexpected_ota_url(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    mock_github_latest_release: str,
    ota_url: str,
    default_ota_url: str,
) -> None:
    """Test no upgrade when the device's default OtaUrl is not an official image."""
    entity_id, fake, _ = await _setup_device(
        hass,
        mqtt_mock,
        entity_registry,
        ota_url=ota_url,
        default_ota_url=default_ota_url,
    )
    await _online(hass, fake)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == "unexpected_ota_url"
    assert exc_info.value.translation_placeholders == {"url": default_ota_url}
    restore = [("OtaUrl", ota_url)] if ota_url else []
    assert fake.commands == [("OtaUrl", ""), ("OtaUrl", "1"), *restore]
    assert fake.ota_url == (ota_url or default_ota_url)
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    ("head_kwargs", "translation_key", "error"),
    [
        ({"status": 404}, "firmware_not_available", None),
        ({"status": 302}, "firmware_not_available", None),
        ({"exc": ClientError("Connection reset")}, "download_check_failed", None),
        ({"exc": TimeoutError()}, "download_check_failed", "TimeoutError"),
    ],
)
@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_firmware_not_downloadable(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    mock_github_latest_release: str,
    head_kwargs: dict[str, Any],
    translation_key: str,
    error: str | None,
) -> None:
    """Test no upgrade when the image can't be downloaded from ota.tasmota.com."""
    aioclient_mock.head(ESP8266_OTA_URL, **head_kwargs)
    entity_id, fake, _ = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders["url"] == ESP8266_OTA_URL
    if error:
        assert exc_info.value.translation_placeholders["error"] == error
    assert fake.commands == [
        ("OtaUrl", ""),
        ("OtaUrl", "1"),
        ("OtaUrl", CUSTOM_OTA_URL),
    ]


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_restore_ota_url_fails(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    mock_github_latest_release: str,
) -> None:
    """Test the install error is raised when restoring OtaUrl fails."""
    aioclient_mock.head(ESP8266_OTA_URL, status=404)
    entity_id, fake, _ = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)
    fake.ignore_ota_url = {CUSTOM_OTA_URL}

    with (
        patch("homeassistant.components.tasmota.update.COMMAND_TIMEOUT", 0.01),
        caplog.at_level(logging.WARNING),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == "firmware_not_available"
    assert f"could not restore OtaUrl {CUSTOM_OTA_URL}" in caplog.text


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_device_offline(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    mock_github_latest_release: str,
) -> None:
    """Test no commands are sent to an offline device."""
    entity_id, fake, _ = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)
    fake.fire("tele/LWT", "Offline")
    await hass.async_block_till_done()

    # The entity stays available, its availability follows the release lookup
    assert hass.states.get(entity_id).state == STATE_ON
    with pytest.raises(HomeAssistantError) as exc_info:
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == "device_offline"
    assert fake.commands == []


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_topic_shared(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_github_latest_release: str,
) -> None:
    """Test no commands are sent to a topic another device uses as well."""
    entity_id, fake, config = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)
    assert UpdateEntityFeature.INSTALL in _features(hass, entity_id)

    other = copy.deepcopy(config)
    other["mac"] = "00000049A3BD"
    _discover(hass, other)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(
        DOMAIN, f"topic_duplicated_{DEVICE_TOPIC}/cmnd/"
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == "topic_duplicated"
    assert fake.commands == []


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_firmware_unknown(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    mock_github_latest_release: str,
) -> None:
    """Test install refuses when the firmware is unknown or not supported."""
    entity_id, fake, _ = await _setup_device(hass, mqtt_mock, entity_registry)
    update_entity = hass.data[DATA_COMPONENT].get_entity(entity_id)

    with pytest.raises(ServiceValidationError) as exc_info:
        await update_entity.async_install(None, False)
    assert exc_info.value.translation_key == "install_not_supported"
    assert exc_info.value.translation_placeholders == {"version": "unknown"}

    fake.fire("stat/STATUS2", _status2("15.2.0(tasmota)", "ESP8266EX"))
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError) as exc_info:
        await update_entity.async_install(None, False)
    assert exc_info.value.translation_placeholders == {"version": "15.2.0"}
    assert fake.commands == []


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_interrupted_by_unload(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    mock_github_latest_release: str,
) -> None:
    """Test unloading aborts a running install and reloading restores the entity."""
    aioclient_mock.head(ESP8266_OTA_URL, status=200)
    entity_id, fake, config = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)

    task = _start_install(hass, entity_id)
    await _settle(hass)
    assert fake.commands[-1] == ("Upgrade", "1")

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    with pytest.raises(HomeAssistantError) as exc_info:
        await task
    assert exc_info.value.translation_key == "install_interrupted"
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # After a reload the entity polls the firmware details again
    fake.published.clear()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    _discover(hass, config)
    await hass.async_block_till_done()
    await _online(hass, fake)
    assert (f"{DEVICE_TOPIC}/cmnd/STATUS", "2") in fake.published
    assert UpdateEntityFeature.INSTALL in _features(hass, entity_id)


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_unloaded_during_download_check(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    mock_github_latest_release: str,
) -> None:
    """Test no upgrade is started when the entity is removed during the checks."""
    entity_id, fake, _ = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    async def unload_during_head(
        method: str, url: Any, data: Any
    ) -> AiohttpClientMockResponse:
        assert await hass.config_entries.async_unload(entry.entry_id)
        return AiohttpClientMockResponse(method, url, status=200)

    aioclient_mock.head(ESP8266_OTA_URL, side_effect=unload_during_head)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == "install_interrupted"
    assert fake.commands == [("OtaUrl", ""), ("OtaUrl", "1")]


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_follows_topic_change(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    mock_github_latest_release: str,
) -> None:
    """Test commands go to the new topic after the device topic was changed."""
    aioclient_mock.head(ESP8266_OTA_URL, status=200)
    entity_id, fake, config = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)

    # Unchanged discovery message
    _discover(hass, config)
    await hass.async_block_till_done()

    config["t"] = "kitchen_plug"
    _discover(hass, config)
    await hass.async_block_till_done()
    await _online(hass, fake)

    fake.on_upgrade = lambda: fake.restart(f"{RELEASE_VERSION}(release-tasmota)")
    fake.published.clear()
    await _install(hass, entity_id)
    assert fake.commands == [("OtaUrl", ""), ("OtaUrl", "1"), ("Upgrade", "1")]
    assert all(topic.startswith("kitchen_plug/") for topic, _ in fake.published)


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_removed_while_resubscribing(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    mock_github_latest_release: str,
) -> None:
    """Test no subscription is left when the entity is removed while resubscribing."""
    _, _, config = await _setup_device(hass, mqtt_mock, entity_registry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    subscribe = TasmotaUpdate.subscribe_topics
    unsubscribe = TasmotaUpdate.unsubscribe_topics
    unsubscribed: list[str] = []

    async def subscribe_and_unload(tasmota_update: TasmotaUpdate) -> None:
        await subscribe(tasmota_update)
        assert await hass.config_entries.async_unload(entry.entry_id)

    async def record_unsubscribe(tasmota_update: TasmotaUpdate) -> None:
        unsubscribed.append(tasmota_update.command_topic)
        await unsubscribe(tasmota_update)

    with (
        patch.object(
            TasmotaUpdate,
            "subscribe_topics",
            autospec=True,
            side_effect=subscribe_and_unload,
        ),
        patch.object(
            TasmotaUpdate,
            "unsubscribe_topics",
            autospec=True,
            side_effect=record_unsubscribe,
        ),
    ):
        config["t"] = "kitchen_plug"
        _discover(hass, config)
        await hass.async_block_till_done()

    # Once when the entity was removed, once more after the subscription
    assert unsubscribed == ["kitchen_plug/cmnd/", "kitchen_plug/cmnd/"]


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_older_version_after_restart(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    mock_github_latest_release: str,
) -> None:
    """Test an error when the device boots with an older version."""
    aioclient_mock.head(ESP8266_OTA_URL, status=200)
    entity_id, fake, _ = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)

    fake.on_upgrade = lambda: fake.restart("15.1.0(release-tasmota)")
    with pytest.raises(HomeAssistantError) as exc_info:
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == "unexpected_version"
    assert exc_info.value.translation_placeholders == {
        "version": "15.1.0",
        "previous": INSTALLED_VERSION,
    }


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_already_running(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    mock_github_latest_release: str,
) -> None:
    """Test a second install is refused while the first one runs."""
    aioclient_mock.head(ESP8266_OTA_URL, status=200)
    entity_id, fake, _ = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)

    task = _start_install(hass, entity_id)
    await _settle(hass)
    assert fake.commands[-1] == ("Upgrade", "1")

    # The update service sees in_progress and refuses
    with pytest.raises(HomeAssistantError) as exc_info:
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == "update_in_progress"
    # A direct call is refused as well
    update_entity = hass.data[DATA_COMPONENT].get_entity(entity_id)
    with pytest.raises(HomeAssistantError) as exc_info:
        await update_entity.async_install(None, False)
    assert exc_info.value.translation_key == "install_in_progress"
    assert fake.commands.count(("Upgrade", "1")) == 1
    # The running install is still shown
    assert _in_progress(hass, entity_id) is True

    fake.restart(f"{RELEASE_VERSION}(release-tasmota)")
    await task
    assert _in_progress(hass, entity_id) is False


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_withdrawn_when_deep_sleep_enabled(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    mock_github_latest_release: str,
) -> None:
    """Test install is withdrawn when discovery reports deep sleep."""
    entity_id, fake, config = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)
    assert UpdateEntityFeature.INSTALL in _features(hass, entity_id)

    config["dslp"] = 1
    _discover(hass, config)
    await hass.async_block_till_done()
    assert UpdateEntityFeature.INSTALL not in _features(hass, entity_id)


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_topic_changed(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    mock_github_latest_release: str,
) -> None:
    """Test no commands are sent when discovery rejected a new topic."""
    entity_id, fake, config = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)
    other = copy.deepcopy(config)
    other["mac"] = "00000049A3BD"
    other["t"] = "kitchen_plug"
    _discover(hass, other)
    await hass.async_block_till_done()

    # The device moves to the topic of the other device, discovery rejects it
    config["t"] = "kitchen_plug"
    _discover(hass, config)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as exc_info:
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == "topic_changed"
    assert not [p for p in fake.published if "/cmnd/OtaUrl" in p[0]]


@pytest.mark.parametrize(
    ("config_update", "command_topic"),
    [
        ({"t": "tasmotas"}, "tasmotas/cmnd/"),
        # Below the group topic, devices subscribe to cmnd/tasmotas/#
        (
            {"ft": "%prefix%/%topic%/", "t": "tasmotas/kitchen"},
            "cmnd/tasmotas/kitchen/",
        ),
    ],
)
@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_group_topic(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    mock_github_latest_release: str,
    config_update: dict[str, str],
    command_topic: str,
) -> None:
    """Test no commands are sent to a topic covered by Tasmota's group topic."""
    entity_id, fake, _ = await _setup_device(
        hass, mqtt_mock, entity_registry, config_update=config_update
    )
    await _online(hass, fake)
    assert UpdateEntityFeature.INSTALL in _features(hass, entity_id)

    with pytest.raises(ServiceValidationError) as exc_info:
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == "topic_group"
    assert exc_info.value.translation_placeholders == {"topic": command_topic}
    assert fake.commands == []


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_topic_shared_during_download_check(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    mock_github_latest_release: str,
) -> None:
    """Test no upgrade when another device takes the topic during the checks."""
    entity_id, fake, config = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)
    other = copy.deepcopy(config)
    other["mac"] = "00000049A3BD"

    async def other_device_during_head(
        method: str, url: Any, data: Any
    ) -> AiohttpClientMockResponse:
        _discover(hass, other)
        await _settle(hass)
        return AiohttpClientMockResponse(method, url, status=200)

    aioclient_mock.head(ESP8266_OTA_URL, side_effect=other_device_during_head)

    with pytest.raises(ServiceValidationError) as exc_info:
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == "topic_duplicated"
    # Neither Upgrade nor the OtaUrl restore go to the shared topic
    assert fake.commands == [("OtaUrl", ""), ("OtaUrl", "1")]


@pytest.mark.parametrize(
    ("restart_version", "log"),
    [
        (f"{RELEASE_VERSION}(release-tasmota)", None),
        (
            f"{INSTALLED_VERSION}(release-tasmota)",
            "firmware install failed: The device restarted, but still runs",
        ),
    ],
)
@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_continues_when_caller_cancelled(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    mock_github_latest_release: str,
    restart_version: str,
    log: str | None,
) -> None:
    """Test the install is followed when the calling action is cancelled."""
    aioclient_mock.head(ESP8266_OTA_URL, status=200)
    entity_id, fake, _ = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)

    task = _start_install(hass, entity_id)
    await _settle(hass)
    assert fake.commands[-1] == ("Upgrade", "1")
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await _settle(hass)
    # The device is flashing, the install is still followed
    assert _in_progress(hass, entity_id) is True

    with caplog.at_level(logging.WARNING):
        fake.restart(restart_version)
        await _settle(hass)
        await hass.async_block_till_done()
    assert _in_progress(hass, entity_id) is False
    if log:
        assert log in caplog.text
    else:
        assert "firmware install failed" not in caplog.text


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_topic_overlap(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    mock_github_latest_release: str,
) -> None:
    """Test no commands are sent when another device subscribes to them too."""
    layout = {"ft": "%prefix%/%topic%/"}
    entity_id, fake, config = await _setup_device(
        hass,
        mqtt_mock,
        entity_registry,
        config_update={**layout, "t": "plug/kitchen"},
    )
    other = copy.deepcopy(config)
    other.update({"mac": "00000049A3BD", "t": "plug"})
    _discover(hass, other)
    await hass.async_block_till_done()
    await _online(hass, fake)
    assert UpdateEntityFeature.INSTALL in _features(hass, entity_id)

    with pytest.raises(ServiceValidationError) as exc_info:
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == "topic_overlap"
    assert exc_info.value.translation_placeholders == {
        "topic": "cmnd/plug/kitchen/",
        "other": "cmnd/plug/",
    }
    assert not [p for p in fake.published if "OtaUrl" in p[0] or "Upgrade" in p[0]]


@pytest.mark.parametrize(
    ("change", "translation_key"),
    [
        ("custom_build", "install_not_supported"),
        ("newer_status2", "firmware_changed"),
        ("newer_discovery", "firmware_changed"),
        ("offline", "device_offline"),
    ],
)
@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_device_changed_during_download_check(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    mock_github_latest_release: str,
    change: str,
    translation_key: str,
) -> None:
    """Test no upgrade when the device changes while its URL is checked."""
    entity_id, fake, config = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)

    async def device_changes_during_head(
        method: str, url: Any, data: Any
    ) -> AiohttpClientMockResponse:
        if change == "custom_build":
            fake.fire("stat/STATUS2", _status2("15.2.0(tasmota)", "ESP8266EX"))
        elif change == "newer_status2":
            fake.fire("stat/STATUS2", _status2("15.3.0(release-tasmota)", "ESP8266EX"))
        elif change == "newer_discovery":
            _discover(hass, {**config, "sw": "15.3.0"})
        else:
            fake.fire("tele/LWT", "Offline")
        await _settle(hass)
        return AiohttpClientMockResponse(method, url, status=200)

    aioclient_mock.head(ESP8266_OTA_URL, side_effect=device_changes_during_head)

    with pytest.raises(HomeAssistantError) as exc_info:
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == translation_key
    assert ("Upgrade", "1") not in fake.commands
    assert fake.commands[-1] == ("OtaUrl", CUSTOM_OTA_URL)


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_restore_publish_fails(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    mock_github_latest_release: str,
) -> None:
    """Test the install error is kept when the OtaUrl restore can't be published."""
    aioclient_mock.head(ESP8266_OTA_URL, status=404)
    entity_id, fake, _ = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)
    fake.fail_publish = {("OtaUrl", CUSTOM_OTA_URL)}

    with (
        caplog.at_level(logging.WARNING),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == "firmware_not_available"
    assert f"could not restore OtaUrl {CUSTOM_OTA_URL}" in caplog.text


@pytest.mark.parametrize(
    "mock_github_latest_release", [f"v{RELEASE_VERSION}"], indirect=True
)
async def test_install_removed_before_ota_url_reset(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    mock_github_latest_release: str,
) -> None:
    """Test OtaUrl is not reset when the entity is removed while it is read."""
    entity_id, fake, _ = await _setup_device(hass, mqtt_mock, entity_registry)
    await _online(hass, fake)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    async def unload_while_reading(
        tasmota_update: TasmotaUpdate, timeout: float
    ) -> str:
        assert await hass.config_entries.async_unload(entry.entry_id)
        return CUSTOM_OTA_URL

    with (
        patch.object(
            TasmotaUpdate,
            "get_ota_url",
            autospec=True,
            side_effect=unload_while_reading,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await _install(hass, entity_id)
    assert exc_info.value.translation_key == "install_interrupted"
    assert fake.commands == []
