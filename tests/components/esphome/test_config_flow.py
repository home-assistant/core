"""Test config flow."""

from ipaddress import ip_address
import json
from typing import Any
from unittest.mock import AsyncMock, patch

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    DeviceInfo,
    InvalidAuthAPIError,
    InvalidEncryptionKeyAPIError,
    RequiresEncryptionAPIError,
    ResolveAPIError,
)
import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.components.esphome import dashboard
from homeassistant.components.esphome.const import (
    CONF_ALLOW_SERVICE_CALLS,
    CONF_DEVICE_NAME,
    CONF_NOISE_PSK,
    CONF_SUBSCRIBE_LOGS,
    DEFAULT_NEW_CONFIG_ALLOW_ALLOW_SERVICE_CALLS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IGNORE, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import VALID_NOISE_PSK
from .conftest import MockGenericDeviceEntryType

from tests.common import MockConfigEntry

INVALID_NOISE_PSK = "lSYBYEjQI1bVL8s2Vask4YytGMj1f1epNtmoim2yuTM="
WRONG_NOISE_PSK = "GP+ciK+nVfTQ/gcz6uOdS+oKEdJgesU+jeu8Ssj2how="


@pytest.fixture(autouse=False)
def mock_setup_entry():
    """Mock setting up a config entry."""
    with patch("homeassistant.components.esphome.async_setup_entry", return_value=True):
        yield


def get_flow_context(hass: HomeAssistant, result: ConfigFlowResult) -> dict[str, Any]:
    """Get the flow context from the result of async_init or async_configure."""
    flow = next(
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )

    return flow["context"]


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_user_connection_works(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 80},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 80,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: "",
        CONF_DEVICE_NAME: "test",
    }
    assert result["options"] == {
        CONF_ALLOW_SERVICE_CALLS: DEFAULT_NEW_CONFIG_ALLOW_ALLOW_SERVICE_CALLS
    }
    assert result["title"] == "test"
    assert result["result"].unique_id == "11:22:33:44:55:aa"

    assert len(mock_client.connect.mock_calls) == 1
    assert len(mock_client.device_info.mock_calls) == 1
    assert len(mock_client.disconnect.mock_calls) == 1
    assert mock_client.host == "127.0.0.1"
    assert mock_client.port == 80
    assert mock_client.password == ""
    assert mock_client.noise_psk is None


@pytest.mark.usefixtures("mock_client", "mock_setup_entry", "mock_zeroconf")
async def test_user_connection_updates_host(hass: HomeAssistant) -> None:
    """Test setup up the same name updates the host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 80},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_updates"
    assert result["description_placeholders"] == {
        "title": "Mock Title",
        "name": "unknown",
        "mac": "11:22:33:44:55:aa",
    }
    assert entry.data[CONF_HOST] == "127.0.0.1"


@pytest.mark.usefixtures("mock_client", "mock_setup_entry", "mock_zeroconf")
async def test_user_sets_unique_id(hass: HomeAssistant) -> None:
    """Test that the user flow sets the unique id."""
    service_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.43.183"),
        ip_addresses=[ip_address("192.168.43.183")],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={
            "mac": "1122334455aa",
        },
        type="mock_type",
    )
    discovery_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert discovery_result["type"] is FlowResultType.FORM
    assert discovery_result["step_id"] == "discovery_confirm"
    assert discovery_result["description_placeholders"] == {
        "name": "test8266",
    }

    discovery_result = await hass.config_entries.flow.async_configure(
        discovery_result["flow_id"],
        {},
    )
    assert discovery_result["type"] is FlowResultType.CREATE_ENTRY
    assert discovery_result["data"] == {
        CONF_HOST: "192.168.43.183",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: "",
        CONF_DEVICE_NAME: "test",
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_updates"
    assert result["description_placeholders"] == {
        "title": "test",
        "name": "test",
        "mac": "11:22:33:44:55:aa",
    }


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_user_resolve_error(hass: HomeAssistant, mock_client: APIClient) -> None:
    """Test user step with IP resolve error."""

    with patch(
        "homeassistant.components.esphome.config_flow.APIConnectionError",
        new_callable=lambda: ResolveAPIError,
    ) as exc:
        mock_client.device_info.side_effect = exc
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "resolve_error"}

    assert len(mock_client.connect.mock_calls) == 1
    assert len(mock_client.device_info.mock_calls) == 1
    assert len(mock_client.disconnect.mock_calls) == 1

    # Now simulate the user retrying with the same host and a successful connection
    mock_client.device_info.side_effect = None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test"
    assert result2["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_DEVICE_NAME: "test",
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: "",
    }


@pytest.mark.usefixtures("mock_client", "mock_setup_entry", "mock_zeroconf")
async def test_user_causes_zeroconf_to_abort(hass: HomeAssistant) -> None:
    """Test that the user flow sets the unique id and aborts the zeroconf flow."""
    service_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.43.183"),
        ip_addresses=[ip_address("192.168.43.183")],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={
            "mac": "1122334455aa",
        },
        type="mock_type",
    )
    discovery_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert discovery_result["type"] is FlowResultType.FORM
    assert discovery_result["step_id"] == "discovery_confirm"
    assert discovery_result["description_placeholders"] == {
        "name": "test8266",
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=None,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: "",
        CONF_DEVICE_NAME: "test",
    }

    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_user_connection_error(
    hass: HomeAssistant,
    mock_client: APIClient,
) -> None:
    """Test user step with connection error."""
    mock_client.device_info.side_effect = APIConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "connection_error"}

    assert len(mock_client.connect.mock_calls) == 1
    assert len(mock_client.device_info.mock_calls) == 1
    assert len(mock_client.disconnect.mock_calls) == 1

    # Now simulate the user retrying with the same host and a successful connection
    mock_client.device_info.side_effect = None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test"
    assert result2["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_DEVICE_NAME: "test",
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: "",
    }


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_user_with_password(
    hass: HomeAssistant,
    mock_client: APIClient,
) -> None:
    """Test user step with password."""
    mock_client.device_info.return_value = DeviceInfo(uses_password=True, name="test")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authenticate"
    assert result["description_placeholders"] == {"name": "test"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "password1"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_PASSWORD: "password1",
        CONF_NOISE_PSK: "",
        CONF_DEVICE_NAME: "test",
    }
    assert mock_client.password == "password1"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_user_invalid_password(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test user step with invalid password."""
    mock_client.device_info.return_value = DeviceInfo(uses_password=True, name="test")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authenticate"
    assert result["description_placeholders"] == {"name": "test"}

    mock_client.connect.side_effect = InvalidAuthAPIError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "invalid"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authenticate"
    assert result["description_placeholders"] == {"name": "test"}
    assert result["errors"] == {"base": "invalid_auth"}

    mock_client.connect.side_effect = None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "good"}
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test"
    assert result2["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_DEVICE_NAME: "test",
        CONF_PASSWORD: "good",
        CONF_NOISE_PSK: "",
    }


