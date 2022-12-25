"""Test the Data Sources integration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import Mock

import pytest
import voluptuous as vol

from homeassistant.components.data_source import (
    InvalidDataSourceConfig,
    async_get_data_source,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from tests.common import mock_platform

TEST_DOMAIN = "test"


async def mock_data_source(
    hass: HomeAssistant, method: Callable[[HomeAssistant, ConfigType], Any]
) -> None:
    """Register a mock data source."""


async def test_data_source(hass: HomeAssistant) -> None:
    """Test a mock data source platform."""

    hass.config.components.add(TEST_DOMAIN)

    async def provide_data(hass: HomeAssistant, config: ConfigType) -> Any:
        return ["a", "b", "c"]

    mock_platform(hass, f"{TEST_DOMAIN}.data_source", Mock(async_get_data=provide_data))

    assert await async_get_data_source(hass, TEST_DOMAIN, {}) == ["a", "b", "c"]


async def test_invalid_domain(hass: HomeAssistant) -> None:
    """Test loading a data source for a domain that does not exist."""

    with pytest.raises(
        InvalidDataSourceConfig, match="Integration 'invalid-domain' not found"
    ):
        await async_get_data_source(hass, "invalid-domain", {})


async def test_invalid_platform(hass: HomeAssistant) -> None:
    """Test loading a data source for a domain that does not support data sources."""

    hass.config.components.add(TEST_DOMAIN)
    mock_platform(hass, f"{TEST_DOMAIN}.sensor", Mock())

    with pytest.raises(
        InvalidDataSourceConfig,
        match="Integration 'test' does not support data sources",
    ):
        await async_get_data_source(hass, TEST_DOMAIN, {})


async def test_invalid_platform_implementation(hass: HomeAssistant) -> None:
    """Test loading a data source with an incorrect platform implementation."""

    hass.config.components.add(TEST_DOMAIN)

    platform = Mock()
    del platform.async_get_data  # return False on hasattr

    mock_platform(hass, f"{TEST_DOMAIN}.data_source", platform)

    with pytest.raises(
        InvalidDataSourceConfig, match="Integration 'test' does not async_get_data"
    ):
        await async_get_data_source(hass, TEST_DOMAIN, {})


async def test_invalid_config(hass: HomeAssistant) -> None:
    """Test an invalid data source schema."""

    hass.config.components.add(TEST_DOMAIN)

    async def provide_data(hass: HomeAssistant, config: ConfigType) -> Any:
        return ["a", "b", "c"]

    platform = Mock()
    platform.DATA_SOURCE_SCHEMA = vol.Schema({vol.Required("example"): str})
    platform.async_get_data = provide_data

    mock_platform(hass, f"{TEST_DOMAIN}.data_source", platform)

    with pytest.raises(vol.Invalid, match="required key not provided"):
        await async_get_data_source(hass, TEST_DOMAIN, {})
