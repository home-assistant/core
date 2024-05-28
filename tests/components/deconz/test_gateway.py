"""Test deCONZ gateway."""

from copy import deepcopy
from unittest.mock import patch

import pydeconz
from pydeconz.websocket import State
import pytest

from homeassistant.components import ssdp
from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.deconz.config_flow import DECONZ_MANUFACTURERURL
from homeassistant.components.deconz.const import DOMAIN as DECONZ_DOMAIN
from homeassistant.components.deconz.errors import AuthenticationRequired, CannotConnect
from homeassistant.components.deconz.hub import DeconzHub, get_deconz_api
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.siren import DOMAIN as SIREN_DOMAIN
from homeassistant.components.ssdp import (
    ATTR_UPNP_MANUFACTURER_URL,
    ATTR_UPNP_SERIAL,
    ATTR_UPNP_UDN,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_HASSIO, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONTENT_TYPE_JSON,
    STATE_OFF,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

API_KEY = "1234567890ABCDEF"
BRIDGEID = "01234E56789A"
HOST = "1.2.3.4"
PORT = 80

DEFAULT_URL = f"http://{HOST}:{PORT}/api/{API_KEY}"

ENTRY_CONFIG = {CONF_API_KEY: API_KEY, CONF_HOST: HOST, CONF_PORT: PORT}

ENTRY_OPTIONS = {}

DECONZ_CONFIG = {
    "bridgeid": BRIDGEID,
    "ipaddress": HOST,
    "mac": "00:11:22:33:44:55",
    "modelid": "deCONZ",
    "name": "deCONZ mock gateway",
    "sw_version": "2.05.69",
    "uuid": "1234",
    "websocketport": 1234,
}

DECONZ_WEB_REQUEST = {
    "config": DECONZ_CONFIG,
    "groups": {},
    "lights": {},
    "sensors": {},
}


def mock_deconz_request(aioclient_mock, config, data):
    """Mock a deCONZ get request."""
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    api_key = config[CONF_API_KEY]

    aioclient_mock.get(
        f"http://{host}:{port}/api/{api_key}",
        json=deepcopy(data),
        headers={"content-type": CONTENT_TYPE_JSON},
    )


def mock_deconz_put_request(aioclient_mock, config, path):
    """Mock a deCONZ put request."""
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    api_key = config[CONF_API_KEY]

    aioclient_mock.put(
        f"http://{host}:{port}/api/{api_key}{path}",
        json={},
        headers={"content-type": CONTENT_TYPE_JSON},
    )


async def setup_deconz_integration(
    hass,
    aioclient_mock=None,
    *,
    config=ENTRY_CONFIG,
    options=ENTRY_OPTIONS,
    get_state_response=DECONZ_WEB_REQUEST,
    entry_id="1",
    unique_id=BRIDGEID,
    source=SOURCE_USER,
):
    """Create the deCONZ gateway."""
    config_entry = MockConfigEntry(
        domain=DECONZ_DOMAIN,
        source=source,
        data=deepcopy(config),
        options=deepcopy(options),
        entry_id=entry_id,
        unique_id=unique_id,
    )
    config_entry.add_to_hass(hass)

    if aioclient_mock:
        mock_deconz_request(aioclient_mock, config, get_state_response)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


async def test_gateway_setup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Successful setup."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ) as forward_entry_setup:
        config_entry = await setup_deconz_integration(hass, aioclient_mock)
        gateway = DeconzHub.get_hub(hass, config_entry)
        assert gateway.bridgeid == BRIDGEID
        assert gateway.master is True
        assert gateway.config.allow_clip_sensor is False
        assert gateway.config.allow_deconz_groups is True
        assert gateway.config.allow_new_devices is True

        assert len(gateway.deconz_ids) == 0
        assert len(hass.states.async_all()) == 0

        assert forward_entry_setup.mock_calls[0][1] == (
            config_entry,
            [
                ALARM_CONTROL_PANEL_DOMAIN,
                BINARY_SENSOR_DOMAIN,
                BUTTON_DOMAIN,
                CLIMATE_DOMAIN,
                COVER_DOMAIN,
                FAN_DOMAIN,
                LIGHT_DOMAIN,
                LOCK_DOMAIN,
                NUMBER_DOMAIN,
                SCENE_DOMAIN,
                SELECT_DOMAIN,
                SENSOR_DOMAIN,
                SIREN_DOMAIN,
                SWITCH_DOMAIN,
            ],
        )

    gateway_entry = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, gateway.bridgeid)}
    )

    assert gateway_entry.configuration_url == f"http://{HOST}:{PORT}"
    assert gateway_entry.entry_type is dr.DeviceEntryType.SERVICE


