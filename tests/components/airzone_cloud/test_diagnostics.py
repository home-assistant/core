"""The diagnostics tests for the Airzone Cloud platform."""

from unittest.mock import patch

from aioairzone_cloud.const import (
    API_DEVICE_ID,
    API_DEVICES,
    API_GROUP_ID,
    API_GROUPS,
    API_WS_ID,
    AZD_AIDOOS,
    AZD_GROUPS,
    AZD_INSTALLATIONS,
    AZD_SYSTEMS,
    AZD_WEBSERVERS,
    AZD_ZONES,
    RAW_DEVICES_CONFIG,
    RAW_DEVICES_STATUS,
    RAW_INSTALLATIONS,
    RAW_INSTALLATIONS_LIST,
    RAW_WEBSERVERS,
)

from homeassistant.components.airzone_cloud.const import DOMAIN
from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .util import CONFIG, WS_ID, async_init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

RAW_DATA_MOCK = {
    RAW_DEVICES_CONFIG: {
        "dev1": {},
    },
    RAW_DEVICES_STATUS: {
        "dev1": {},
    },
    RAW_INSTALLATIONS: {
        CONFIG[CONF_ID]: {
            API_GROUPS: [
                {
                    API_GROUP_ID: "grp1",
                    API_DEVICES: [
                        {
                            API_DEVICE_ID: "dev1",
                            API_WS_ID: WS_ID,
                        },
                    ],
                },
            ],
            "plugins": {
                "schedules": {
                    "calendar_ws_ids": [
                        WS_ID,
                    ],
                },
            },
        },
    },
    RAW_INSTALLATIONS_LIST: {},
    RAW_WEBSERVERS: {
        WS_ID: {},
    },
    "test_cov": {
        "1": None,
        "2": ["foo", "bar"],
        "3": [
            [
                "foo",
                "bar",
            ],
        ],
    },
}


async def test_config_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test config entry diagnostics."""
    await async_init_integration(hass)
    assert hass.data[DOMAIN]

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.raw_data",
        return_value=RAW_DATA_MOCK,
    ):
        diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert list(diag["api_data"]) >= list(RAW_DATA_MOCK)
    assert "dev1" not in diag["api_data"][RAW_DEVICES_CONFIG]
    assert "device1" in diag["api_data"][RAW_DEVICES_CONFIG]
    assert (
        diag["api_data"][RAW_INSTALLATIONS]["installation1"][API_GROUPS][0][
            API_GROUP_ID
        ]
        == "group1"
    )
    assert "inst1" not in diag["api_data"][RAW_INSTALLATIONS]
    assert "installation1" in diag["api_data"][RAW_INSTALLATIONS]
    assert WS_ID not in diag["api_data"][RAW_WEBSERVERS]
    assert "webserver1" in diag["api_data"][RAW_WEBSERVERS]

    assert (
        diag["config_entry"].items()
        >= {
            "data": {
                CONF_ID: "installation1",
                CONF_PASSWORD: REDACTED,
                CONF_USERNAME: REDACTED,
            },
            "domain": DOMAIN,
            "unique_id": "installation1",
        }.items()
    )

    assert list(diag["coord_data"]) >= [
        AZD_AIDOOS,
        AZD_GROUPS,
        AZD_INSTALLATIONS,
        AZD_SYSTEMS,
        AZD_WEBSERVERS,
        AZD_ZONES,
    ]
