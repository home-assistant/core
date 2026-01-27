"""Test Kostal Plenticore diagnostics."""

from unittest.mock import Mock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.common import ANY, MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_plenticore_client: Mock,
    init_integration: MockConfigEntry,
) -> None:
    """Test config entry diagnostics."""

    # set some test process data for the diagnostics output
    mock_plenticore_client.get_process_data.return_value = {
        "devices:local": ["HomeGrid_P", "HomePv_P"]
    }

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == {
        "config_entry": {
            "entry_id": "2ab8dd92a62787ddfe213a67e09406bd",
            "version": 1,
            "minor_version": 1,
            "domain": "kostal_plenticore",
            "title": "scb",
            "data": {"host": "192.168.1.2", "password": REDACTED},
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "unique_id": None,
            "disabled_by": None,
            "created_at": ANY,
            "modified_at": ANY,
            "discovery_keys": {},
            "subentries": [],
        },
        "client": {
            "version": "api_version='0.2.0' hostname='scb' name='PUCK RESTful API' sw_version='01.16.05025'",
            "me": "is_locked=False is_active=True is_authenticated=True permissions=[] is_anonymous=False role='USER'",
            "available_process_data": {"devices:local": ["HomeGrid_P", "HomePv_P"]},
            "available_settings_data": {
                "devices:local": [
                    "min='5' max='100' default=None access='readwrite' unit='%' id='Battery:MinSoc' type='byte'",
                    "min='50' max='38000' default=None access='readwrite' unit='W' id='Battery:MinHomeComsumption' type='byte'",
                ],
                "scb:network": [
                    "min='1' max='63' default=None access='readwrite' unit=None id='Hostname' type='string'"
                ],
            },
        },
        "configuration": {
            "devices:local": {
                "Properties:StringCnt": "2",
                "Properties:String0Features": "1",
                "Properties:String1Features": "1",
            },
        },
        "device": {
            "configuration_url": "http://192.168.1.2",
            "identifiers": "**REDACTED**",
            "manufacturer": "Kostal",
            "model": "PLENTICORE plus 10",
            "name": "scb",
            "sw_version": "IOC: 01.45 MC: 01.46",
        },
    }


async def test_entry_diagnostics_invalid_string_count(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_plenticore_client: Mock,
    mock_get_setting_values: Mock,
    init_integration: MockConfigEntry,
) -> None:
    """Test config entry diagnostics if string count is invalid."""

    # set some test process data for the diagnostics output
    mock_plenticore_client.get_process_data.return_value = {
        "devices:local": ["HomeGrid_P", "HomePv_P"]
    }

    mock_get_setting_values["devices:local"]["Properties:StringCnt"] = "invalid"

    diagnostic_data = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )

    assert diagnostic_data["configuration"] == {
        "devices:local": {"Properties:StringCnt": "invalid"}
    }
