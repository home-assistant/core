"""Test the homewizard energy config flow."""
from unittest.mock import AsyncMock, Mock, patch

from aiohwenergy import DisabledError

from homeassistant import config_entries
from homeassistant.components.homewizard_energy.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.data_entry_flow import RESULT_TYPE_ABORT, RESULT_TYPE_CREATE_ENTRY


def get_mock_device(
    serial="aabbccddeeff",
    host="1.2.3.4",
    product_name="P1 meter",
    product_type="HWE-P1",
):
    """Return a mock bridge."""
    mock_device = Mock()
    mock_device._host = host

    mock_device.device.product_name = product_name
    mock_device.device.product_type = product_type
    mock_device.device.serial = serial
    mock_device.device.api_version = "v1"
    mock_device.device.firmware_version = "1.00"

    mock_device.initialize = AsyncMock()
    mock_device.close = AsyncMock()

    return mock_device


async def test_manual_flow_works(hass, aioclient_mock):
    """Test config flow accepts user configuration."""

    device = get_mock_device()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "2.2.2.2"}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.homewizard_energy.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"name": "CustomName"}
        )

    assert result["title"] == f"{device.device.product_name} (CustomName)"
    assert result["data"]["host"] == "2.2.2.2"
    assert (
        result["data"]["unique_id"]
        == f"{device.device.product_type}_{device.device.serial}"
    )
    assert result["data"]["product_name"] == device.device.product_name
    assert result["data"]["product_type"] == device.device.product_type
    assert result["data"]["serial"] == device.device.serial

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        entries = hass.config_entries.async_entries(DOMAIN)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.unique_id == f"{device.device.product_type}_{device.device.serial}"

    assert len(device.initialize.mock_calls) == 1
    assert len(device.close.mock_calls) == 1


async def test_discovery_flow_works(hass, aioclient_mock):
    """Test discovery setup flow works."""

    service_info = {
        "host": "192.168.43.183",
        "port": 80,
        "hostname": "p1meter-ddeeff.local.",
        "properties": {
            "api_enabled": "1",
            "path": "/api/v1",
            "product_name": "P1 meter",
            "product_type": "HWE-P1",
            "serial": "aabbccddeeff",
        },
    }

    with patch("aiohwenergy.HomeWizardEnergy", return_value=get_mock_device()), patch(
        "homeassistant.components.homewizard_energy.async_setup_entry",
        return_value=True,
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=service_info,
        )

    with patch(
        "homeassistant.components.homewizard_energy.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], user_input={}
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "P1 meter"
    assert result["data"][CONF_HOST] == "192.168.43.183"
    assert result["data"][CONF_PORT] == 80

    assert result["result"]
    assert result["result"].unique_id == "HWE-P1_aabbccddeeff"


async def test_discovery_disabled_api(hass, aioclient_mock):
    """Test discovery detecting disabled api."""

    service_info = {
        "host": "192.168.43.183",
        "port": 80,
        "hostname": "p1meter-ddeeff.local.",
        "properties": {
            "api_enabled": "0",
            "path": "/api/v1",
            "product_name": "P1 meter",
            "product_type": "HWE-P1",
            "serial": "aabbccddeeff",
        },
    }

    with patch("aiohwenergy.HomeWizardEnergy", return_value=get_mock_device()), patch(
        "homeassistant.components.homewizard_energy.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=service_info,
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "api_not_enabled"


async def test_discovery_missing_data_in_service_info(hass, aioclient_mock):
    """Test discovery detecting missing discovery info."""

    service_info = {
        # "host": "192.168.43.183", -> Removed
        "port": 80,
        "hostname": "p1meter-ddeeff.local.",
        "properties": {
            "api_enabled": "1",
            "path": "/api/v1",
            "product_name": "P1 meter",
            "product_type": "HWE-P1",
            "serial": "aabbccddeeff",
        },
    }

    with patch("aiohwenergy.HomeWizardEnergy", return_value=get_mock_device()), patch(
        "homeassistant.components.homewizard_energy.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=service_info,
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "invalid_discovery_parameters"

    service_info = {
        "host": "192.168.43.183",
        "port": 80,
        "hostname": "p1meter-ddeeff.local.",
        "properties": {
            # "api_enabled": "0", - Removed
            "path": "/api/v1",
            "product_name": "P1 meter",
            "product_type": "HWE-P1",
            "serial": "aabbccddeeff",
        },
    }

    with patch("aiohwenergy.HomeWizardEnergy", return_value=get_mock_device()), patch(
        "homeassistant.components.homewizard_energy.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=service_info,
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "invalid_discovery_parameters"


async def test_discovery_invalid_api(hass, aioclient_mock):
    """Test discovery detecting invalid_api."""

    service_info = {
        "host": "192.168.43.183",
        "port": 80,
        "hostname": "p1meter-ddeeff.local.",
        "properties": {
            "api_enabled": "1",
            "path": "/api/not_v1",
            "product_name": "P1 meter",
            "product_type": "HWE-P1",
            "serial": "aabbccddeeff",
        },
    }

    with patch("aiohwenergy.HomeWizardEnergy", return_value=get_mock_device()), patch(
        "homeassistant.components.homewizard_energy.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=service_info,
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unsupported_api_version"


async def test_check_disabled_api(hass, aioclient_mock):
    """Test check detecting disabled api."""

    def MockInitialize():
        raise DisabledError

    device = get_mock_device()
    device.initialize.side_effect = MockInitialize

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "2.2.2.2"}
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "api_not_enabled"


async def test_check_error_handling_api(hass, aioclient_mock):
    """Test check detecting error with api."""

    def MockInitialize():
        raise Exception()

    device = get_mock_device()
    device.initialize.side_effect = MockInitialize

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "2.2.2.2"}
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unknown_error"


async def test_check_detects_unexpected_api_response(hass, aioclient_mock):
    """Test check detecting device endpoint failed fetching data."""

    device = get_mock_device()
    device.device = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "2.2.2.2"}
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unknown_error"


async def test_check_detects_invalid_api(hass, aioclient_mock):
    """Test check detecting device endpoint failed fetching data."""

    device = get_mock_device()
    device.device.api_version = "not_v1"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "2.2.2.2"}
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unsupported_api_version"


async def test_check_detects_unsuported_device(hass, aioclient_mock):
    """Test check detecting device endpoint failed fetching data."""

    device = get_mock_device(product_type="not_an_energy_device")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "2.2.2.2"}
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "device_not_supported"
