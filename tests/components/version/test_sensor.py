"""The test for the version sensor platform."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from pyhaversion import HaVersionChannel, HaVersionSource
from pyhaversion.exceptions import HaVersionException
import pytest

from homeassistant.components.version.const import (
    CONF_BETA,
    CONF_CHANNEL,
    CONF_IMAGE,
    CONF_VERSION_SOURCE,
    DEFAULT_NAME_LATEST,
    DOMAIN,
    VERSION_SOURCE_DOCKER_HUB,
    VERSION_SOURCE_VERSIONS,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import (
    MOCK_VERSION,
    MOCK_VERSION_DATA,
    TEST_DEFAULT_IMPORT_CONFIG,
    mock_get_version_update,
    setup_version_integration,
)


async def async_setup_sensor_wrapper(
    hass: HomeAssistant, config: dict[str, Any]
) -> ConfigEntry:
    """Set up the Version sensor platform."""
    with patch(
        "pyhaversion.HaVersion.get_version",
        return_value=(MOCK_VERSION, MOCK_VERSION_DATA),
    ):
        assert await async_setup_component(
            hass, "sensor", {"sensor": {"platform": DOMAIN, **config}}
        )
        await hass.async_block_till_done()

    config_entries = hass.config_entries.async_entries(DOMAIN)
    config_entry = config_entries[-1]
    assert config_entry.source == "import"
    return config_entry


async def test_version_sensor(hass: HomeAssistant):
    """Test the Version sensor with different sources."""
    await setup_version_integration(hass)

    state = hass.states.get("sensor.local_installation")
    assert state.state == MOCK_VERSION
    assert "source" not in state.attributes
    assert "channel" not in state.attributes


async def test_update(hass: HomeAssistant, caplog: pytest.LogCaptureFixture):
    """Test updates."""
    await setup_version_integration(hass)
    assert hass.states.get("sensor.local_installation").state == MOCK_VERSION

    await mock_get_version_update(hass, version="1970.1.1")
    assert hass.states.get("sensor.local_installation").state == "1970.1.1"

    assert "Error fetching version data" not in caplog.text
    await mock_get_version_update(hass, side_effect=HaVersionException)
    assert hass.states.get("sensor.local_installation").state == "unavailable"
    assert "Error fetching version data" in caplog.text


@pytest.mark.parametrize(
    "yaml,converted",
    (
        (
            {},
            TEST_DEFAULT_IMPORT_CONFIG,
        ),
        (
            {CONF_NAME: "test"},
            {**TEST_DEFAULT_IMPORT_CONFIG, CONF_NAME: "test"},
        ),
        (
            {CONF_SOURCE: "hassio", CONF_IMAGE: "odroid-n2"},
            {
                **TEST_DEFAULT_IMPORT_CONFIG,
                CONF_NAME: DEFAULT_NAME_LATEST,
                CONF_SOURCE: HaVersionSource.SUPERVISOR,
                CONF_VERSION_SOURCE: VERSION_SOURCE_VERSIONS,
                CONF_IMAGE: "odroid-n2",
            },
        ),
        (
            {CONF_SOURCE: "docker"},
            {
                **TEST_DEFAULT_IMPORT_CONFIG,
                CONF_NAME: DEFAULT_NAME_LATEST,
                CONF_SOURCE: HaVersionSource.CONTAINER,
                CONF_VERSION_SOURCE: VERSION_SOURCE_DOCKER_HUB,
            },
        ),
        (
            {CONF_BETA: True},
            {
                **TEST_DEFAULT_IMPORT_CONFIG,
                CONF_CHANNEL: HaVersionChannel.BETA,
            },
        ),
        (
            {CONF_SOURCE: "container", CONF_IMAGE: "odroid-n2"},
            {
                **TEST_DEFAULT_IMPORT_CONFIG,
                CONF_NAME: DEFAULT_NAME_LATEST,
                CONF_SOURCE: HaVersionSource.CONTAINER,
                CONF_VERSION_SOURCE: VERSION_SOURCE_DOCKER_HUB,
                CONF_IMAGE: "odroid-n2-homeassistant",
            },
        ),
    ),
)
async def test_config_import(
    hass: HomeAssistant, yaml: dict[str, Any], converted: dict[str, Any]
) -> None:
    """Test importing YAML configuration."""
    config_entry = await async_setup_sensor_wrapper(hass, yaml)
    assert config_entry.data == converted
