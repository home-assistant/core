"""Test the HAVEN IAQ config flow."""

from unittest.mock import ANY, AsyncMock, MagicMock

from haveniaq import (
    DeviceInfo,
    HavenApiError,
    HavenUnsupportedApiVersionError,
    HavenUnsupportedProductError,
)
import pytest

from homeassistant.components.haven.const import DEFAULT_PATH, DEFAULT_PORT, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PATH, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    TEST_HOST,
    TEST_INFO,
    TEST_PATH,
    TEST_PORT,
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
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: DEFAULT_PORT,
        CONF_PATH: DEFAULT_PATH,
    }
    assert result["result"].unique_id == TEST_SERIAL


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_cannot_connect_then_recovers(
    hass: HomeAssistant, mock_haven_client: AsyncMock
) -> None:
    """Test manual setup recovers from a connection failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_haven_client.get_info.side_effect = [
        HavenApiError("Unable to connect"),
        DeviceInfo.from_dict(TEST_INFO),
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (HavenUnsupportedApiVersionError, "unsupported_api_version"),
        (HavenUnsupportedProductError, "unsupported_product"),
    ],
)
async def test_user_flow_rejects_unsupported_device(
    hass: HomeAssistant,
    mock_haven_client: AsyncMock,
    error: type[Exception],
    expected: str,
) -> None:
    """Test unsupported API and product errors remain actionable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_haven_client.get_info.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )
    assert result["errors"] == {"base": expected}


async def test_user_flow_rejects_controller(
    hass: HomeAssistant, mock_haven_client: AsyncMock
) -> None:
    """Test the initial integration rejects products without air-quality data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_haven_client.get_info.return_value = DeviceInfo.from_dict(
        TEST_UNSUPPORTED_CONTROLLER_INFO
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_product"}


async def test_user_flow_aborts_duplicate(
    hass: HomeAssistant,
    mock_haven_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test manual setup rejects an already configured device."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


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
        port=TEST_PORT,
        path=TEST_PATH,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_PATH: TEST_PATH,
    }
    assert result["result"].unique_id == TEST_SERIAL


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
    assert entry.data == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_PATH: TEST_PATH,
    }


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (HavenApiError, "cannot_connect"),
        (HavenUnsupportedApiVersionError, "unsupported_api_version"),
        (HavenUnsupportedProductError, "unsupported_product"),
    ],
)
async def test_zeroconf_aborts_on_device_errors(
    hass: HomeAssistant,
    mock_haven_client: AsyncMock,
    error: type[Exception],
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
