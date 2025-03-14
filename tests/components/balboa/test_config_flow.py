"""Test the Balboa Spa Client config flow."""

from unittest.mock import MagicMock, patch

from pybalboa.exceptions import SpaConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.balboa.const import CONF_SYNC_TIME, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry

TEST_HOST = "1.1.1.1"
TEST_DATA = {CONF_HOST: TEST_HOST}
TEST_MAC = "ef:ef:ef:c0:ff:ee"
TEST_DHCP_SERVICE_INFO = DhcpServiceInfo(
    ip=TEST_HOST, macaddress=TEST_MAC.replace(":", ""), hostname="fakespa"
)


async def test_form(hass: HomeAssistant, client: MagicMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.balboa.config_flow.SpaClient.__aenter__",
            return_value=client,
        ),
        patch(
            "homeassistant.components.balboa.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == TEST_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant, client: MagicMock) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.balboa.config_flow.SpaClient.__aenter__",
        return_value=client,
        side_effect=SpaConnectionError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_DATA
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_spa_not_configured(hass: HomeAssistant, client: MagicMock) -> None:
    """Test we handle spa not configured error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.balboa.config_flow.SpaClient.__aenter__",
        return_value=client,
    ):
        client.async_configuration_loaded.return_value = False
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_DATA
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_unknown_error(hass: HomeAssistant, client: MagicMock) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.balboa.config_flow.SpaClient.__aenter__",
        return_value=client,
        side_effect=Exception("Boom"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_already_configured(hass: HomeAssistant, client: MagicMock) -> None:
    """Test when provided credentials are already configured."""
    MockConfigEntry(domain=DOMAIN, data=TEST_DATA, unique_id=TEST_MAC).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.balboa.config_flow.SpaClient.__aenter__",
            return_value=client,
        ),
        patch(
            "homeassistant.components.balboa.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant, client: MagicMock) -> None:
    """Test specifying non default settings using options flow."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_DATA, unique_id=TEST_MAC)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    with patch(
        "homeassistant.components.balboa.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_SYNC_TIME: True},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert dict(config_entry.options) == {CONF_SYNC_TIME: True}


async def test_dhcp_discovery(hass: HomeAssistant, client: MagicMock) -> None:
    """Test we can process the discovery from dhcp."""
    with patch(
        "homeassistant.components.balboa.config_flow.SpaClient.__aenter__",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=TEST_DHCP_SERVICE_INFO,
        )

        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "FakeSpa"
        assert result["data"] == TEST_DATA
        assert result["result"].unique_id == TEST_MAC

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=TEST_DHCP_SERVICE_INFO,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_dhcp_discovery_updates_host(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test dhcp discovery updates host and aborts."""
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_DATA, unique_id=TEST_MAC)
    entry.add_to_hass(hass)

    updated_ip = "1.1.1.2"
    TEST_DHCP_SERVICE_INFO.ip = updated_ip
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=TEST_DHCP_SERVICE_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.data[CONF_HOST] == updated_ip


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (SpaConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_dhcp_discovery_failed(
    hass: HomeAssistant, client: MagicMock, side_effect: Exception, reason: str
) -> None:
    """Test failed setup from dhcp."""
    with patch(
        "homeassistant.components.balboa.config_flow.SpaClient.__aenter__",
        return_value=client,
        side_effect=side_effect(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=TEST_DHCP_SERVICE_INFO,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == reason


async def test_dhcp_discovery_manual_user_setup(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test dhcp discovery with manual user setup."""
    with patch(
        "homeassistant.components.balboa.config_flow.SpaClient.__aenter__",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=TEST_DHCP_SERVICE_INFO,
        )

        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == TEST_DATA