@pytest.mark.usefixtures("mock_dashboard", "mock_setup_entry", "mock_zeroconf")
async def test_user_dashboard_has_wrong_key(
    hass: HomeAssistant,
    mock_client: APIClient,
) -> None:
    """Test user step with key from dashboard that is incorrect."""
    mock_client.device_info.side_effect = [
        RequiresEncryptionAPIError,
        InvalidEncryptionKeyAPIError("Wrong key", "test"),
        DeviceInfo(
            uses_password=False,
            name="test",
            mac_address="11:22:33:44:55:AA",
        ),
    ]

    with patch(
        "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_encryption_key",
        return_value=WRONG_NOISE_PSK,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encryption_key"
    assert result["description_placeholders"] == {"name": "test"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: VALID_NOISE_PSK,
        CONF_DEVICE_NAME: "test",
    }
    assert mock_client.noise_psk == VALID_NOISE_PSK


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_user_discovers_name_and_gets_key_from_dashboard(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test user step can discover the name and get the key from the dashboard."""
    mock_client.device_info.side_effect = [
        RequiresEncryptionAPIError,
        InvalidEncryptionKeyAPIError("Wrong key", "test"),
        DeviceInfo(
            uses_password=False,
            name="test",
            mac_address="11:22:33:44:55:AA",
        ),
    ]

    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
        }
    )
    await dashboard.async_get_dashboard(hass).async_refresh()

    with patch(
        "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_encryption_key",
        return_value=VALID_NOISE_PSK,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: VALID_NOISE_PSK,
        CONF_DEVICE_NAME: "test",
    }
    assert mock_client.noise_psk == VALID_NOISE_PSK


@pytest.mark.parametrize(
    "dashboard_exception",
    [aiohttp.ClientError(), json.JSONDecodeError("test", "test", 0)],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_user_discovers_name_and_gets_key_from_dashboard_fails(
    hass: HomeAssistant,
    dashboard_exception: Exception,
    mock_client: APIClient,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test user step can discover the name and get the key from the dashboard."""
    mock_client.device_info.side_effect = [
        RequiresEncryptionAPIError,
        InvalidEncryptionKeyAPIError("Wrong key", "test"),
        DeviceInfo(
            uses_password=False,
            name="test",
            mac_address="11:22:33:44:55:AA",
        ),
    ]

    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
        }
    )
    await dashboard.async_get_dashboard(hass).async_refresh()

    with patch(
        "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_encryption_key",
        side_effect=dashboard_exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encryption_key"
    assert result["description_placeholders"] == {"name": "test"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: VALID_NOISE_PSK,
        CONF_DEVICE_NAME: "test",
    }
    assert mock_client.noise_psk == VALID_NOISE_PSK


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_user_discovers_name_and_dashboard_is_unavailable(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test user step can discover the name but the dashboard is unavailable."""
    mock_client.device_info.side_effect = [
        RequiresEncryptionAPIError,
        InvalidEncryptionKeyAPIError("Wrong key", "test"),
        DeviceInfo(
            uses_password=False,
            name="test",
            mac_address="11:22:33:44:55:AA",
        ),
    ]

    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
        }
    )

    with patch(
        "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_devices",
        side_effect=TimeoutError,
    ):
        await dashboard.async_get_dashboard(hass).async_refresh()
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encryption_key"
    assert result["description_placeholders"] == {"name": "test"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: VALID_NOISE_PSK,
        CONF_DEVICE_NAME: "test",
    }
    assert mock_client.noise_psk == VALID_NOISE_PSK


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_login_connection_error(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test user step with connection error on login attempt."""
    mock_client.device_info.return_value = DeviceInfo(uses_password=True, name="test")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authenticate"
    assert result["description_placeholders"] == {"name": "test"}

    mock_client.connect.side_effect = APIConnectionError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "valid"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authenticate"
    assert result["description_placeholders"] == {"name": "test"}
    assert result["errors"] == {"base": "connection_error"}

    mock_client.connect.side_effect = None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "good"}
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test"
    assert result2["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_DEVICE_NAME: "test",
        CONF_PASSWORD: "good",
        CONF_NOISE_PSK: "",
    }


@pytest.mark.usefixtures("mock_client", "mock_setup_entry", "mock_zeroconf")
async def test_discovery_initiation(hass: HomeAssistant) -> None:
    """Test discovery importing works."""
    service_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.43.183"),
        ip_addresses=[ip_address("192.168.43.183")],
        hostname="test.local.",
        name="mock_name",
        port=6053,
        properties={
            "mac": "1122334455aa",
            "friendly_name": "The Test",
        },
        type="mock_type",
    )
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )
    assert get_flow_context(hass, flow) == {
        "source": config_entries.SOURCE_ZEROCONF,
        "title_placeholders": {"name": "The Test (test)"},
        "unique_id": "11:22:33:44:55:aa",
    }

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"][CONF_HOST] == "192.168.43.183"
    assert result["data"][CONF_PORT] == 6053

    assert result["result"]
    assert result["result"].unique_id == "11:22:33:44:55:aa"


