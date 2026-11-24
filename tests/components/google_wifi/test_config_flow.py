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
from .conftest import HARDWARE_ID
from .const import build_response

DEVICES = (
    ("192.168.86.1", "hardware-1"),
    ("192.168.86.2", "hardware-2"),
    ("192.168.86.3", "hardware-3"),
)


def _mock_devices(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock the three Google Wifi devices."""
    for host, hardware_id in DEVICES:
        mock_device(aioclient_mock, host, hardware_id=hardware_id)


async def test_user_flow_adds_each_device(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the user can add a separate config entry for each device."""
    _mock_devices(aioclient_mock)

    for host, hardware_id in DEVICES:
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
        assert result["result"].unique_id == hardware_id

    assert len(hass.config_entries.async_entries(DOMAIN)) == 3


async def test_user_flow_rejects_duplicate_device(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test adding the same router again updates its address."""
    _mock_devices(aioclient_mock)
    mock_device(aioclient_mock, "192.168.86.4", hardware_id="hardware-1")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.1"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "hardware-1"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.4"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_HOST] == "192.168.86.4"
    assert entries[0].title == "192.168.86.4"


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
    mock_device(aioclient_mock, "192.168.86.1", hardware_id="hardware-1")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.1"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "hardware-1"


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
    mock_device(aioclient_mock, "192.168.86.9", hardware_id="hardware-9")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.9"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_missing_hardware_id(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a status response without a hardware ID is invalid."""
    aioclient_mock.get(
        "http://192.168.86.9/api/v1/status",
        json=build_response(hardware_id=""),
    )
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
    mock_device(aioclient_mock, "192.168.86.9", hardware_id="hardware-9")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.9"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "hardware-9"


async def test_user_flow_unexpected_exception(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an unexpected API exception is reported by the user flow."""
    mock_device(aioclient_mock, "192.168.86.1", hardware_id="hardware-1")

    with patch(
        "homeassistant.components.google_wifi.config_flow.async_get_hardware_id",
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
    assert result["result"].unique_id == "hardware-1"


@pytest.mark.usefixtures("mock_success")
async def test_reconfigure_updates_host(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reconfigure changes the address of the same device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HARDWARE_ID,
        title="192.168.86.1",
        data={CONF_HOST: "192.168.86.1"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_device(aioclient_mock, "192.168.86.9", hardware_id=HARDWARE_ID)
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
async def test_reconfigure_rejects_different_device(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure does not point an entry at a different device."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_device(aioclient_mock, "192.168.86.2", hardware_id="hardware-2")
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.86.2"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
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
    mock_device(aioclient_mock, "192.168.86.9", hardware_id=HARDWARE_ID)
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
        "homeassistant.components.google_wifi.config_flow.async_get_hardware_id",
        side_effect=RuntimeError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: "192.168.86.9", "name": "Google Wifi"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


@pytest.mark.parametrize(
    ("existing_titles", "expected_title"),
    [
        (("Living Room",), "Living Room 192.168.86.9"),
        (
            ("Living Room", "Living Room 192.168.86.9"),
            "192.168.86.9",
        ),
    ],
)
async def test_import_name_collision(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    existing_titles: tuple[str, ...],
    expected_title: str,
) -> None:
    """Test YAML import titles avoid collisions."""
    for index, title in enumerate(existing_titles):
        MockConfigEntry(
            domain=DOMAIN,
            unique_id=f"existing-{index}",
            title=title,
            data={CONF_HOST: f"192.168.86.{index + 1}"},
        ).add_to_hass(hass)

    mock_device(aioclient_mock, "192.168.86.9", hardware_id="hardware-9")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "192.168.86.9", "name": "Living Room"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
    assert result["result"].unique_id == "hardware-9"
