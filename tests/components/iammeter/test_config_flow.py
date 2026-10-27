"""Test IAMMETER UI, import and reconfiguration flows."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from requests.exceptions import ConnectionError, HTTPError, Timeout

from homeassistant.components.iammeter.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_DATA, MOCK_INPUT

pytestmark = pytest.mark.usefixtures("mock_setup_entry", "mock_meter")


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the form and successful meter identification."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_INPUT
    assert result["result"].unique_id == "test-meter"
    assert result["title"] == "IamMeter"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ConnectionError(), "cannot_connect"),
        (Timeout(), "cannot_connect"),
        (TimeoutError(), "cannot_connect"),
        (HTTPError(), "cannot_connect"),
        (ValueError(), "invalid_data"),
        (KeyError(), "invalid_data"),
        (IndexError(), "invalid_data"),
        (TypeError(), "invalid_data"),
        (UnboundLocalError(), "invalid_data"),
        (RuntimeError(), "unknown"),
    ],
)
async def test_errors_and_recovery(
    hass: HomeAssistant, mock_meter: MagicMock, error: Exception, expected: str
) -> None:
    """An error leaves the form available for another connection attempt."""
    mock_meter.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}
    mock_meter.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "data",
    [
        {**MOCK_DATA, "sn": ""},
        {**MOCK_DATA, "sn": "   "},
        {**MOCK_DATA, "sn": None},
        {**MOCK_DATA, "Model": "unsupported"},
    ],
)
async def test_invalid_identity(
    hass: HomeAssistant, mock_meter: MagicMock, data: dict[str, Any]
) -> None:
    """Reject endpoints without a stable, supported identity."""
    mock_meter.return_value.measurement = data
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_INPUT
    )
    assert result["errors"] == {"base": "invalid_data"}
    mock_meter.return_value.measurement = MOCK_DATA.copy()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "test-meter"


@pytest.mark.parametrize("source", [SOURCE_USER, SOURCE_IMPORT])
async def test_duplicate(
    hass: HomeAssistant, mock_entry: MockConfigEntry, source: str
) -> None:
    """Both YAML and UI deduplicate by serial, including a different IP."""
    mock_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data={**MOCK_INPUT, CONF_HOST: "192.0.2.2"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_entry.data == MOCK_INPUT


async def test_multiple_devices(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_meter: MagicMock
) -> None:
    """A different serial creates a second entry."""
    mock_entry.add_to_hass(hass)
    mock_meter.return_value.measurement = {**MOCK_DATA, "sn": "second-meter"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**MOCK_INPUT, CONF_HOST: "192.0.2.2"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "second-meter"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


@pytest.mark.parametrize(
    ("name", "title"), [({}, "IamMeter"), ({CONF_NAME: "Solar"}, "Solar")]
)
async def test_import(hass: HomeAssistant, name: dict[str, str], title: str) -> None:
    """Import the legacy platform name without storing YAML-only keys."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "192.0.2.1", "platform": DOMAIN, **name},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "test-meter"
    assert result["title"] == title
    assert result["data"] == MOCK_INPUT


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (ConnectionError(), "cannot_connect"),
        (ValueError(), "invalid_data"),
        (RuntimeError(), "unknown"),
    ],
)
async def test_import_error(
    hass: HomeAssistant, mock_meter: MagicMock, error: Exception, reason: str
) -> None:
    """A failed import does not create a broken config entry."""
    mock_meter.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_reconfigure(hass: HomeAssistant, mock_entry: MockConfigEntry) -> None:
    """Update an IP address and port and reload the same meter."""
    mock_entry.add_to_hass(hass)
    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    with patch.object(
        hass.config_entries, "async_reload", new_callable=AsyncMock
    ) as reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.0.2.2", CONF_PORT: 8080}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_entry.data == {CONF_HOST: "192.0.2.2", CONF_PORT: 8080}
    reload.assert_awaited_once_with(mock_entry.entry_id)


async def test_reconfigure_wrong_meter(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_meter: MagicMock
) -> None:
    """Do not transfer historical entities to a different physical meter."""
    mock_entry.add_to_hass(hass)
    mock_meter.return_value.measurement = {**MOCK_DATA, "sn": "other-meter"}
    result = await mock_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.2", CONF_PORT: 80}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_entry.data == MOCK_INPUT