@pytest.mark.usefixtures("mock_client", "mock_setup_entry", "mock_zeroconf")
async def test_discovery_no_mac(hass: HomeAssistant) -> None:
    """Test discovery aborted if old ESPHome without mac in zeroconf."""
    service_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.43.183"),
        ip_addresses=[ip_address("192.168.43.183")],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={},
        type="mock_type",
    )
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )
    assert flow["type"] is FlowResultType.ABORT
    assert flow["reason"] == "mdns_missing_mac"


@pytest.mark.usefixtures("mock_client", "mock_setup_entry", "mock_zeroconf")
async def test_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test discovery aborts if already configured via hostname."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test8266.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )

    entry.add_to_hass(hass)

    service_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.43.183"),
        ip_addresses=[ip_address("192.168.43.183")],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={"mac": "1122334455aa"},
        type="mock_type",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_updates"
    assert result["description_placeholders"] == {
        "title": "Mock Title",
        "name": "unknown",
        "mac": "11:22:33:44:55:aa",
    }


@pytest.mark.usefixtures("mock_client", "mock_setup_entry", "mock_zeroconf")
async def test_discovery_ignored(hass: HomeAssistant) -> None:
    """Test discovery does not probe and ignored entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test8266.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
        source=SOURCE_IGNORE,
    )

    entry.add_to_hass(hass)

    service_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.43.183"),
        ip_addresses=[ip_address("192.168.43.183")],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={"mac": "1122334455aa"},
        type="mock_type",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_client", "mock_setup_entry", "mock_zeroconf")
async def test_discovery_duplicate_data(hass: HomeAssistant) -> None:
    """Test discovery aborts if same mDNS packet arrives."""
    service_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.43.183"),
        ip_addresses=[ip_address("192.168.43.183")],
        hostname="test.local.",
        name="mock_name",
        port=6053,
        properties={"address": "test.local", "mac": "1122334455aa"},
        type="mock_type",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, data=service_info, context={"source": config_entries.SOURCE_ZEROCONF}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {"name": "test"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, data=service_info, context={"source": config_entries.SOURCE_ZEROCONF}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.usefixtures("mock_client", "mock_setup_entry", "mock_zeroconf")
async def test_discovery_updates_unique_id(hass: HomeAssistant) -> None:
    """Test a duplicate discovery host aborts and updates existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )

    entry.add_to_hass(hass)

    service_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.43.184"),
        ip_addresses=[ip_address("192.168.43.184")],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={"address": "test8266.local", "mac": "1122334455aa"},
        type="mock_type",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_updates"
    assert result["description_placeholders"] == {
        "title": "Mock Title",
        "name": "unknown",
        "mac": "11:22:33:44:55:aa",
    }

    assert entry.data[CONF_HOST] == "192.168.43.184"
    assert entry.unique_id == "11:22:33:44:55:aa"


