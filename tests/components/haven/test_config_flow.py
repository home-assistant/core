"""Test the HAVEN IAQ config flow."""

from unittest.mock import ANY, AsyncMock, MagicMock

from haveniaq import (
    DeviceInfo,
    HavenApiError,
    HavenUnsupportedApiVersionError,
    HavenUnsupportedProductError,
)
import pytest

from homeassistant.components.haven.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    TEST_HOST,
    TEST_INFO,
    TEST_SERIAL,
    TEST_UNSUPPORTED_CONTROLLER_INFO,
    ZEROCONF_DISCOVERY,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_success(
    hass: HomeAssistant, mock_haven_client: AsyncMock
) -> None:
    """Test manual setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Room Air Monitor {TEST_SERIAL}"
    assert result["data"] == {CONF_HOST: TEST_HOST}
    assert result["result"].unique_id == TEST_SERIAL


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("first_response", "expected"),
    [
        pytest.param(
            HavenApiError("Unable to connect"),
            "cannot_connect",
            id="cannot-connect",
        ),
        pytest.param(
            HavenUnsupportedApiVersionError("Unsupported API version"),
            "unsupported_api_version",
            id="unsupported-api-version",
        ),
        pytest.param(
            HavenUnsupportedProductError("Unsupported product"),
            "unsupported_product",
            id="unsupported-product",
        ),
        pytest.param(
            DeviceInfo.from_dict(TEST_UNSUPPORTED_CONTROLLER_INFO),
            "unsupported_product",
            id="missing-air-quality-capability",
        ),
    ],
)
async def test_user_flow_error_then_recovers(
    hass: HomeAssistant,
    mock_haven_client: AsyncMock,
    first_response: DeviceInfo | Exception,
    expected: str,
) -> None:
    """Test manual setup errors remain actionable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_haven_client.get_info.side_effect = [
        first_response,
        DeviceInfo.from_dict(TEST_INFO),
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected}

    new_host = "192.0.2.2"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: new_host}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Room Air Monitor {TEST_SERIAL}"
    assert result["data"] == {CONF_HOST: new_host}
    assert result["result"].unique_id == TEST_SERIAL


async def test_user_flow_aborts_duplicate(
    hass: HomeAssistant,
    mock_haven_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test manual setup updates and rejects an already configured device."""
    new_host = "192.0.2.2"
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: new_host}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {CONF_HOST: new_host}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_success(
    hass: HomeAssistant,
    mock_haven_client: AsyncMock,
    mock_haven_client_class: MagicMock,
) -> None:
    """Test zeroconf discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    mock_haven_client_class.assert_called_once_with(
        TEST_HOST,
        session=ANY,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Room Air Monitor {TEST_SERIAL}"
    assert result["data"] == {CONF_HOST: TEST_HOST}
    assert result["result"].unique_id == TEST_SERIAL


async def test_discovery_confirm_aborts_without_state(
    hass: HomeAssistant, mock_haven_client: AsyncMock
) -> None:
    """Test restored discovery aborts when its saved state is missing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    flow = hass.config_entries.flow.async_get(result["flow_id"])
    flow["context"].pop("title_placeholders")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_zeroconf_updates_existing_entry(
    hass: HomeAssistant, mock_haven_client: AsyncMock
) -> None:
    """Test rediscovery updates the host on an existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SERIAL,
        data={CONF_HOST: "192.0.2.2"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {CONF_HOST: TEST_HOST}


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(
            HavenApiError("Unable to connect"),
            "cannot_connect",
            id="cannot-connect",
        ),
        pytest.param(
            HavenUnsupportedApiVersionError("Unsupported API version"),
            "unsupported_api_version",
            id="unsupported-api-version",
        ),
        pytest.param(
            HavenUnsupportedProductError("Unsupported product"),
            "unsupported_product",
            id="unsupported-product",
        ),
    ],
)
async def test_zeroconf_aborts_on_device_errors(
    hass: HomeAssistant,
    mock_haven_client: AsyncMock,
    error: Exception,
    expected: str,
) -> None:
    """Test discovery failures abort with specific reasons."""
    mock_haven_client.get_info.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected
