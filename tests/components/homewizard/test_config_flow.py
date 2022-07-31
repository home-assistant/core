"""Test the homewizard config flow."""
import logging
from unittest.mock import patch

from homewizard_energy.errors import DisabledError, RequestError, UnsupportedError

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.homewizard.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.data_entry_flow import FlowResultType

from .generator import get_mock_device

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_manual_flow_works(hass, aioclient_mock):
    """Test config flow accepts user configuration."""

    device = get_mock_device()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.homewizard.config_flow.HomeWizardEnergy",
        return_value=device,
    ), patch(
        "homeassistant.components.homewizard.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "2.2.2.2"}
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "P1 meter (aabbccddeeff)"
    assert result["data"][CONF_IP_ADDRESS] == "2.2.2.2"

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert len(device.device.mock_calls) == 1
    assert len(device.close.mock_calls) == 1

    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovery_flow_works(hass, aioclient_mock):
    """Test discovery setup flow works."""

    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.43.183",
        addresses=["192.168.43.183"],
        port=80,
        hostname="p1meter-ddeeff.local.",
        type="",
        name="",
        properties={
            "api_enabled": "1",
            "path": "/api/v1",
            "product_name": "P1 meter",
            "product_type": "HWE-P1",
            "serial": "aabbccddeeff",
        },
    )

    with patch(
        "homeassistant.components.homewizard.config_flow.HomeWizardEnergy",
        return_value=get_mock_device(),
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=service_info,
        )

    with patch(
        "homeassistant.components.homewizard.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.homewizard.config_flow.HomeWizardEnergy",
        return_value=get_mock_device(),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], user_input=None
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    with patch(
        "homeassistant.components.homewizard.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.homewizard.config_flow.HomeWizardEnergy",
        return_value=get_mock_device(),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], user_input={"ip_address": "192.168.43.183"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "P1 meter (aabbccddeeff)"
    assert result["data"][CONF_IP_ADDRESS] == "192.168.43.183"

    assert result["result"]
    assert result["result"].unique_id == "HWE-P1_aabbccddeeff"


async def test_config_flow_imports_entry(aioclient_mock, hass):
    """Test config flow accepts imported configuration."""

    device = get_mock_device()

    mock_entry = MockConfigEntry(domain="homewizard_energy", data={"host": "1.2.3.4"})
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homewizard.config_flow.HomeWizardEnergy",
        return_value=device,
    ), patch(
        "homeassistant.components.homewizard.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_IMPORT,
                "old_config_entry_id": mock_entry.entry_id,
            },
            data=mock_entry.data,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "P1 meter (aabbccddeeff)"
    assert result["data"][CONF_IP_ADDRESS] == "1.2.3.4"

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(device.device.mock_calls) == 1
    assert len(device.close.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovery_disabled_api(hass, aioclient_mock):
    """Test discovery detecting disabled api."""

    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.43.183",
        addresses=["192.168.43.183"],
        port=80,
        hostname="p1meter-ddeeff.local.",
        type="",
        name="",
        properties={
            "api_enabled": "0",
            "path": "/api/v1",
            "product_name": "P1 meter",
            "product_type": "HWE-P1",
            "serial": "aabbccddeeff",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=service_info,
    )

    assert result["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.homewizard.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.homewizard.config_flow.HomeWizardEnergy",
        return_value=get_mock_device(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"ip_address": "192.168.43.183"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "api_not_enabled"


async def test_discovery_missing_data_in_service_info(hass, aioclient_mock):
    """Test discovery detecting missing discovery info."""

    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.43.183",
        addresses=["192.168.43.183"],
        port=80,
        hostname="p1meter-ddeeff.local.",
        type="",
        name="",
        properties={
            # "api_enabled": "1", --> removed
            "path": "/api/v1",
            "product_name": "P1 meter",
            "product_type": "HWE-P1",
            "serial": "aabbccddeeff",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=service_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_parameters"


async def test_discovery_invalid_api(hass, aioclient_mock):
    """Test discovery detecting invalid_api."""

    service_info = zeroconf.ZeroconfServiceInfo(
        host="192.168.43.183",
        addresses=["192.168.43.183"],
        port=80,
        hostname="p1meter-ddeeff.local.",
        type="",
        name="",
        properties={
            "api_enabled": "1",
            "path": "/api/not_v1",
            "product_name": "P1 meter",
            "product_type": "HWE-P1",
            "serial": "aabbccddeeff",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=service_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unsupported_api_version"


async def test_check_disabled_api(hass, aioclient_mock):
    """Test check detecting disabled api."""

    def mock_initialize():
        raise DisabledError

    device = get_mock_device()
    device.device.side_effect = mock_initialize

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.homewizard.config_flow.HomeWizardEnergy",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "2.2.2.2"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "api_not_enabled"


async def test_check_error_handling_api(hass, aioclient_mock):
    """Test check detecting error with api."""

    def mock_initialize():
        raise Exception()

    device = get_mock_device()
    device.device.side_effect = mock_initialize

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.homewizard.config_flow.HomeWizardEnergy",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "2.2.2.2"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown_error"


async def test_check_detects_invalid_api(hass, aioclient_mock):
    """Test check detecting device endpoint failed fetching data."""

    def mock_initialize():
        raise UnsupportedError

    device = get_mock_device()
    device.device.side_effect = mock_initialize

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.homewizard.config_flow.HomeWizardEnergy",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "2.2.2.2"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unsupported_api_version"


async def test_check_requesterror(hass, aioclient_mock):
    """Test check detecting device endpoint failed fetching data due to a requesterror."""

    def mock_initialize():
        raise RequestError

    device = get_mock_device()
    device.device.side_effect = mock_initialize

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.homewizard.config_flow.HomeWizardEnergy",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "2.2.2.2"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown_error"
