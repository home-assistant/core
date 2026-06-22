"""Test the Midea ccm15 AC Controller config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.ccm15.const import (
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.httpx_client import get_async_client

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_test_connection",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 80,
        CONF_MIN_TEMP: DEFAULT_MIN_TEMP,
        CONF_MAX_TEMP: DEFAULT_MAX_TEMP,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_host(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_test_connection",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    assert len(mock_setup_entry.mock_calls) == 0

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_test_connection", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.0.0.1",
            },
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_test_connection", return_value=False
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_test_connection", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.0.0.1",
            },
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_unexpected_error(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_test_connection",
        side_effect=Exception(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_test_connection", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.0.0.1",
            },
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate_host(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.1.1.1",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 80,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 80,
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("min_temp", "max_temp"),
    [
        pytest.param(25, 20, id="min_greater_than_max"),
        pytest.param(25, 25, id="min_equal_to_max"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_invalid_temp_range(
    hass: HomeAssistant, min_temp: int, max_temp: int
) -> None:
    """The user step rejects both min > max and min == max."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_test_connection", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_MIN_TEMP: min_temp,
                CONF_MAX_TEMP: max_temp,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_temp_range"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure(hass: HomeAssistant) -> None:
    """Test the reconfigure flow updates the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.1.1.1",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 80,
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_test_connection", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 80,
                CONF_MIN_TEMP: 17,
                CONF_MAX_TEMP: 28,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert entry.data[CONF_MIN_TEMP] == 17
    assert entry.data[CONF_MAX_TEMP] == 28


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_cannot_connect(hass: HomeAssistant) -> None:
    """Reconfigure surfaces cannot_connect when the probe returns False, then recovers."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.1.1.1",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 80,
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_test_connection", return_value=False
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 80,
                CONF_MIN_TEMP: 18,
                CONF_MAX_TEMP: 30,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reconfigure"
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_test_connection", return_value=True
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 80,
                CONF_MIN_TEMP: 18,
                CONF_MAX_TEMP: 30,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_unknown_error(hass: HomeAssistant) -> None:
    """Reconfigure surfaces an unknown error when the probe raises."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.1.1.1",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 80,
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_test_connection",
        side_effect=Exception(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 80,
                CONF_MIN_TEMP: 18,
                CONF_MAX_TEMP: 30,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reconfigure"
    assert result2["errors"] == {"base": "unknown"}


@pytest.mark.parametrize(
    ("min_temp", "max_temp"),
    [
        pytest.param(28, 20, id="min_greater_than_max"),
        pytest.param(28, 28, id="min_equal_to_max"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_invalid_temp_range(
    hass: HomeAssistant, min_temp: int, max_temp: int
) -> None:
    """The reconfigure step rejects both min > max and min == max."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.1.1.1",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 80,
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_test_connection", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 80,
                CONF_MIN_TEMP: min_temp,
                CONF_MAX_TEMP: max_temp,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reconfigure"
    assert result2["errors"] == {"base": "invalid_temp_range"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_duplicate_host(hass: HomeAssistant) -> None:
    """Reconfigure must reject changing host/port to match another entry."""
    other = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.1.1.1",
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 80},
    )
    other.add_to_hass(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="2.2.2.2",
        data={CONF_HOST: "2.2.2.2", CONF_PORT: 80},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with patch(
        "ccm15.CCM15Device.CCM15Device.async_test_connection", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 80,
                CONF_MIN_TEMP: 18,
                CONF_MAX_TEMP: 30,
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_uses_shared_httpx_client(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """The config flow passes HA's shared httpx client to the library.

    Letting the library build its own client runs blocking certifi/SSL setup on
    the event loop, which aborts the flow; the shared client avoids that.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ccm15.config_flow.CCM15Device", autospec=True
    ) as mock_device:
        mock_device.return_value.async_test_connection.return_value = True
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert mock_device.call_args.kwargs["client"] is get_async_client(hass)
