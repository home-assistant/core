"""Test the melnor config flow."""
from unittest.mock import patch

from bleak.backends.scanner import AdvertisementData, BLEDevice
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.components.melnor.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_MAC
from homeassistant.data_entry_flow import FlowResultType

from . import FAKE_ADDRESS, FAKE_SERVICE_INFO

INTEGRATION_DISCOVERY = {CONF_MAC: FAKE_ADDRESS}


async def test_pick_device(hass):
    """Test we properly handle device picking."""

    with patch(
        "homeassistant.components.melnor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.bluetooth.async_discovered_service_info",
    ) as mock_async_discovered_service_info:

        device = BluetoothServiceInfoBleak(
            name="None",
            address=FAKE_ADDRESS,
            rssi=-19,
            manufacturer_data={13: bytearray([89])},
            service_data={},
            service_uuids=[],
            source="local",
            device=BLEDevice(FAKE_ADDRESS, None),
            advertisement=AdvertisementData(local_name=""),
            time=0,
            connectable=True,
        )

        mock_async_discovered_service_info.return_value = [device]

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "pick_device"
        assert result["data_schema"].__dict__["schema"][CONF_ADDRESS].container == {
            FAKE_ADDRESS
        }

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADDRESS: FAKE_ADDRESS}
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == {CONF_ADDRESS: FAKE_ADDRESS}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_discovered(hass):
    """Test we short circuit to config entry creation."""

    with patch(
        "homeassistant.components.melnor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=FAKE_SERVICE_INFO,
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "bluetooth_confirm"
        assert result["description_placeholders"] == {"name": FAKE_ADDRESS}

    assert len(mock_setup_entry.mock_calls) == 0


async def test_bluetooth_confirm(hass):
    """Test we short circuit to config entry creation."""

    with patch(
        "homeassistant.components.melnor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        # Create the config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_BLUETOOTH,
                "step_id": "bluetooth_confirm",
                "user_input": {CONF_MAC: FAKE_ADDRESS},
            },
            data=FAKE_SERVICE_INFO,
        )

        # Interact with it like a user would
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == FAKE_ADDRESS
        assert result2["data"] == {CONF_ADDRESS: FAKE_ADDRESS}

    assert len(mock_setup_entry.mock_calls) == 1
