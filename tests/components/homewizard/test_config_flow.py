"""Test the homewizard config flow."""
from unittest.mock import MagicMock, patch

from homewizard_energy.errors import DisabledError, RequestError, UnsupportedError

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.homewizard.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .generator import get_mock_device

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_manual_flow_works(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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

    assert len(device.close.mock_calls) == len(device.device.mock_calls)

    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovery_flow_works(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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


async def test_discovery_flow_during_onboarding(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_onboarding: MagicMock
) -> None:
    """Test discovery setup flow during onboarding."""

    with patch(
        "homeassistant.components.homewizard.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.homewizard.config_flow.HomeWizardEnergy",
        return_value=get_mock_device(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=zeroconf.ZeroconfServiceInfo(
                host="192.168.43.183",
                addresses=["192.168.43.183"],
                port=80,
                hostname="p1meter-ddeeff.local.",
                type="mock_type",
                name="mock_name",
                properties={
                    "api_enabled": "1",
                    "path": "/api/v1",
                    "product_name": "P1 meter",
                    "product_type": "HWE-P1",
                    "serial": "aabbccddeeff",
                },
            ),
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "P1 meter (aabbccddeeff)"
    assert result["data"][CONF_IP_ADDRESS] == "192.168.43.183"

    assert result["result"]
    assert result["result"].unique_id == "HWE-P1_aabbccddeeff"

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_onboarding.mock_calls) == 1


async def test_discovery_flow_during_onboarding_disabled_api(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_onboarding: MagicMock
) -> None:
    """Test discovery setup flow during onboarding with a disabled API."""

    def mock_initialize():
        raise DisabledError

    device = get_mock_device()
    device.device.side_effect = mock_initialize

    with patch(
        "homeassistant.components.homewizard.config_flow.HomeWizardEnergy",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=zeroconf.ZeroconfServiceInfo(
                host="192.168.43.183",
                addresses=["192.168.43.183"],
                port=80,
                hostname="p1meter-ddeeff.local.",
                type="mock_type",
                name="mock_name",
                properties={
                    "api_enabled": "0",
                    "path": "/api/v1",
                    "product_name": "P1 meter",
                    "product_type": "HWE-P1",
                    "serial": "aabbccddeeff",
                },
            ),
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["errors"] == {"base": "api_not_enabled"}

    # We are onboarded, user enabled API again and picks up from discovery/config flow
    device.device.side_effect = None
    mock_onboarding.return_value = True

    with patch(
        "homeassistant.components.homewizard.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.homewizard.config_flow.HomeWizardEnergy",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"ip_address": "192.168.43.183"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "P1 meter (aabbccddeeff)"
    assert result["data"][CONF_IP_ADDRESS] == "192.168.43.183"

    assert result["result"]
    assert result["result"].unique_id == "HWE-P1_aabbccddeeff"

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_onboarding.mock_calls) == 1


async def test_discovery_disabled_api(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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

    def mock_initialize():
        raise DisabledError

    device = get_mock_device()
    device.device.side_effect = mock_initialize

    with patch(
        "homeassistant.components.homewizard.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.homewizard.config_flow.HomeWizardEnergy",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"ip_address": "192.168.43.183"}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "api_not_enabled"}


async def test_discovery_missing_data_in_service_info(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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


async def test_discovery_invalid_api(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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


async def test_check_disabled_api(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "api_not_enabled"}


async def test_check_error_handling_api(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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


async def test_check_detects_invalid_api(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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


async def test_check_requesterror(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "network_error"}


async def test_reauth_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test reauth flow while API is enabled."""

    mock_entry = MockConfigEntry(
        domain="homewizard_energy", data={CONF_IP_ADDRESS: "1.2.3.4"}
    )

    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_entry.entry_id,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    device = get_mock_device()
    with patch(
        "homeassistant.components.homewizard.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.homewizard.config_flow.HomeWizardEnergy",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"


async def test_reauth_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test reauth flow while API is still disabled."""

    def mock_initialize():
        raise DisabledError()

    mock_entry = MockConfigEntry(
        domain="homewizard_energy", data={CONF_IP_ADDRESS: "1.2.3.4"}
    )

    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_entry.entry_id,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    device = get_mock_device()
    device.device.side_effect = mock_initialize
    with patch(
        "homeassistant.components.homewizard.config_flow.HomeWizardEnergy",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "api_not_enabled"}
