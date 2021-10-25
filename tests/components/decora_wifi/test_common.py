"""Test the decora_wifi Common components."""

from unittest.mock import patch

from homeassistant.components.decora_wifi.common import (
    CommFailed,
    DecoraWifiEntity,
    DecoraWifiPlatform,
    LoginFailed,
)
from homeassistant.helpers import device_registry

from tests.components.decora_wifi.common import (
    SWITCH_NAME,
    FakeDecoraWiFiIotSwitch,
    FakeDecoraWiFiResidence,
    FakeDecoraWiFiResidentialAccount,
    FakeDecoraWiFiSession,
)

USERNAME = "username@home-assisant.com"
PASSWORD = "test-password"
INCORRECT_PASSWORD = "incorrect-password"
MODEL = "DW4SF"


async def test_platform_works(hass):
    """Check DecoraWifiPlatform initialization and deletion."""
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
        "homeassistant.components.decora_wifi.common.Person.logout"
    ) as mock_person_logout:
        # Setup platform object
        instance = await DecoraWifiPlatform.async_setup_decora_wifi(
            hass, USERNAME, PASSWORD
        )
        assert isinstance(instance, DecoraWifiPlatform)
        assert instance.email == USERNAME
        # Check that getdevices left platform object in expected state
        assert len(instance.active_platforms) == 1
        assert len(instance.lights) == 6

        # Clear the _iot_switches dict and check that refresh_devices recreates it.
        instance._iot_switches = {}
        instance.refresh_devices()
        assert len(instance.lights) == 6

        # Check instance teardown
        instance.teardown()
        mock_person_logout.assert_called_once()


async def test_platform_init_invalid_pw(hass):
    """Check DecoraWifiPlatform login failure throws correct exception."""
    instance = None
    exception = None

    with patch(
        "homeassistant.components.decora_wifi.common.DecoraWiFiSession",
        side_effect=FakeDecoraWiFiSession,
    ), patch(
        "homeassistant.components.decora_wifi.common.Person.logout"
    ) as mock_person_logout:
        # Check exception thrown as expected
        try:
            instance = DecoraWifiPlatform(USERNAME, INCORRECT_PASSWORD)
            instance.setup()
        except Exception as ex:
            exception = ex
        assert isinstance(exception, LoginFailed)
        mock_person_logout.assert_not_called()


async def test_platform_init_no_comms(hass):
    """Check DecoraWifiPlatform communication failure throws correct exception."""
    instance = None
    exception = None

    with patch(
        "homeassistant.components.decora_wifi.common.DecoraWiFiSession.login",
        side_effect=ValueError,
    ), patch(
        "homeassistant.components.decora_wifi.common.Person.logout"
    ) as mock_person_logout:
        # Check exception thrown as expected
        try:
            instance = DecoraWifiPlatform(USERNAME, PASSWORD)
            instance.setup()
        except Exception as ex:
            exception = ex
        assert isinstance(exception, CommFailed)
        mock_person_logout.assert_not_called()


async def test_platform_api_get_devices_comm_failed(hass):
    """Check DecoraWifiPlatform comm failure during initial getdevices."""
    instance = None
    exception = None

    # Failure in Gather Permissions
    with patch(
        "tests.components.decora_wifi.common.FakeDecoraWiFiPerson.get_residential_permissions",
        side_effect=ValueError,
    ), patch(
        "homeassistant.components.decora_wifi.common.DecoraWiFiSession",
        side_effect=FakeDecoraWiFiSession,
    ):
        try:
            instance = DecoraWifiPlatform(USERNAME, PASSWORD)
            instance.setup()
        except CommFailed as ex:
            exception = ex
        assert isinstance(exception, CommFailed)

    # Failure in Gather Residences
    with patch(
        "homeassistant.components.decora_wifi.common.DecoraWiFiSession",
        side_effect=FakeDecoraWiFiSession,
    ), patch(
        "homeassistant.components.decora_wifi.common.Residence",
        side_effect=FakeDecoraWiFiResidence,
    ), patch(
        "homeassistant.components.decora_wifi.common.ResidentialAccount.get_residences",
        side_effect=ValueError,
    ):
        try:
            instance = DecoraWifiPlatform(USERNAME, PASSWORD)
            instance.setup()
        except CommFailed as ex:
            exception = ex
        assert isinstance(exception, CommFailed)

    # Failure in Gather Switches
    with patch(
        "homeassistant.components.decora_wifi.common.DecoraWiFiSession",
        side_effect=FakeDecoraWiFiSession,
    ), patch(
        "homeassistant.components.decora_wifi.common.Residence.get_iot_switches",
        side_effect=ValueError,
    ), patch(
        "homeassistant.components.decora_wifi.common.ResidentialAccount",
        side_effect=FakeDecoraWiFiResidentialAccount,
    ):
        try:
            instance = DecoraWifiPlatform(USERNAME, PASSWORD)
            instance.setup()
        except CommFailed as ex:
            exception = ex
        assert isinstance(exception, CommFailed)


async def test_platform_api_logout_comm_failed(hass):
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


async def test_decora_wifi_entity_init(hass):
    """Check DecoraWifiEntity initialization."""
    session = FakeDecoraWiFiSession()
    switch = FakeDecoraWiFiIotSwitch(session, MODEL)

    entity = DecoraWifiEntity(switch)

    assert entity._switch == switch
    assert entity.unique_id == switch.mac
    assert entity.name == SWITCH_NAME
    assert entity.device_info == {
        "name": entity._switch.name,
        "connections": {(device_registry.CONNECTION_NETWORK_MAC, entity._mac_address)},
        "manufacturer": entity._switch.manufacturer,
        "model": entity._switch.model,
        "sw_version": entity._switch.version,
    }