async def test_gateway_device_configuration_url_when_addon(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Successful setup."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ):
        config_entry = await setup_deconz_integration(
            hass, aioclient_mock, source=SOURCE_HASSIO
        )
        gateway = DeconzHub.get_hub(hass, config_entry)

    gateway_entry = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, gateway.bridgeid)}
    )

    assert (
        gateway_entry.configuration_url == "homeassistant://hassio/ingress/core_deconz"
    )


async def test_connection_status_signalling(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_deconz_websocket
) -> None:
    """Make sure that connection status triggers a dispatcher send."""
    data = {
        "sensors": {
            "1": {
                "name": "presence",
                "type": "ZHAPresence",
                "state": {"presence": False},
                "config": {"on": True, "reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        await setup_deconz_integration(hass, aioclient_mock)

    assert hass.states.get("binary_sensor.presence").state == STATE_OFF

    await mock_deconz_websocket(state=State.RETRYING)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.presence").state == STATE_UNAVAILABLE

    await mock_deconz_websocket(state=State.RUNNING)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.presence").state == STATE_OFF


async def test_update_address(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Make sure that connection status triggers a dispatcher send."""
    config_entry = await setup_deconz_integration(hass, aioclient_mock)
    gateway = DeconzHub.get_hub(hass, config_entry)
    assert gateway.api.host == "1.2.3.4"

    with patch(
        "homeassistant.components.deconz.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        await hass.config_entries.flow.async_init(
            DECONZ_DOMAIN,
            data=ssdp.SsdpServiceInfo(
                ssdp_st="mock_st",
                ssdp_usn="mock_usn",
                ssdp_location="http://2.3.4.5:80/",
                upnp={
                    ATTR_UPNP_MANUFACTURER_URL: DECONZ_MANUFACTURERURL,
                    ATTR_UPNP_SERIAL: BRIDGEID,
                    ATTR_UPNP_UDN: "uuid:456DEF",
                },
            ),
            context={"source": SOURCE_SSDP},
        )
        await hass.async_block_till_done()

    assert gateway.api.host == "2.3.4.5"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reset_after_successful_setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Make sure that connection status triggers a dispatcher send."""
    config_entry = await setup_deconz_integration(hass, aioclient_mock)
    gateway = DeconzHub.get_hub(hass, config_entry)

    result = await gateway.async_reset()
    await hass.async_block_till_done()

    assert result is True


async def test_get_deconz_api(hass: HomeAssistant) -> None:
    """Successful call."""
    config_entry = MockConfigEntry(domain=DECONZ_DOMAIN, data=ENTRY_CONFIG)
    with patch("pydeconz.DeconzSession.refresh_state", return_value=True):
        assert await get_deconz_api(hass, config_entry)


@pytest.mark.parametrize(
    ("side_effect", "raised_exception"),
    [
        (TimeoutError, CannotConnect),
        (pydeconz.RequestError, CannotConnect),
        (pydeconz.ResponseError, CannotConnect),
        (pydeconz.Unauthorized, AuthenticationRequired),
    ],
)
async def test_get_deconz_api_fails(
    hass: HomeAssistant, side_effect, raised_exception
) -> None:
    """Failed call."""
    config_entry = MockConfigEntry(domain=DECONZ_DOMAIN, data=ENTRY_CONFIG)
    with (
        patch(
            "pydeconz.DeconzSession.refresh_state",
            side_effect=side_effect,
        ),
        pytest.raises(raised_exception),
    ):
        assert await get_deconz_api(hass, config_entry)