async def test_reconfigure_error(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_meter: MagicMock
) -> None:
    """Keep the existing address on a failed reconfiguration."""
    mock_entry.add_to_hass(hass)
    mock_meter.side_effect = ConnectionError()
    result = await mock_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_INPUT
    )
    assert result["errors"] == {"base": "cannot_connect"}
    assert mock_entry.data == MOCK_INPUT

    mock_meter.side_effect = None
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_INPUT
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(
    ("address", "expected_port", "expected_host"),
    [
        ("http://192.0.2.1", 80, "http://192.0.2.1/monitorjson"),
        ("http://192.0.2.1/", 80, "http://192.0.2.1/monitorjson"),
        (
            "http://192.0.2.1:8080/monitorjson",
            8080,
            "http://192.0.2.1:8080/monitorjson",
        ),
        ("192.0.2.1:8080", 8080, "192.0.2.1"),
    ],
)
async def test_name_interval_and_url(
    hass: HomeAssistant,
    mock_meter: MagicMock,
    address: str,
    expected_port: int,
    expected_host: str,
) -> None:
    """Normalize copied addresses and save preferences separately from identity."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: address,
            CONF_PORT: 80,
            CONF_NAME: "Solar meter",
            CONF_SCAN_INTERVAL: 60,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "test-meter"
    assert result["title"] == "Solar meter"
    assert result["data"] == {CONF_HOST: expected_host, CONF_PORT: expected_port}
    assert result["options"] == {CONF_SCAN_INTERVAL: 60}
    mock_meter.assert_called_once_with(expected_host, expected_port)


@pytest.mark.parametrize(
    "address", ["ftp://192.0.2.1", "http://192.0.2.1:bad", "http://192.0.2.1/#fragment"]
)
async def test_invalid_address_recovery(
    hass: HomeAssistant, mock_meter: MagicMock, address: str
) -> None:
    """Invalid addresses show an actionable error without starting a connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**MOCK_INPUT, CONF_HOST: address}
    )
    assert result["errors"] == {"base": "invalid_host"}
    mock_meter.assert_not_called()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "test-meter"


async def test_reconfigure_interval(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Changing connection preferences keeps the existing device title and ID."""
    mock_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_entry, options={CONF_SCAN_INTERVAL: 60})
    result = await mock_entry.start_reconfigure_flow(hass)
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "http://192.0.2.2:8080/",
                CONF_PORT: 80,
                CONF_SCAN_INTERVAL: 120,
            },
        )
        await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert mock_entry.data == {
        CONF_HOST: "http://192.0.2.2:8080/monitorjson",
        CONF_PORT: 8080,
    }
    assert mock_entry.options == {CONF_SCAN_INTERVAL: 120}
    assert mock_entry.title == "IamMeter"
    assert mock_entry.unique_id == "test-meter"


async def test_import_interval(hass: HomeAssistant) -> None:
    """Preserve the legacy platform's parsed scan interval and configured name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            **MOCK_INPUT,
            CONF_NAME: "Solar",
            CONF_SCAN_INTERVAL: timedelta(seconds=45),
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "test-meter"
    assert result["options"] == {CONF_SCAN_INTERVAL: 45}


@pytest.mark.parametrize("interval", [0, 3601])
async def test_invalid_import_interval(hass: HomeAssistant, interval: int) -> None:
    """Do not silently accept an invalid polling interval from YAML."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={**MOCK_INPUT, CONF_SCAN_INTERVAL: interval},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_interval"


async def test_invalid_import_address(hass: HomeAssistant) -> None:
    """Reject invalid imported addresses with a specific reason."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={**MOCK_INPUT, CONF_HOST: "http://192.0.2.1/#fragment"},
    )
    assert result["reason"] == "invalid_host"


@pytest.mark.parametrize(
    ("url", "port", "expected_url"),
    [
        (
            "https://meter.example/WEM3080/monitorjson",
            443,
            "https://meter.example/WEM3080/monitorjson",
        ),
        (
            "http://meter.example/WEM3080/monitorjson",
            80,
            "http://meter.example/WEM3080/monitorjson",
        ),
        (
            "https://meter.example:8443/api/read?channel=A",
            8443,
            "https://meter.example:8443/api/read/monitorjson?channel=A",
        ),
    ],
)
async def test_full_data_url(
    hass: HomeAssistant, mock_meter: MagicMock, url: str, port: int, expected_url: str
) -> None:
    """Store the full endpoint so setup cannot discard its scheme or path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: url, CONF_PORT: 9999}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "test-meter"
    assert result["data"] == {CONF_HOST: expected_url, CONF_PORT: port}
    mock_meter.assert_called_once_with(expected_url, port)


async def test_reconfigure_url_to_host(hass: HomeAssistant) -> None:
    """Switch from URL mode to a bare host without a stale URL override."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Solar",
        unique_id="test-meter",
        data={CONF_HOST: "https://meter.example/WEM3080/monitorjson", CONF_PORT: 443},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.0.2.1", CONF_PORT: 8080, CONF_SCAN_INTERVAL: 30},
        )
        await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_HOST: "192.0.2.1", CONF_PORT: 8080}
    assert entry.title == "Solar"
