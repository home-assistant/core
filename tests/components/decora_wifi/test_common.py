"""Test the decora_wifi Common components."""

import logging
from unittest.mock import patch

from homeassistant.components.decora_wifi.common import (
    CommFailed,
    DecoraWifiEntity,
    DecoraWifiPlatform,
    LoginFailed,
)
from homeassistant.components.decora_wifi.const import DOMAIN
from homeassistant.helpers import device_registry

from tests.components.decora_wifi.common import (
    SWITCH_NAME,
    FakeDecoraWiFiIotSwitch,
    FakeDecoraWiFiResidence,
    FakeDecoraWiFiResidentialAccount,
    FakeDecoraWiFiSession,
)

_LOGGER = logging.getLogger(__name__)

USERNAME = "username@home-assisant.com"
PASSWORD = "test-password"
INCORRECT_PASSWORD = "incoreect-password"
MODEL = "DW4SF"


async def test_DecoraWifiPlatform_init(hass):
    """Check DecoraWifiPlatform initialization and deletion."""
    instance = None

    with patch(
        "homeassistant.components.decora_wifi.common.DecoraWiFiSession",
        side_effect=FakeDecoraWiFiSession,
    ) as mock_session_construct, patch(
        "homeassistant.components.decora_wifi.common.DecoraWifiPlatform._api_get_devices"
    ) as mock_api_get_devices, patch(
        "homeassistant.components.decora_wifi.common.Person.logout"
    ) as mock_person_logout:
        # Check object setup
        instance = DecoraWifiPlatform(USERNAME, PASSWORD)
        instance.setup()
        assert isinstance(instance, DecoraWifiPlatform)
        mock_session_construct.assert_called_once()
        mock_api_get_devices.assert_called_once()
        mock_session_construct.reset_mock()
        mock_api_get_devices.reset_mock()

        # Check object reauth
        instance.reauth()
        mock_person_logout.assert_called_once()
        mock_session_construct.assert_called_once()
        mock_person_logout.reset_mock()

        # Check object refresh devices
        instance.refresh_devices()
        mock_api_get_devices.assert_called_once()

        # Check object teardown on removal from hass
        instance.teardown()
        mock_person_logout.assert_called_once()


async def test_DecoraWifiPlatform_init_invalidpw(hass):
    """Check DecoraWifiPlatform login failure throws correct exception."""
    instance = None
    exception = None

    with patch(
        "homeassistant.components.decora_wifi.common.DecoraWiFiSession.login",
        return_value=None,
    ) as mock_session_login, patch(
        "homeassistant.components.decora_wifi.common.DecoraWifiPlatform._api_get_devices"
    ) as mock_api_get_devices, patch(
        "homeassistant.components.decora_wifi.common.DecoraWifiPlatform._api_logout"
    ) as mock_api_logout:
        # Check exception thrown as expected
        try:
            instance = DecoraWifiPlatform(USERNAME, PASSWORD)
            instance.setup()
        except Exception as ex:
            exception = ex
        assert isinstance(exception, LoginFailed)
        mock_session_login.assert_called_once()
        mock_api_get_devices.assert_not_called()
        mock_api_logout.assert_not_called()


async def test_DecoraWifiPlatform_init_nocomms(hass):
    """Check DecoraWifiPlatform communication failure throws correct exception."""
    instance = None
    exception = None

    with patch(
        "homeassistant.components.decora_wifi.common.DecoraWiFiSession.login",
        side_effect=ValueError,
    ) as mock_session_login, patch(
        "homeassistant.components.decora_wifi.common.DecoraWifiPlatform._api_get_devices"
    ) as mock_api_get_devices, patch(
        "homeassistant.components.decora_wifi.common.DecoraWifiPlatform._api_logout"
    ) as mock_api_logout:
        # Check exception thrown as expected
        try:
            instance = DecoraWifiPlatform(USERNAME, PASSWORD)
            instance.setup()
        except Exception as ex:
            exception = ex
        assert isinstance(exception, CommFailed)
        mock_session_login.assert_called_once()
        mock_api_get_devices.assert_not_called()
        mock_api_logout.assert_not_called()


