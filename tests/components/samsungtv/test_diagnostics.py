"""Test samsungtv diagnostics."""

from unittest.mock import Mock

import pytest
from samsungtvws.exceptions import HttpApiError

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from . import setup_samsungtv_entry
from .const import (
    MOCK_ENTRY_WS_WITH_MAC,
    MOCK_ENTRYDATA_ENCRYPTED_WS,
    SAMPLE_DEVICE_INFO_UE48JU6400,
    SAMPLE_DEVICE_INFO_WIFI,
)

from tests.common import ANY
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("remotews", "rest_api")
async def test_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test config entry diagnostics."""
    config_entry = await setup_samsungtv_entry(hass, MOCK_ENTRY_WS_WITH_MAC)

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "created_at": ANY,
            "data": {
                "host": "fake_host",
                "ip_address": "test",
                "mac": "aa:bb:cc:dd:ee:ff",
                "method": "websocket",
                "model": "82GXARRS",
                "name": "fake",
                "port": 8002,
                "token": REDACTED,
            },
            "disabled_by": None,
            "discovery_keys": {},
            "domain": "samsungtv",
            "entry_id": "123456",
            "minor_version": 2,
            "modified_at": ANY,
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "subentries": [],
            "title": "Mock Title",
            "unique_id": "any",
            "version": 2,
        },
        "device_info": SAMPLE_DEVICE_INFO_WIFI,
    }


@pytest.mark.usefixtures("remoteencws")
async def test_entry_diagnostics_encrypted(
    hass: HomeAssistant, rest_api: Mock, hass_client: ClientSessionGenerator
) -> None:
    """Test config entry diagnostics."""
    rest_api.rest_device_info.return_value = SAMPLE_DEVICE_INFO_UE48JU6400
    config_entry = await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "created_at": ANY,
            "data": {
                "host": "fake_host",
                "ip_address": "test",
                "mac": "aa:bb:cc:dd:ee:ff",
                "method": "encrypted",
                "model": "UE48JU6400",
                "name": "fake",
                "port": 8000,
                "token": REDACTED,
                "session_id": REDACTED,
            },
            "disabled_by": None,
            "discovery_keys": {},
            "domain": "samsungtv",
            "entry_id": "123456",
            "minor_version": 2,
            "modified_at": ANY,
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "subentries": [],
            "title": "Mock Title",
            "unique_id": "any",
            "version": 2,
        },
        "device_info": SAMPLE_DEVICE_INFO_UE48JU6400,
    }


@pytest.mark.usefixtures("remoteencws")
async def test_entry_diagnostics_encrypte_offline(
    hass: HomeAssistant, rest_api: Mock, hass_client: ClientSessionGenerator
) -> None:
    """Test config entry diagnostics."""
    rest_api.rest_device_info.side_effect = HttpApiError
    config_entry = await setup_samsungtv_entry(hass, MOCK_ENTRYDATA_ENCRYPTED_WS)

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "created_at": ANY,
            "data": {
                "host": "fake_host",
                "ip_address": "test",
                "mac": "aa:bb:cc:dd:ee:ff",
                "method": "encrypted",
                "name": "fake",
                "port": 8000,
                "token": REDACTED,
                "session_id": REDACTED,
            },
            "disabled_by": None,
            "discovery_keys": {},
            "domain": "samsungtv",
            "entry_id": "123456",
            "minor_version": 2,
            "modified_at": ANY,
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "subentries": [],
            "title": "Mock Title",
            "unique_id": "any",
            "version": 2,
        },
        "device_info": None,
    }
