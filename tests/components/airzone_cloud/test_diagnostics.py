"""The diagnostics tests for the Airzone Cloud platform."""

from unittest.mock import patch

from aioairzone_cloud.const import (
    API_DEVICE_ID,
    API_DEVICES,
    API_GROUP_ID,
    API_GROUPS,
    API_WS_ID,
    RAW_DEVICES_CONFIG,
    RAW_DEVICES_STATUS,
    RAW_INSTALLATIONS,
    RAW_INSTALLATIONS_LIST,
    RAW_WEBSERVERS,
)
from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.airzone_cloud.const import DOMAIN
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant

from .util import CONFIG, WS_ID, WS_ID_AIDOO, WS_ID_AIDOO_PRO, async_init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

RAW_DATA_MOCK = {
    RAW_DEVICES_CONFIG: {
        "dev1": {},
        "dev2": {},
        "dev3": {},
    },
    RAW_DEVICES_STATUS: {
        "dev1": {},
        "dev2": {},
        "dev3": {},
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
                {
                    API_GROUP_ID: "grp2",
                    API_DEVICES: [
                        {
                            API_DEVICE_ID: "dev2",
                            API_WS_ID: WS_ID_AIDOO,
                        },
                    ],
                },
                {
                    API_GROUP_ID: "grp3",
                    API_DEVICES: [
                        {
                            API_DEVICE_ID: "dev3",
                            API_WS_ID: WS_ID_AIDOO_PRO,
                        },
                    ],
                },
            ],
            "plugins": {
                "schedules": {
                    "calendar_ws_ids": [
                        WS_ID,
                        WS_ID_AIDOO,
                        WS_ID_AIDOO_PRO,
                    ],
                },
            },
        },
    },
    RAW_INSTALLATIONS_LIST: {},
    RAW_WEBSERVERS: {
        WS_ID: {},
        WS_ID_AIDOO: {},
        WS_ID_AIDOO_PRO: {},
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
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await async_init_integration(hass)

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.raw_data",
        return_value=RAW_DATA_MOCK,
    ):
        result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        assert result == snapshot(exclude=props("created_at", "modified_at"))