@pytest.mark.usefixtures("mock_client", "mock_setup_entry", "mock_zeroconf")
async def test_discovery_abort_without_update_same_host_port(
    hass: HomeAssistant,
) -> None:
    """Test discovery aborts without update when hsot and port are the same."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )

    entry.add_to_hass(hass)

    service_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.43.183"),
        ip_addresses=[ip_address("192.168.43.183")],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={"address": "test8266.local", "mac": "1122334455aa"},
        type="mock_type",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_user_requires_psk(hass: HomeAssistant, mock_client: APIClient) -> None:
    """Test user step with requiring encryption key."""
    mock_client.device_info.side_effect = RequiresEncryptionAPIError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encryption_key"
    assert result["errors"] == {}
    assert result["description_placeholders"] == {"name": "ESPHome"}

    assert len(mock_client.connect.mock_calls) == 2
    assert len(mock_client.device_info.mock_calls) == 2
    assert len(mock_client.disconnect.mock_calls) == 2

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: INVALID_NOISE_PSK}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encryption_key"
    assert result["errors"] == {"base": "requires_encryption_key"}
    assert result["description_placeholders"] == {"name": "ESPHome"}

    mock_client.device_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: VALID_NOISE_PSK,
        CONF_DEVICE_NAME: "test",
    }
    assert mock_client.noise_psk == VALID_NOISE_PSK


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_encryption_key_valid_psk(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test encryption key step with valid key."""

    mock_client.device_info.side_effect = RequiresEncryptionAPIError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encryption_key"
    assert result["description_placeholders"] == {"name": "ESPHome"}

    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(uses_password=False, name="test")
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: VALID_NOISE_PSK,
        CONF_DEVICE_NAME: "test",
    }
    assert mock_client.noise_psk == VALID_NOISE_PSK


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_encryption_key_invalid_psk(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test encryption key step with invalid key."""

    mock_client.device_info.side_effect = RequiresEncryptionAPIError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encryption_key"
    assert result["description_placeholders"] == {"name": "ESPHome"}

    mock_client.device_info.side_effect = InvalidEncryptionKeyAPIError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: INVALID_NOISE_PSK}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encryption_key"
    assert result["errors"] == {"base": "invalid_psk"}
    assert result["description_placeholders"] == {"name": "ESPHome"}
    assert mock_client.noise_psk == INVALID_NOISE_PSK

    mock_client.device_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: VALID_NOISE_PSK,
        CONF_DEVICE_NAME: "test",
    }
    assert mock_client.noise_psk == VALID_NOISE_PSK


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_reauth_confirm_valid(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test reauth initiation with valid PSK."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {
        "name": "Mock Title (test)",
    }

    mock_client.device_info.return_value = DeviceInfo(
        uses_password=False, name="test", mac_address="11:22:33:44:55:aa"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK


@pytest.mark.usefixtures("mock_zeroconf", "mock_setup_entry")
async def test_reauth_attempt_to_change_mac_aborts(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test reauth initiation with valid PSK attempting to change mac.

    This can happen if reauth starts, but they don't finish it before
    a new device takes the place of the old one at the same IP.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    mock_client.device_info.return_value = DeviceInfo(
        uses_password=False, name="test", mac_address="11:22:33:44:55:bb"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_unique_id_changed"
    assert CONF_NOISE_PSK not in entry.data
    assert result["description_placeholders"] == {
        "expected_mac": "11:22:33:44:55:aa",
        "host": "127.0.0.1",
        "name": "test",
        "unexpected_device_name": "test",
        "unexpected_mac": "11:22:33:44:55:bb",
    }


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_reauth_fixed_via_dashboard(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test reauth fixed automatically via dashboard."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    mock_client.device_info.return_value = DeviceInfo(
        uses_password=False, name="test", mac_address="11:22:33:44:55:aa"
    )

    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
        }
    )

    await dashboard.async_get_dashboard(hass).async_refresh()

    with patch(
        "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_encryption_key",
        return_value=VALID_NOISE_PSK,
    ) as mock_get_encryption_key:
        result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.ABORT, result
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK

    assert len(mock_get_encryption_key.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_reauth_fixed_via_dashboard_add_encryption_remove_password(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_dashboard: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth fixed automatically via dashboard with password removed."""
    mock_client.device_info.side_effect = (
        InvalidAuthAPIError,
        DeviceInfo(uses_password=False, name="test", mac_address="11:22:33:44:55:aa"),
    )

    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
        }
    )

    await dashboard.async_get_dashboard(hass).async_refresh()

    with patch(
        "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_encryption_key",
        return_value=VALID_NOISE_PSK,
    ) as mock_get_encryption_key:
        result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.ABORT, result
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK
    assert mock_config_entry.data[CONF_PASSWORD] == ""

    assert len(mock_get_encryption_key.mock_calls) == 1


@pytest.mark.usefixtures("mock_dashboard", "mock_setup_entry", "mock_zeroconf")
async def test_reauth_fixed_via_remove_password(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth fixed automatically by seeing password removed."""
    mock_client.device_info.return_value = DeviceInfo(
        uses_password=False, name="test", mac_address="11:22:33:44:55:aa"
    )

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.ABORT, result
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == ""


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_reauth_fixed_via_dashboard_at_confirm(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test reauth fixed automatically via dashboard at confirm step."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    mock_client.device_info.return_value = DeviceInfo(
        uses_password=False, name="test", mac_address="11:22:33:44:55:aa"
    )

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM, result
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {
        "name": "Mock Title (test)",
    }

    mock_dashboard["configured"].append(
        {
            "name": "test",
            "configuration": "test.yaml",
        }
    )

    await dashboard.async_get_dashboard(hass).async_refresh()

    with patch(
        "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_encryption_key",
        return_value=VALID_NOISE_PSK,
    ) as mock_get_encryption_key:
        # We just fetch the form
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT, result
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK

    assert len(mock_get_encryption_key.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_reauth_confirm_invalid(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test reauth initiation with invalid PSK."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    mock_client.device_info.side_effect = InvalidEncryptionKeyAPIError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: INVALID_NOISE_PSK}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {
        "name": "Mock Title (test)",
    }
    assert result["errors"]
    assert result["errors"]["base"] == "invalid_psk"

    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(
            uses_password=False, name="test", mac_address="11:22:33:44:55:aa"
        )
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_reauth_confirm_invalid_with_unique_id(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test reauth initiation with invalid PSK."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    mock_client.device_info.side_effect = InvalidEncryptionKeyAPIError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: INVALID_NOISE_PSK}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {
        "name": "Mock Title (test)",
    }
    assert result["errors"]
    assert result["errors"]["base"] == "invalid_psk"

    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(
            uses_password=False, name="test", mac_address="11:22:33:44:55:aa"
        )
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK


@pytest.mark.usefixtures("mock_client", "mock_setup_entry", "mock_zeroconf")
async def test_reauth_encryption_key_removed(hass: HomeAssistant) -> None:
    """Test reauth when the encryption key was removed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_NOISE_PSK: VALID_NOISE_PSK,
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_encryption_removed_confirm"
    assert result["description_placeholders"] == {
        "name": "Mock Title (test)",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_NOISE_PSK] == ""


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_discovery_dhcp_updates_host(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test dhcp discovery updates host and aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)
    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(name="test8266", mac_address="1122334455aa")
    )

    service_info = DhcpServiceInfo(
        ip="192.168.43.184",
        hostname="test8266",
        macaddress="1122334455aa",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=service_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_updates"
    assert result["description_placeholders"] == {
        "title": "Mock Title",
        "name": "unknown",
        "mac": "11:22:33:44:55:aa",
    }

    assert entry.data[CONF_HOST] == "192.168.43.184"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_discovery_dhcp_does_not_update_host_wrong_mac(
    hass: HomeAssistant,
    mock_client: APIClient,
) -> None:
    """Test dhcp discovery does not update the host if the mac is wrong."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)
    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(name="test8266", mac_address="1122334455ff")
    )

    service_info = DhcpServiceInfo(
        ip="192.168.43.184",
        hostname="test8266",
        macaddress="1122334455aa",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=service_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_detailed"
    assert result["description_placeholders"] == {
        "title": "Mock Title",
        "name": "unknown",
        "mac": "11:22:33:44:55:aa",
    }

    # Mac was wrong, should not update
    assert entry.data[CONF_HOST] == "192.168.43.183"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_discovery_dhcp_does_not_update_host_wrong_mac_bad_key(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test dhcp discovery does not update the host if the mac is wrong."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)
    mock_client.device_info.side_effect = InvalidEncryptionKeyAPIError(
        "Wrong key", "test8266", "1122334455cc"
    )
    service_info = DhcpServiceInfo(
        ip="192.168.43.184",
        hostname="test8266",
        macaddress="1122334455aa",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=service_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_detailed"
    assert result["description_placeholders"] == {
        "title": "Mock Title",
        "name": "unknown",
        "mac": "11:22:33:44:55:aa",
    }

    # Mac was wrong, should not update
    assert entry.data[CONF_HOST] == "192.168.43.183"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_discovery_dhcp_does_not_update_host_missing_mac_bad_key(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test dhcp discovery does not update the host if the mac is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)
    mock_client.device_info.side_effect = InvalidEncryptionKeyAPIError(
        "Wrong key", "test8266", None
    )
    service_info = DhcpServiceInfo(
        ip="192.168.43.184",
        hostname="test8266",
        macaddress="1122334455aa",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=service_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured_detailed"
    assert result["description_placeholders"] == {
        "title": "Mock Title",
        "name": "unknown",
        "mac": "11:22:33:44:55:aa",
    }

    # Mac was missing, should not update
    assert entry.data[CONF_HOST] == "192.168.43.183"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_discovery_dhcp_no_changes(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test dhcp discovery updates host and aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.43.183", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )
    entry.add_to_hass(hass)

    mock_client.device_info = AsyncMock(return_value=DeviceInfo(name="test8266"))

    service_info = DhcpServiceInfo(
        ip="192.168.43.183",
        hostname="test8266",
        macaddress="000000000000",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=service_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.data[CONF_HOST] == "192.168.43.183"


@pytest.mark.usefixtures("mock_dashboard")
async def test_discovery_hassio(hass: HomeAssistant) -> None:
    """Test dashboard discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={
                "host": "mock-esphome",
                "port": 6052,
            },
            name="ESPHome",
            slug="mock-slug",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "service_received"

    dash = dashboard.async_get_dashboard(hass)
    assert dash is not None
    assert dash.addon_slug == "mock-slug"


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_zeroconf_encryption_key_via_dashboard(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test encryption key retrieved from dashboard."""
    service_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.43.183"),
        ip_addresses=[ip_address("192.168.43.183")],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={
            "mac": "1122334455aa",
        },
        type="mock_type",
    )
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert flow["type"] is FlowResultType.FORM
    assert flow["step_id"] == "discovery_confirm"
    assert flow["description_placeholders"] == {"name": "test8266"}

    mock_dashboard["configured"].append(
        {
            "name": "test8266",
            "configuration": "test8266.yaml",
        }
    )

    await dashboard.async_get_dashboard(hass).async_refresh()

    mock_client.device_info.side_effect = [
        RequiresEncryptionAPIError,
        DeviceInfo(
            uses_password=False,
            name="test8266",
            mac_address="11:22:33:44:55:AA",
        ),
    ]

    with patch(
        "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_encryption_key",
        return_value=VALID_NOISE_PSK,
    ) as mock_get_encryption_key:
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], user_input={}
        )

    assert len(mock_get_encryption_key.mock_calls) == 1

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test8266"
    assert result["data"][CONF_HOST] == "192.168.43.183"
    assert result["data"][CONF_PORT] == 6053
    assert result["data"][CONF_NOISE_PSK] == VALID_NOISE_PSK

    assert result["result"]
    assert result["result"].unique_id == "11:22:33:44:55:aa"

    assert mock_client.noise_psk == VALID_NOISE_PSK


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_zeroconf_encryption_key_via_dashboard_with_api_encryption_prop(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test encryption key retrieved from dashboard with api_encryption property set."""
    service_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.43.183"),
        ip_addresses=[ip_address("192.168.43.183")],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={
            "mac": "1122334455aa",
            "api_encryption": "any",
        },
        type="mock_type",
    )
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert flow["type"] is FlowResultType.FORM
    assert flow["step_id"] == "discovery_confirm"
    assert flow["description_placeholders"] == {"name": "test8266"}

    mock_dashboard["configured"].append(
        {
            "name": "test8266",
            "configuration": "test8266.yaml",
        }
    )

    await dashboard.async_get_dashboard(hass).async_refresh()

    mock_client.device_info.side_effect = [
        DeviceInfo(
            uses_password=False,
            name="test8266",
            mac_address="11:22:33:44:55:AA",
        ),
    ]

    with patch(
        "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_encryption_key",
        return_value=VALID_NOISE_PSK,
    ) as mock_get_encryption_key:
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], user_input={}
        )

    assert len(mock_get_encryption_key.mock_calls) == 1

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test8266"
    assert result["data"][CONF_HOST] == "192.168.43.183"
    assert result["data"][CONF_PORT] == 6053
    assert result["data"][CONF_NOISE_PSK] == VALID_NOISE_PSK

    assert result["result"]
    assert result["result"].unique_id == "11:22:33:44:55:aa"

    assert mock_client.noise_psk == VALID_NOISE_PSK


@pytest.mark.usefixtures("mock_dashboard", "mock_setup_entry", "mock_zeroconf")
async def test_zeroconf_no_encryption_key_via_dashboard(
    hass: HomeAssistant,
    mock_client: APIClient,
) -> None:
    """Test encryption key not retrieved from dashboard."""
    service_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.43.183"),
        ip_addresses=[ip_address("192.168.43.183")],
        hostname="test8266.local.",
        name="mock_name",
        port=6053,
        properties={
            "mac": "1122334455aa",
        },
        type="mock_type",
    )
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=service_info
    )

    assert flow["type"] is FlowResultType.FORM
    assert flow["step_id"] == "discovery_confirm"
    assert flow["description_placeholders"] == {"name": "test8266"}

    await dashboard.async_get_dashboard(hass).async_refresh()

    mock_client.device_info.side_effect = RequiresEncryptionAPIError

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encryption_key"
    assert result["description_placeholders"] == {"name": "test8266"}

    mock_client.device_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "192.168.43.183",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: VALID_NOISE_PSK,
        CONF_DEVICE_NAME: "test",
    }
    assert mock_client.noise_psk == VALID_NOISE_PSK


async def test_option_flow_allow_service_calls(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test config flow options for allow service calls."""
    entry = await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {
        CONF_ALLOW_SERVICE_CALLS: DEFAULT_NEW_CONFIG_ALLOW_ALLOW_SERVICE_CALLS,
        CONF_SUBSCRIBE_LOGS: False,
    }

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {
        CONF_ALLOW_SERVICE_CALLS: DEFAULT_NEW_CONFIG_ALLOW_ALLOW_SERVICE_CALLS,
        CONF_SUBSCRIBE_LOGS: False,
    }
    with patch(
        "homeassistant.components.esphome.async_setup_entry", return_value=True
    ) as mock_reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_ALLOW_SERVICE_CALLS: True, CONF_SUBSCRIBE_LOGS: False},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_ALLOW_SERVICE_CALLS: True,
        CONF_SUBSCRIBE_LOGS: False,
    }
    assert len(mock_reload.mock_calls) == 1


async def test_option_flow_subscribe_logs(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test config flow options with subscribe logs."""
    entry = await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {
        CONF_ALLOW_SERVICE_CALLS: DEFAULT_NEW_CONFIG_ALLOW_ALLOW_SERVICE_CALLS,
        CONF_SUBSCRIBE_LOGS: False,
    }

    with patch(
        "homeassistant.components.esphome.async_setup_entry", return_value=True
    ) as mock_reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_ALLOW_SERVICE_CALLS: False, CONF_SUBSCRIBE_LOGS: True},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_ALLOW_SERVICE_CALLS: False,
        CONF_SUBSCRIBE_LOGS: True,
    }
    assert len(mock_reload.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_user_discovers_name_no_dashboard(
    hass: HomeAssistant,
    mock_client: APIClient,
) -> None:
    """Test user step can discover the name and the there is not dashboard."""
    mock_client.device_info.side_effect = [
        RequiresEncryptionAPIError,
        InvalidEncryptionKeyAPIError("Wrong key", "test"),
        DeviceInfo(
            uses_password=False,
            name="test",
            mac_address="11:22:33:44:55:AA",
        ),
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encryption_key"
    assert result["description_placeholders"] == {"name": "test"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: VALID_NOISE_PSK,
        CONF_DEVICE_NAME: "test",
    }
    assert mock_client.noise_psk == VALID_NOISE_PSK


async def mqtt_discovery_test_abort(
    hass: HomeAssistant, payload: str, reason: str
) -> None:
    """Test discovery aborted."""
    service_info = MqttServiceInfo(
        topic="esphome/discover/test",
        payload=payload,
        qos=0,
        retain=False,
        subscribed_topic="esphome/discover/#",
        timestamp=None,
    )
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=service_info
    )
    assert flow["type"] is FlowResultType.ABORT
    assert flow["reason"] == reason


@pytest.mark.usefixtures("mock_client", "mock_setup_entry", "mock_zeroconf")
async def test_discovery_mqtt_no_mac(hass: HomeAssistant) -> None:
    """Test discovery aborted if mac is missing in MQTT payload."""
    await mqtt_discovery_test_abort(hass, "{}", "mqtt_missing_mac")


@pytest.mark.usefixtures("mock_client", "mock_setup_entry", "mock_zeroconf")
async def test_discovery_mqtt_empty_payload(hass: HomeAssistant) -> None:
    """Test discovery aborted if MQTT payload is empty."""
    await mqtt_discovery_test_abort(hass, "", "mqtt_missing_payload")


@pytest.mark.usefixtures("mock_client", "mock_setup_entry", "mock_zeroconf")
async def test_discovery_mqtt_no_api(hass: HomeAssistant) -> None:
    """Test discovery aborted if api/port is missing in MQTT payload."""
    await mqtt_discovery_test_abort(hass, '{"mac":"abcdef123456"}', "mqtt_missing_api")


@pytest.mark.usefixtures("mock_client", "mock_setup_entry", "mock_zeroconf")
async def test_discovery_mqtt_no_ip(hass: HomeAssistant) -> None:
    """Test discovery aborted if ip is missing in MQTT payload."""
    await mqtt_discovery_test_abort(
        hass, '{"mac":"abcdef123456","port":6053}', "mqtt_missing_ip"
    )


@pytest.mark.usefixtures("mock_client", "mock_setup_entry", "mock_zeroconf")
async def test_discovery_mqtt_initiation(hass: HomeAssistant) -> None:
    """Test discovery importing works."""
    service_info = MqttServiceInfo(
        topic="esphome/discover/test",
        payload='{"name":"mock_name","mac":"1122334455aa","port":6053,"ip":"192.168.43.183"}',
        qos=0,
        retain=False,
        subscribed_topic="esphome/discover/#",
        timestamp=None,
    )
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_MQTT}, data=service_info
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test"
    assert result["data"][CONF_HOST] == "192.168.43.183"
    assert result["data"][CONF_PORT] == 6053

    assert result["result"]
    assert result["result"].unique_id == "11:22:33:44:55:aa"


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_user_flow_name_conflict_migrate(
    hass: HomeAssistant,
    mock_client: APIClient,
) -> None:
    """Test handle migration on name conflict."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE_NAME: "test"},
        unique_id="11:22:33:44:55:cc",
    )
    existing_entry.add_to_hass(hass)
    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(
            uses_password=False,
            name="test",
            mac_address="11:22:33:44:55:AA",
        )
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "name_conflict"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "name_conflict_migrate"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "name_conflict_migrated"
    assert result["description_placeholders"] == {
        "existing_mac": "11:22:33:44:55:cc",
        "mac": "11:22:33:44:55:aa",
        "name": "test",
    }
    assert existing_entry.data == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: "",
        CONF_DEVICE_NAME: "test",
    }
    assert existing_entry.unique_id == "11:22:33:44:55:aa"


@pytest.mark.usefixtures("mock_setup_entry", "mock_zeroconf")
async def test_user_flow_name_conflict_overwrite(
    hass: HomeAssistant,
    mock_client: APIClient,
) -> None:
    """Test handle overwrite on name conflict."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE_NAME: "test"},
        unique_id="11:22:33:44:55:cc",
    )
    existing_entry.add_to_hass(hass)
    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(
            uses_password=False,
            name="test",
            mac_address="11:22:33:44:55:AA",
        )
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "127.0.0.1", CONF_PORT: 6053},
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "name_conflict"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "name_conflict_overwrite"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: "",
        CONF_DEVICE_NAME: "test",
    }
    assert result["context"]["unique_id"] == "11:22:33:44:55:aa"


