"""Test the Google Wifi config flow."""

from unittest.mock import patch

import aiohttp
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.google_wifi.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import mock_device

HOSTS = ("192.168.86.1", "192.168.86.2", "192.168.86.3")


async def test_user_flow_adds_each_device(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the user can add a separate config entry for each device."""
    for host in HOSTS:
        mock_device(aioclient_mock, host)

    for host in HOSTS:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: f"  {host}  "},
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == host
        assert result["data"] == {CONF_HOST: host}

    assert len(hass.config_entries.async_entries(DOMAIN)) == 3


async def test_user_flow_rejects_duplicate_host(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a host that is already configured cannot be added again."""
    mock_device(aioclient_mock, "192.168.86.1")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.1"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.1"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a connection error can be recovered from."""
    aioclient_mock.get(
        "http://192.168.86.1/api/v1/status",
        exc=aiohttp.ClientConnectionError("connection refused"),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.1"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    aioclient_mock.clear_requests()
    mock_device(aioclient_mock, "192.168.86.1")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.1"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.168.86.1"}


async def test_user_flow_invalid_response(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a response that is not Google Wifi status."""
    aioclient_mock.get("http://192.168.86.9/api/v1/status", json=["not-a-status"])
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.9"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_response"}

    aioclient_mock.clear_requests()
    mock_device(aioclient_mock, "192.168.86.9")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.9"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.168.86.9"}


async def test_user_flow_unexpected_exception(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an unexpected API exception is reported by the user flow."""
    mock_device(aioclient_mock, "192.168.86.1")

    with patch(
        "homeassistant.components.google_wifi.config_flow.async_validate_host",
        side_effect=RuntimeError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.86.1"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.1"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.168.86.1"}


@pytest.mark.usefixtures("mock_success")
async def test_reconfigure_updates_host(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reconfigure changes the address of a device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="192.168.86.1",
        data={CONF_HOST: "192.168.86.1"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_device(aioclient_mock, "192.168.86.9")
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.9"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.168.86.9"
    assert entry.title == "192.168.86.9"


@pytest.mark.usefixtures("mock_success")
async def test_reconfigure_rejects_host_of_another_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure cannot point an entry at a host that is already configured."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    MockConfigEntry(
        domain=DOMAIN,
        title="Office",
        data={CONF_HOST: "192.168.86.2"},
    ).add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.2"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.86.1"


@pytest.mark.usefixtures("mock_success")
async def test_reconfigure_cannot_connect(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure can return to the form after a connection error."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://192.168.86.9/api/v1/status",
        exc=aiohttp.ClientConnectionError("connection refused"),
    )
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.9"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}

    aioclient_mock.clear_requests()
    mock_device(aioclient_mock, "192.168.86.9")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.9"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.86.9"


async def test_import_invalid_response(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an invalid import response aborts the flow."""
    aioclient_mock.get("http://192.168.86.9/api/v1/status", json=["not-a-status"])

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "192.168.86.9", "name": "Google Wifi"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_response"


async def test_import_unexpected_exception(hass: HomeAssistant) -> None:
    """Test an unexpected import exception aborts the flow."""
    with patch(
        "homeassistant.components.google_wifi.config_flow.async_validate_host",
        side_effect=RuntimeError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: "192.168.86.9", "name": "Google Wifi"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_import_already_configured_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test importing a host that is already configured aborts the flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "192.168.86.1", "name": "Google Wifi"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_keeps_name_shared_with_another_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an imported entry keeps its YAML name even if another entry uses it."""
    MockConfigEntry(
        domain=DOMAIN,
        title="Living Room",
        data={CONF_HOST: "192.168.86.1"},
    ).add_to_hass(hass)
    mock_device(aioclient_mock, "192.168.86.9")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "192.168.86.9", "name": "Living Room"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room"
    assert result["data"] == {CONF_HOST: "192.168.86.9"}
