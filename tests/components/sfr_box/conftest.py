"""Provide common SFR Box fixtures."""
from collections.abc import Generator
import json
from unittest.mock import patch

import pytest
from sfrbox_api.models import DslInfo, SystemInfo

from homeassistant.components.sfr_box.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="config_entry")
def get_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Create and register mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={CONF_HOST: "192.168.0.1"},
        unique_id="e4:5d:51:00:11:22",
        options={},
        entry_id="123456",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(name="config_entry_with_auth")
def get_config_entry_with_auth(hass: HomeAssistant) -> ConfigEntry:
    """Create and register mock config entry."""
    config_entry_with_auth = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_HOST: "192.168.0.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
        unique_id="e4:5d:51:00:11:23",
        options={},
        entry_id="1234567",
    )
    config_entry_with_auth.add_to_hass(hass)
    return config_entry_with_auth


@pytest.fixture
def system_get_info() -> Generator[SystemInfo, None, None]:
    """Fixture for SFRBox.system_get_info."""
    system_info = SystemInfo(**json.loads(load_fixture("system_getInfo.json", DOMAIN)))
    with patch(
        "homeassistant.components.sfr_box.coordinator.SFRBox.system_get_info",
        return_value=system_info,
    ):
        yield system_info


@pytest.fixture
def dsl_get_info() -> Generator[DslInfo, None, None]:
    """Fixture for SFRBox.dsl_get_info."""
    dsl_info = DslInfo(**json.loads(load_fixture("dsl_getInfo.json", DOMAIN)))
    with patch(
        "homeassistant.components.sfr_box.coordinator.SFRBox.dsl_get_info",
        return_value=dsl_info,
    ):
        yield dsl_info
