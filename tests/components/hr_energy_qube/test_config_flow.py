"""Test the Qube Heat Pump config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from python_qube_heatpump import QubeDeviceInfo

from homeassistant.components.hr_energy_qube.const import DOMAIN, MDNS_LOOKUP_TIMEOUT
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import DEVICE_INFO

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("device_info", "unique_id"),
    [(DEVICE_INFO, DEVICE_INFO.uuid), (None, None)],
    ids=["mdns", "no_mdns"],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_device_info: AsyncMock,
    mock_async_zeroconf: MagicMock,
    device_info: QubeDeviceInfo | None,
    unique_id: str | None,
) -> None:
    """Test the user flow, with and without the controller's mDNS record."""
    mock_device_info.return_value = device_info

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "qube.local"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Qube heat pump"
    assert result["data"] == {CONF_HOST: "qube.local", CONF_PORT: 502}
    assert result["result"].unique_id == unique_id
    mock_device_info.assert_awaited_once_with(
        "qube.local", mock_async_zeroconf, timeout=MDNS_LOOKUP_TIMEOUT
    )


@pytest.mark.parametrize(
    ("connect_side_effect", "connect_result", "version_result", "error"),
    [
        (None, False, "2.15", "cannot_connect"),
        (OSError, None, "2.15", "cannot_connect"),
        (None, True, None, "not_qube_device"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_errors(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    connect_side_effect: type[Exception] | None,
    connect_result: bool | None,
    version_result: str | None,
    error: str,
) -> None:
    """Test flow error handling with recovery."""
    mock_qube_client.connect = AsyncMock(
        side_effect=connect_side_effect, return_value=connect_result
    )
    mock_qube_client.async_get_software_version = AsyncMock(return_value=version_result)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Reset mocks for successful retry
    mock_qube_client.connect = AsyncMock(return_value=True)
    mock_qube_client.async_get_software_version = AsyncMock(return_value="2.15")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_already_configured(
    hass: HomeAssistant, mock_qube_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_already_configured_by_unique_id(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_device_info: AsyncMock,
) -> None:
    """Test we abort when the same controller is added under another host."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "qube.local", CONF_PORT: 502},
        unique_id=DEVICE_INFO.uuid,
    ).add_to_hass(hass)
    mock_device_info.return_value = DEVICE_INFO

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