async def test_DecoraWifiPlatform_getdevices(hass):
    """Check DecoraWifiPlatform getdevices function."""
    instance = None

    with patch(
        "homeassistant.components.decora_wifi.common.DecoraWiFiSession",
        side_effect=FakeDecoraWiFiSession,
    ), patch(
        "homeassistant.components.decora_wifi.common.Residence",
        side_effect=FakeDecoraWiFiResidence,
    ), patch(
        "homeassistant.components.decora_wifi.common.ResidentialAccount",
        side_effect=FakeDecoraWiFiResidentialAccount,
    ), patch(
        "homeassistant.components.decora_wifi.common.DecoraWifiPlatform._api_logout"
    ) as mock_api_logout:
        # Setup platform object
        instance = DecoraWifiPlatform(USERNAME, PASSWORD)
        instance.setup()
        assert isinstance(instance, DecoraWifiPlatform)

        # Check that getdevices left platform object in expected state
        assert len(instance.lights) == 6
        assert len(instance.active_platforms) == 1
        # Check object teardown
        instance.teardown()
        mock_api_logout.assert_called_once()


async def test_async_setup_decora_wifi(hass):
    """Check async wrapper for platform setup."""

    with patch(
        "homeassistant.components.decora_wifi.common.DecoraWifiPlatform"
    ) as mock_platform_setup:
        await DecoraWifiPlatform.async_setup_decora_wifi(hass, USERNAME, PASSWORD)
        await hass.async_block_till_done()
        mock_platform_setup.assert_called_once()


async def test_DecoraWifiPlatform_apigetdevices_commfailed(hass):
    """Check DecoraWifiPlatform comm failure during initial getdevices."""
    instance = None
    exception = None

    with patch(
        "homeassistant.components.decora_wifi.common.DecoraWiFiSession",
        side_effect=FakeDecoraWiFiSession,
    ), patch(
        "homeassistant.components.decora_wifi.common.Residence",
        side_effect=FakeDecoraWiFiResidence,
    ), patch(
        "homeassistant.components.decora_wifi.common.ResidentialAccount",
        side_effect=ValueError,
    ), patch(
        "homeassistant.components.decora_wifi.common.DecoraWifiPlatform._api_logout"
    ):
        # Setup Object
        try:
            instance = DecoraWifiPlatform(USERNAME, PASSWORD)
            instance.setup()
        except CommFailed as ex:
            exception = ex
        assert isinstance(exception, CommFailed)


async def test_DecoraWifiPlatform_apilogout_commfailed(hass):
    """Check DecoraWifiPlatform comm failure during deletion."""
    exception = None

    with patch(
        "homeassistant.components.decora_wifi.common.DecoraWiFiSession",
        side_effect=FakeDecoraWiFiSession,
    ), patch(
        "homeassistant.components.decora_wifi.common.DecoraWifiPlatform._api_get_devices"
    ), patch(
        "homeassistant.components.decora_wifi.common.Person.logout",
        side_effect=ValueError,
    ) as mock_person_logout:
        # Setup Object
        try:
            instance = DecoraWifiPlatform(USERNAME, PASSWORD)
            instance.setup()
            instance.teardown()
        except CommFailed as ex:
            exception = ex
        assert isinstance(exception, CommFailed)
        mock_person_logout.assert_called_once()


async def test_DecoraWifiEntity_init(hass):
    """Check DecoraWifiEntity initialization."""
    session = FakeDecoraWiFiSession()
    switch = FakeDecoraWiFiIotSwitch(session, MODEL)

    entity = DecoraWifiEntity(switch)

    assert entity._switch == switch
    assert entity.unique_id == switch.mac
    assert entity.name == SWITCH_NAME
    assert entity.device_info == {
        "name": entity._switch.name,
        "connections": {(device_registry.CONNECTION_NETWORK_MAC, entity._unique_id)},
        "identifiers": {(DOMAIN, entity._unique_id)},
        "manufacturer": entity._switch.manufacturer,
        "model": entity._switch.model,
        "sw_version": entity._switch.version,
    }
