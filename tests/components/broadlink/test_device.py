"""Tests for Broadlink devices."""
import broadlink.exceptions as blke

from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.broadlink.device import get_domains
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_ERROR,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.helpers.entity_registry import async_entries_for_device

from . import get_device

from tests.async_mock import patch
from tests.common import mock_device_registry, mock_registry


async def test_device_setup(hass):
    """Test a successful setup."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward, patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_init:
        await hass.config_entries.async_setup(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_LOADED
    assert mock_api.auth.call_count == 1
    assert mock_api.get_fwversion.call_count == 1
    forward_entries = {c[1][1] for c in mock_forward.mock_calls}
    domains = get_domains(mock_api.type)
    assert mock_forward.call_count == len(domains)
    assert forward_entries == domains
    assert mock_init.call_count == 0


async def test_device_setup_authentication_error(hass):
    """Test we handle an authentication error."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.AuthenticationError()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward, patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_init:
        await hass.config_entries.async_setup(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_SETUP_ERROR
    assert mock_api.auth.call_count == 1
    assert mock_forward.call_count == 0
    assert mock_init.call_count == 1
    assert mock_init.mock_calls[0][2]["context"]["source"] == "reauth"
    assert mock_init.mock_calls[0][2]["data"] == {
        "name": device.name,
        **device.get_entry_data(),
    }


async def test_device_setup_device_offline(hass):
    """Test we handle a device offline."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.DeviceOfflineError()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward, patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_init:
        await hass.config_entries.async_setup(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_SETUP_RETRY
    assert mock_api.auth.call_count == 1
    assert mock_forward.call_count == 0
    assert mock_init.call_count == 0


async def test_device_setup_os_error(hass):
    """Test we handle an OS error."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = OSError()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward, patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_init:
        await hass.config_entries.async_setup(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_SETUP_RETRY
    assert mock_api.auth.call_count == 1
    assert mock_forward.call_count == 0
    assert mock_init.call_count == 0


async def test_device_setup_broadlink_exception(hass):
    """Test we handle a Broadlink exception."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.BroadlinkException()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward, patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_init:
        await hass.config_entries.async_setup(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_SETUP_ERROR
    assert mock_api.auth.call_count == 1
    assert mock_forward.call_count == 0
    assert mock_init.call_count == 0


async def test_device_setup_update_device_offline(hass):
    """Test we handle a device offline in the update step."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.side_effect = blke.DeviceOfflineError()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward, patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_init:
        await hass.config_entries.async_setup(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_SETUP_RETRY
    assert mock_api.auth.call_count == 1
    assert mock_api.check_sensors.call_count == 1
    assert mock_forward.call_count == 0
    assert mock_init.call_count == 0


async def test_device_setup_update_authorization_error(hass):
    """Test we handle an authorization error in the update step."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.side_effect = (blke.AuthorizationError(), None)
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward, patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_init:
        await hass.config_entries.async_setup(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_LOADED
    assert mock_api.auth.call_count == 2
    assert mock_api.check_sensors.call_count == 2
    forward_entries = {c[1][1] for c in mock_forward.mock_calls}
    domains = get_domains(mock_api.type)
    assert mock_forward.call_count == len(domains)
    assert forward_entries == domains
    assert mock_init.call_count == 0


async def test_device_setup_update_authentication_error(hass):
    """Test we handle an authentication error in the update step."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.side_effect = blke.AuthorizationError()
    mock_api.auth.side_effect = (None, blke.AuthenticationError())
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward, patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_init:
        await hass.config_entries.async_setup(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_SETUP_RETRY
    assert mock_api.auth.call_count == 2
    assert mock_api.check_sensors.call_count == 1
    assert mock_forward.call_count == 0
    assert mock_init.call_count == 1
    assert mock_init.mock_calls[0][2]["context"]["source"] == "reauth"
    assert mock_init.mock_calls[0][2]["data"] == {
        "name": device.name,
        **device.get_entry_data(),
    }


async def test_device_setup_update_broadlink_exception(hass):
    """Test we handle a Broadlink exception in the update step."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.side_effect = blke.BroadlinkException()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward, patch.object(
        hass.config_entries.flow, "async_init"
    ) as mock_init:
        await hass.config_entries.async_setup(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_SETUP_RETRY
    assert mock_api.auth.call_count == 1
    assert mock_api.check_sensors.call_count == 1
    assert mock_forward.call_count == 0
    assert mock_init.call_count == 0


async def test_device_setup_get_fwversion_broadlink_exception(hass):
    """Test we load the device even if we cannot read the firmware version."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.get_fwversion.side_effect = blke.BroadlinkException()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward:
        await hass.config_entries.async_setup(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_LOADED
    forward_entries = {c[1][1] for c in mock_forward.mock_calls}
    domains = get_domains(mock_api.type)
    assert mock_forward.call_count == len(domains)
    assert forward_entries == domains


async def test_device_setup_get_fwversion_os_error(hass):
    """Test we load the device even if we cannot read the firmware version."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.get_fwversion.side_effect = OSError()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as mock_forward:
        await hass.config_entries.async_setup(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_LOADED
    forward_entries = {c[1][1] for c in mock_forward.mock_calls}
    domains = get_domains(mock_api.type)
    assert mock_forward.call_count == len(domains)
    assert forward_entries == domains


async def test_device_setup_registry(hass):
    """Test we register the device and the entries correctly."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    device_registry = mock_device_registry(hass)
    entity_registry = mock_registry(hass)

    with patch("broadlink.gendevice", return_value=mock_api):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert len(device_registry.devices) == 1

    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_entry.unique_id)}, set()
    )
    assert device_entry.identifiers == {(DOMAIN, device.mac)}
    assert device_entry.name == device.name
    assert device_entry.model == device.model
    assert device_entry.manufacturer == device.manufacturer
    assert device_entry.sw_version == device.fwversion

    for entry in async_entries_for_device(entity_registry, device_entry.id):
        assert entry.original_name.startswith(device.name)


async def test_device_unload_works(hass):
    """Test we unload the device."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as mock_forward:
        await hass.config_entries.async_unload(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_NOT_LOADED
    forward_entries = {c[1][1] for c in mock_forward.mock_calls}
    domains = get_domains(mock_api.type)
    assert mock_forward.call_count == len(domains)
    assert forward_entries == domains


async def test_device_unload_authentication_error(hass):
    """Test we unload a device that failed the authentication step."""
    device = get_device("Living Room")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.AuthenticationError()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ), patch.object(hass.config_entries.flow, "async_init"):
        await hass.config_entries.async_setup(mock_entry.entry_id)

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as mock_forward:
        await hass.config_entries.async_unload(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_NOT_LOADED
    assert mock_forward.call_count == 0


async def test_device_unload_update_failed(hass):
    """Test we unload a device that failed the update step."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.side_effect = blke.DeviceOfflineError()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    with patch("broadlink.gendevice", return_value=mock_api), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as mock_forward:
        await hass.config_entries.async_unload(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_NOT_LOADED
    assert mock_forward.call_count == 0


async def test_device_update_listener(hass):
    """Test we update device and entity registry when the entry is renamed."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    device_registry = mock_device_registry(hass)
    entity_registry = mock_registry(hass)

    with patch("broadlink.gendevice", return_value=mock_api):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        hass.config_entries.async_update_entry(mock_entry, title="New Name")
        await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_entry.unique_id)}, set()
    )
    assert device_entry.name == "New Name"
    for entry in async_entries_for_device(entity_registry, device_entry.id):
        assert entry.original_name.startswith("New Name")
