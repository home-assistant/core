"""Test deCONZ gateway."""

from unittest.mock import patch

from pydeconz.websocket import State
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components import ssdp
from homeassistant.components.deconz.config_flow import DECONZ_MANUFACTURERURL
from homeassistant.components.deconz.const import DOMAIN as DECONZ_DOMAIN
from homeassistant.components.ssdp import (
    ATTR_UPNP_MANUFACTURER_URL,
    ATTR_UPNP_SERIAL,
    ATTR_UPNP_UDN,
)
from homeassistant.config_entries import SOURCE_SSDP
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import BRIDGE_ID

from tests.common import MockConfigEntry


async def test_device_registry_entry(
    config_entry_setup: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Successful setup."""
    device_entry = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, config_entry_setup.unique_id)}
    )
    assert device_entry == snapshot


@pytest.mark.parametrize(
    "sensor_payload",
    [
        {
            "name": "presence",
            "type": "ZHAPresence",
            "state": {"presence": False},
            "config": {"on": True, "reachable": True},
            "uniqueid": "00:00:00:00:00:00:00:00-00",
        }
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_connection_status_signalling(
    hass: HomeAssistant, mock_websocket_state
) -> None:
    """Make sure that connection status triggers a dispatcher send."""
    assert hass.states.get("binary_sensor.presence").state == STATE_OFF

    await mock_websocket_state(State.RETRYING)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.presence").state == STATE_UNAVAILABLE

    await mock_websocket_state(State.RUNNING)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.presence").state == STATE_OFF


async def test_update_address(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Make sure that connection status triggers a dispatcher send."""
    assert config_entry_setup.data["host"] == "1.2.3.4"

    with (
        patch(
            "homeassistant.components.deconz.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch("pydeconz.gateway.WSClient") as ws_mock,
    ):
        await hass.config_entries.flow.async_init(
            DECONZ_DOMAIN,
            data=ssdp.SsdpServiceInfo(
                ssdp_st="mock_st",
                ssdp_usn="mock_usn",
                ssdp_location="http://2.3.4.5:80/",
                upnp={
                    ATTR_UPNP_MANUFACTURER_URL: DECONZ_MANUFACTURERURL,
                    ATTR_UPNP_SERIAL: BRIDGE_ID,
                    ATTR_UPNP_UDN: "uuid:456DEF",
                },
            ),
            context={"source": SOURCE_SSDP},
        )
        await hass.async_block_till_done()

    assert ws_mock.call_args[0][1] == "2.3.4.5"
    assert config_entry_setup.data["host"] == "2.3.4.5"
    assert len(mock_setup_entry.mock_calls) == 1
