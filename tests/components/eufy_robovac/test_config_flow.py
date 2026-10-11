"""Tests for the Eufy RoboVac config flow."""

from unittest.mock import AsyncMock, patch

from eufy_robovac import AuthenticationError, RoboVacConnectionError

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEVICE_ID, MOCK_INFO, MOCK_STATE

from tests.common import MockConfigEntry

ACCOUNT_INPUT = {
    CONF_USERNAME: "user@example.com",
    CONF_PASSWORD: "supersecret",
}


async def _async_start_flow(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        "eufy_robovac", context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result["flow_id"]


async def test_cloud_discovery_and_local_validation(hass: HomeAssistant) -> None:
    """Test credentials discover a vacuum but are not persisted."""
    flow_id = await _async_start_flow(hass)

    with patch(
        "homeassistant.components.eufy_robovac.config_flow.CloudClient",
        autospec=True,
    ) as cloud_client:
        cloud_client.return_value.list_devices = AsyncMock(return_value=[MOCK_INFO])
        result = await hass.config_entries.flow.async_configure(flow_id, ACCOUNT_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_device"

    result = await hass.config_entries.flow.async_configure(
        flow_id, {"device_id": DEVICE_ID}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device"

    with (
        patch(
            "homeassistant.components.eufy_robovac.config_flow.RoboVac",
            autospec=True,
        ) as robovac,
        patch(
            "homeassistant.components.eufy_robovac.async_setup_entry",
            return_value=True,
        ),
    ):
        robovac.return_value.update = AsyncMock(return_value=MOCK_STATE)
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: "192.168.1.51", "protocol_version": "3.3"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_INFO.name
    assert result["data"] == {
        "name": MOCK_INFO.name,
        "model": MOCK_INFO.model,
        "device_id": MOCK_INFO.device_id,
        "local_key": MOCK_INFO.local_key,
        "host": "192.168.1.51",
        "protocol_version": "3.3",
    }
    assert CONF_USERNAME not in result["data"]
    assert CONF_PASSWORD not in result["data"]


async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid cloud credentials."""
    flow_id = await _async_start_flow(hass)

    with patch(
        "homeassistant.components.eufy_robovac.config_flow.CloudClient",
        autospec=True,
    ) as cloud_client:
        cloud_client.return_value.list_devices = AsyncMock(
            side_effect=AuthenticationError
        )
        result = await hass.config_entries.flow.async_configure(flow_id, ACCOUNT_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cloud_cannot_connect(hass: HomeAssistant) -> None:
    """Test cloud connection errors."""
    flow_id = await _async_start_flow(hass)

    with patch(
        "homeassistant.components.eufy_robovac.config_flow.CloudClient",
        autospec=True,
    ) as cloud_client:
        cloud_client.return_value.list_devices = AsyncMock(
            side_effect=RoboVacConnectionError
        )
        result = await hass.config_entries.flow.async_configure(flow_id, ACCOUNT_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_no_supported_devices(hass: HomeAssistant) -> None:
    """Test accounts without a supported vacuum."""
    flow_id = await _async_start_flow(hass)

    with patch(
        "homeassistant.components.eufy_robovac.config_flow.CloudClient",
        autospec=True,
    ) as cloud_client:
        cloud_client.return_value.list_devices = AsyncMock(return_value=[])
        result = await hass.config_entries.flow.async_configure(flow_id, ACCOUNT_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}


async def test_local_validation_failure(hass: HomeAssistant) -> None:
    """Test local connectivity is checked before creating an entry."""
    flow_id = await _async_start_flow(hass)

    with patch(
        "homeassistant.components.eufy_robovac.config_flow.CloudClient",
        autospec=True,
    ) as cloud_client:
        cloud_client.return_value.list_devices = AsyncMock(return_value=[MOCK_INFO])
        await hass.config_entries.flow.async_configure(flow_id, ACCOUNT_INPUT)

    await hass.config_entries.flow.async_configure(flow_id, {"device_id": DEVICE_ID})
    with patch(
        "homeassistant.components.eufy_robovac.config_flow.RoboVac",
        autospec=True,
    ) as robovac:
        robovac.return_value.update = AsyncMock(side_effect=RoboVacConnectionError)
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_HOST: MOCK_INFO.host, "protocol_version": "3.3"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_device(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a vacuum can only be configured once."""
    mock_config_entry.add_to_hass(hass)
    flow_id = await _async_start_flow(hass)

    with patch(
        "homeassistant.components.eufy_robovac.config_flow.CloudClient",
        autospec=True,
    ) as cloud_client:
        cloud_client.return_value.list_devices = AsyncMock(return_value=[MOCK_INFO])
        await hass.config_entries.flow.async_configure(flow_id, ACCOUNT_INPUT)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {"device_id": DEVICE_ID}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