@pytest.mark.usefixtures("mock_zeroconf", "mock_setup_entry")
async def test_reconfig_success_with_same_ip_new_name(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test reconfig initiation with same ip and new name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    mock_client.device_info.return_value = DeviceInfo(
        uses_password=False, name="other", mac_address="11:22:33:44:55:aa"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 6053}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "127.0.0.1"
    assert entry.data[CONF_DEVICE_NAME] == "other"


@pytest.mark.usefixtures("mock_zeroconf", "mock_setup_entry")
async def test_reconfig_success_with_new_ip_new_name(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test reconfig initiation with new ip and new name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    mock_client.device_info.return_value = DeviceInfo(
        uses_password=False, name="other", mac_address="11:22:33:44:55:aa"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.2", CONF_PORT: 6053}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "127.0.0.2"
    assert entry.data[CONF_DEVICE_NAME] == "other"


@pytest.mark.usefixtures("mock_zeroconf", "mock_setup_entry")
async def test_reconfig_success_with_new_ip_same_name(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test reconfig initiation with new ip and same name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
            CONF_NOISE_PSK: VALID_NOISE_PSK,
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    mock_client.device_info.return_value = DeviceInfo(
        uses_password=False, name="test", mac_address="11:22:33:44:55:aa"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 6053}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "127.0.0.1"
    assert entry.data[CONF_DEVICE_NAME] == "test"
    assert entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK


@pytest.mark.usefixtures("mock_zeroconf", "mock_setup_entry")
async def test_reconfig_success_noise_psk_changes(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test reconfig initiation with new ip and new noise psk."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
            CONF_NOISE_PSK: VALID_NOISE_PSK,
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    mock_client.device_info.side_effect = [
        RequiresEncryptionAPIError,
        InvalidEncryptionKeyAPIError("Wrong key", "test"),
        DeviceInfo(uses_password=False, name="test", mac_address="11:22:33:44:55:aa"),
    ]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 6053}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encryption_key"
    assert result["description_placeholders"] == {"name": "Mock Title (test)"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encryption_key"
    assert result["description_placeholders"] == {"name": "Mock Title (test)"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NOISE_PSK: VALID_NOISE_PSK}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "127.0.0.1"
    assert entry.data[CONF_DEVICE_NAME] == "test"
    assert entry.data[CONF_NOISE_PSK] == VALID_NOISE_PSK


@pytest.mark.usefixtures("mock_zeroconf", "mock_setup_entry")
async def test_reconfig_name_conflict_with_existing_entry(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test reconfig with a name conflict with an existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.2",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "other",
        },
        unique_id="11:22:33:44:55:bb",
    )
    entry2.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    mock_client.device_info.return_value = DeviceInfo(
        uses_password=False, name="other", mac_address="11:22:33:44:55:aa"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.3", CONF_PORT: 6053}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_name_conflict"
    assert result["description_placeholders"] == {
        "existing_title": "Mock Title",
        "expected_mac": "11:22:33:44:55:aa",
        "host": "127.0.0.3",
        "name": "test",
    }


@pytest.mark.usefixtures("mock_zeroconf", "mock_setup_entry")
async def test_reconfig_attempt_to_change_mac_aborts(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test reconfig initiation with valid PSK attempting to change mac."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    mock_client.device_info.return_value = DeviceInfo(
        uses_password=False, name="other", mac_address="11:22:33:44:55:bb"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.2", CONF_PORT: 6053}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_unique_id_changed"
    assert CONF_NOISE_PSK not in entry.data
    assert result["description_placeholders"] == {
        "expected_mac": "11:22:33:44:55:aa",
        "host": "127.0.0.2",
        "name": "test",
        "unexpected_device_name": "other",
        "unexpected_mac": "11:22:33:44:55:bb",
    }


@pytest.mark.usefixtures("mock_zeroconf", "mock_setup_entry")
async def test_reconfig_mac_used_by_other_entry(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test reconfig when there is another entry for the mac."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.2",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test4",
        },
        unique_id="11:22:33:44:55:bb",
    )
    entry2.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)

    mock_client.device_info.return_value = DeviceInfo(
        uses_password=False, name="test", mac_address="11:22:33:44:55:bb"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.2", CONF_PORT: 6053}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_already_configured"
    assert result["description_placeholders"] == {
        "title": "Mock Title",
        "name": "test4",
        "mac": "11:22:33:44:55:bb",
    }


@pytest.mark.usefixtures("mock_zeroconf", "mock_setup_entry")
async def test_reconfig_name_conflict_migrate(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test reconfig initiation when device has been replaced."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    mock_client.device_info.return_value = DeviceInfo(
        uses_password=False, name="test", mac_address="11:22:33:44:55:bb"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.2", CONF_PORT: 6053}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "name_conflict"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "name_conflict_migrate"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "name_conflict_migrated"

    assert entry.data == {
        CONF_HOST: "127.0.0.2",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: "",
        CONF_DEVICE_NAME: "test",
    }
    assert entry.unique_id == "11:22:33:44:55:bb"


@pytest.mark.usefixtures("mock_zeroconf", "mock_setup_entry")
async def test_reconfig_name_conflict_overwrite(
    hass: HomeAssistant, mock_client: APIClient
) -> None:
    """Test reconfig initiation when device has been replaced."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    mock_client.device_info.return_value = DeviceInfo(
        uses_password=False, name="test", mac_address="11:22:33:44:55:bb"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.2", CONF_PORT: 6053}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "name_conflict"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "name_conflict_overwrite"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert result["data"] == {
        CONF_HOST: "127.0.0.2",
        CONF_PORT: 6053,
        CONF_PASSWORD: "",
        CONF_NOISE_PSK: "",
        CONF_DEVICE_NAME: "test",
    }
    assert result["context"]["unique_id"] == "11:22:33:44:55:bb"
    assert (
        hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, "11:22:33:44:55:aa"
        )
        is None
    )
