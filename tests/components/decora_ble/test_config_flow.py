"""Test the EufyLife config flow."""
import logging
from unittest.mock import patch

from decora_bleak import DeviceConnectionError, DeviceNotInPairingModeError

from homeassistant import config_entries
from homeassistant.components.decora_ble.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    DECORA_BLE_SERVICE_INFO,
    NOT_DECORA_BLE_SERVICE_INFO,
    patch_async_ble_device_from_address,
    patch_decora_ble_get_api_key,
    patch_decora_ble_get_api_key_fail_with_exception,
)

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(level=logging.DEBUG)


async def test_async_step_bluetooth_initial_form_when_decora_device(
    hass: HomeAssistant,
) -> None:
    """Test structure of initial form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DECORA_BLE_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["data_schema"].schema[CONF_NAME]


async def test_async_step_bluetooth_creates_entity_when_api_key_found(
    hass: HomeAssistant,
) -> None:
    """Test entity creation when things are right."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DECORA_BLE_SERVICE_INFO,
    )

    with patch_async_ble_device_from_address(
        DECORA_BLE_SERVICE_INFO
    ), patch_decora_ble_get_api_key("A1B2C3D4"):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_NAME: "Garage Lights"}
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Garage Lights"
    assert result2["data"] == {
        CONF_ADDRESS: "11:22:33:44:55:66",
        CONF_API_KEY: "A1B2C3D4",
        CONF_NAME: "Garage Lights",
    }
    assert result2["result"].unique_id == "11:22:33:44:55:66"


async def test_async_step_bluetooth_aborts_when_device_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test aborting if the device is already set up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="11:22:33:44:55:66",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DECORA_BLE_SERVICE_INFO,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_bluetooth_errors_on_no_device(hass: HomeAssistant) -> None:
    """Test showing an error if the device cannot be connected to over bluetooth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DECORA_BLE_SERVICE_INFO,
    )

    with patch_async_ble_device_from_address(None):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_NAME: "Garage Lights"}
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


async def test_async_step_bluetooth_errors_on_device_not_in_pairing_mode(
    hass: HomeAssistant,
) -> None:
    """Test showing an error if the device is not in pairing mode."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DECORA_BLE_SERVICE_INFO,
    )

    with patch_async_ble_device_from_address(
        DECORA_BLE_SERVICE_INFO
    ), patch_decora_ble_get_api_key_fail_with_exception(DeviceNotInPairingModeError):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_NAME: "Garage Lights"}
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "not_in_pairing_mode"


async def test_async_step_bluetooth_errors_on_device_connection_problems(
    hass: HomeAssistant,
) -> None:
    """Test showing an error if the device is not in pairing mode."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DECORA_BLE_SERVICE_INFO,
    )

    with patch_async_ble_device_from_address(
        DECORA_BLE_SERVICE_INFO
    ), patch_decora_ble_get_api_key_fail_with_exception(DeviceConnectionError):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_NAME: "Garage Lights"}
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


async def test_async_step_user_no_devices_found_leads_to_abort(
    hass: HomeAssistant,
) -> None:
    """Test no bluetooth devices found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_initial_form_when_decora_device(
    hass: HomeAssistant,
) -> None:
    """Test structure of initial form."""
    with patch(
        "homeassistant.components.decora_ble.config_flow.async_discovered_service_info",
        return_value=[DECORA_BLE_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"].schema[CONF_ADDRESS]
    assert result["data_schema"].schema[CONF_NAME]


async def test_async_step_user_aborts_when_only_device_is_not_decora(
    hass: HomeAssistant,
) -> None:
    """Test aborting if device discovered is not a Decora device."""
    with patch(
        "homeassistant.components.decora_ble.config_flow.async_discovered_service_info",
        return_value=[NOT_DECORA_BLE_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_aborts_when_configured_decora_device_is_only_device(
    hass: HomeAssistant,
) -> None:
    """Test aborting if the only discovered device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="11:22:33:44:55:66",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.decora_ble.config_flow.async_discovered_service_info",
        return_value=[DECORA_BLE_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_creates_entity_when_api_key_found(
    hass: HomeAssistant,
) -> None:
    """Test entity creation when things are right."""
    with patch(
        "homeassistant.components.decora_ble.config_flow.async_discovered_service_info",
        return_value=[DECORA_BLE_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    with patch_async_ble_device_from_address(
        DECORA_BLE_SERVICE_INFO
    ), patch_decora_ble_get_api_key("A1B2C3D4"):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: "11:22:33:44:55:66", CONF_NAME: "Garage Lights"},
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Garage Lights"
    assert result2["data"] == {
        CONF_ADDRESS: "11:22:33:44:55:66",
        CONF_API_KEY: "A1B2C3D4",
        CONF_NAME: "Garage Lights",
    }
    assert result2["result"].unique_id == "11:22:33:44:55:66"


async def test_async_step_user_errors_on_no_device(hass: HomeAssistant) -> None:
    """Test showing an error if the device cannot be connected to over bluetooth."""
    with patch(
        "homeassistant.components.decora_ble.config_flow.async_discovered_service_info",
        return_value=[DECORA_BLE_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    with patch_async_ble_device_from_address(None):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: "11:22:33:44:55:66", CONF_NAME: "Garage Lights"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


async def test_async_step_user_errors_on_device_not_in_pairing_mode(
    hass: HomeAssistant,
) -> None:
    """Test showing an error if the device is not in pairing mode."""
    with patch(
        "homeassistant.components.decora_ble.config_flow.async_discovered_service_info",
        return_value=[DECORA_BLE_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    with patch_async_ble_device_from_address(
        DECORA_BLE_SERVICE_INFO
    ), patch_decora_ble_get_api_key_fail_with_exception(DeviceNotInPairingModeError):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: "11:22:33:44:55:66", CONF_NAME: "Garage Lights"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "not_in_pairing_mode"


async def test_async_step_user_errors_on_device_connection_problems(
    hass: HomeAssistant,
) -> None:
    """Test showing an error if the device is not in pairing mode."""
    with patch(
        "homeassistant.components.decora_ble.config_flow.async_discovered_service_info",
        return_value=[DECORA_BLE_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    with patch_async_ble_device_from_address(
        DECORA_BLE_SERVICE_INFO
    ), patch_decora_ble_get_api_key_fail_with_exception(DeviceConnectionError):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: "11:22:33:44:55:66", CONF_NAME: "Garage Lights"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"
