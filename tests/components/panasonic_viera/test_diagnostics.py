"""Tests for the diagnostics data provided by Panasonic Viera."""

from unittest.mock import Mock
from urllib.error import URLError

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.panasonic_viera.const import (
    ATTR_DEVICE_INFO,
    ATTR_UDN,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from .conftest import MOCK_CONFIG_DATA, MOCK_DEVICE_INFO

# The description of a 2012 TV as served on nrc/ddd.xml
MOCK_NRC_DEVICE_INFO = {
    "deviceType": "urn:panasonic-com:device:p00RemoteController:1",
    "friendlyName": "VIERA ST50 Series",
    "manufacturer": "Panasonic",
    "modelName": "Panasonic VIErA",
    "UDN": "uuid:4D454930-0200-1000-8001-D8AFF1123456",
    "viera:X_DMRUDN": "uuid:4D454930-0100-1000-8001-D8AFF1123456",
    "viera:X_NRCUDN": "uuid:4D454930-0200-1000-8001-D8AFF1123456",
    "viera:X_VERSION": "NRC-2.00",
    "viera:X_DEVICE_TYPE": "DTV",
    "viera:X_KEY_TYPE": "PAL-6,PAL-1",
    "viera:X_NRCCAP": "VR_DMR,VR_GPAD,VR_VECTOR,VR_BROWSER",
    "serviceList": {
        "service": {
            "serviceType": "urn:panasonic-com:service:p00NetworkControl:1",
            "serviceId": "urn:upnp-org:serviceId:p00NetworkControl",
            "SCPDURL": "/nrc/sdd_0.xml",
            "controlURL": "/nrc/control_0",
            "eventSubURL": "/nrc/event_0",
        }
    },
}


@pytest.mark.parametrize(
    "get_device_info",
    [
        pytest.param(Mock(return_value=MOCK_NRC_DEVICE_INFO), id="tv_reachable"),
        pytest.param(Mock(side_effect=URLError("Host is unreachable")), id="tv_off"),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_remote: Mock,
    get_device_info: Mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics of a config entry."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_DEVICE_INFO[ATTR_UDN],
        data={**MOCK_CONFIG_DATA, ATTR_DEVICE_INFO: MOCK_DEVICE_INFO},
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    # The setup is done, the diagnostics fetch the description served now
    mock_remote.get_device_info = get_device_info

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_entry
    ) == snapshot(exclude=props("created_at", "modified_at", "entry_id"))
