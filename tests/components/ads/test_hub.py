"""Test the ADS hub."""

from unittest.mock import MagicMock

import pyads
import pytest

from homeassistant.components.ads.hub import AdsHub, apply_local_net_id, async_get_hub
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady

from .conftest import MockPyadsLocalNetId
from .const import AUTO_NET_ID, LOCAL_NET_ID

from tests.common import MockConfigEntry


@pytest.fixture
def ads_client() -> MagicMock:
    """Return a mocked pyads client."""
    return MagicMock()


@pytest.fixture
def hub(ads_client: MagicMock) -> AdsHub:
    """Return an AdsHub connected to the mocked client."""
    return AdsHub(ads_client)


def test_async_get_hub_not_loaded(hass: HomeAssistant) -> None:
    """Test async_get_hub raises when no entry is loaded."""
    with pytest.raises(PlatformNotReady):
        async_get_hub(hass)


async def test_async_get_hub(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyads_connection: MagicMock,
) -> None:
    """Test async_get_hub returns the loaded entry's hub."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert async_get_hub(hass) is mock_config_entry.runtime_data


def test_write_by_name(hub: AdsHub, ads_client: MagicMock) -> None:
    """Test writing a value by name."""
    hub.write_by_name("GVL.test", 42, pyads.PLCTYPE_INT)

    ads_client.write_by_name.assert_called_once_with("GVL.test", 42, pyads.PLCTYPE_INT)


def test_write_by_name_error(hub: AdsHub, ads_client: MagicMock) -> None:
    """Test a write error is logged instead of raised."""
    ads_client.write_by_name.side_effect = pyads.ADSError(text="timeout")

    hub.write_by_name("GVL.test", 42, pyads.PLCTYPE_INT)


def test_read_by_name(hub: AdsHub, ads_client: MagicMock) -> None:
    """Test reading a value by name."""
    ads_client.read_by_name.return_value = 42

    assert hub.read_by_name("GVL.test", pyads.PLCTYPE_INT) == 42


def test_read_by_name_error(hub: AdsHub, ads_client: MagicMock) -> None:
    """Test a read error is logged instead of raised."""
    ads_client.read_by_name.side_effect = pyads.ADSError(text="timeout")

    assert hub.read_by_name("GVL.test", pyads.PLCTYPE_INT) is None


def test_add_device_notification(hub: AdsHub, ads_client: MagicMock) -> None:
    """Test adding a device notification stores it on the hub."""
    ads_client.add_device_notification.return_value = (1, 2)

    hub.add_device_notification("GVL.test", pyads.PLCTYPE_INT, MagicMock())

    assert 1 in hub._notification_items


def test_add_device_notification_error(hub: AdsHub, ads_client: MagicMock) -> None:
    """Test a notification subscription error is logged instead of raised."""
    ads_client.add_device_notification.side_effect = pyads.ADSError(text="timeout")

    hub.add_device_notification("GVL.test", pyads.PLCTYPE_INT, MagicMock())

    assert not hub._notification_items


def test_shutdown(hub: AdsHub, ads_client: MagicMock) -> None:
    """Test shutdown deletes notifications and closes the connection."""
    ads_client.add_device_notification.return_value = (1, 2)
    hub.add_device_notification("GVL.test", pyads.PLCTYPE_INT, MagicMock())
    device = MagicMock()
    hub.register_device(device)

    hub.shutdown()

    ads_client.del_device_notification.assert_called_once_with(1, 2)
    ads_client.close.assert_called_once()
    assert not hub._notification_items
    device.mark_unavailable.assert_called_once()


def test_shutdown_ignores_ads_errors(hub: AdsHub, ads_client: MagicMock) -> None:
    """Test shutdown still closes the connection if cleanup calls fail."""
    ads_client.add_device_notification.return_value = (1, 2)
    hub.add_device_notification("GVL.test", pyads.PLCTYPE_INT, MagicMock())
    ads_client.del_device_notification.side_effect = pyads.ADSError(text="timeout")
    ads_client.close.side_effect = pyads.ADSError(text="timeout")

    hub.shutdown()

    assert not hub._notification_items


def test_unregister_device(hub: AdsHub) -> None:
    """Test a device is removed from the hub's registered devices."""
    device = MagicMock()
    hub.register_device(device)

    hub.unregister_device(device)

    assert device not in hub.devices


def test_apply_local_net_id_noop_without_override(
    mock_pyads_local_net_id: MockPyadsLocalNetId,
) -> None:
    """Test clearing the local NetID is a no-op if it was never overridden."""
    apply_local_net_id(None)

    mock_pyads_local_net_id.open_port.assert_not_called()
    mock_pyads_local_net_id.set_local_address.assert_not_called()


def test_apply_local_net_id_sets_custom(
    mock_pyads_local_net_id: MockPyadsLocalNetId,
) -> None:
    """Test a configured local NetID is applied."""
    apply_local_net_id(LOCAL_NET_ID)

    mock_pyads_local_net_id.open_port.assert_called_once()
    mock_pyads_local_net_id.set_local_address.assert_called_once_with(LOCAL_NET_ID)
    mock_pyads_local_net_id.close_port.assert_called_once()


def test_apply_local_net_id_restores_original(
    mock_pyads_local_net_id: MockPyadsLocalNetId,
) -> None:
    """Test the original NetID is restored once the custom one is cleared."""
    apply_local_net_id(LOCAL_NET_ID)

    apply_local_net_id(None)

    mock_pyads_local_net_id.set_local_address.assert_called_with(AUTO_NET_ID)
