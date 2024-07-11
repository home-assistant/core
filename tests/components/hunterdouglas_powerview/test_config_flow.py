"""Test the Hunter Douglas Powerview config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import dhcp, zeroconf
from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.const import CONF_API_VERSION, CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import DHCP_DATA, DISCOVERY_DATA, HOMEKIT_DATA

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_user_form(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    api_version: int,
) -> None:
    """Test we get the user form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"Powerview Generation {api_version}"
    assert result2["data"] == {CONF_HOST: "1.2.3.4", CONF_API_VERSION: api_version}
    assert result2["result"].unique_id == "A1B2C3D4E5G6H7"

    assert len(mock_setup_entry.mock_calls) == 1

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {}

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )
    assert result4["type"] is FlowResultType.ABORT
    assert result4["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize(("source", "discovery_info", "api_version"), DISCOVERY_DATA)
async def test_form_homekit_and_dhcp_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    source: str,
    discovery_info: dhcp.DhcpServiceInfo,
    api_version: int,
) -> None:
    """Test we get the form with homekit and dhcp source."""

    ignored_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, source=config_entries.SOURCE_IGNORE
    )
    ignored_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.hunterdouglas_powerview.Hub.query_firmware",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=discovery_info,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

    # test we can recover from the failed entry
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source},
        data=discovery_info,
    )

    result3 = await hass.config_entries.flow.async_configure(result2["flow_id"], {})
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == f"Powerview Generation {api_version}"
    assert result3["data"] == {CONF_HOST: "1.2.3.4", CONF_API_VERSION: api_version}
    assert result3["result"].unique_id == "A1B2C3D4E5G6H7"

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize(("source", "discovery_info", "api_version"), DISCOVERY_DATA)
async def test_form_homekit_and_dhcp(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    source: str,
    discovery_info: dhcp.DhcpServiceInfo | zeroconf.ZeroconfServiceInfo,
    api_version: int,
) -> None:
    """Test we get the form with homekit and dhcp source."""

    ignored_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, source=config_entries.SOURCE_IGNORE
    )
    ignored_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"
    assert result["errors"] is None
    assert result["description_placeholders"] == {
        CONF_HOST: "1.2.3.4",
        CONF_NAME: f"Powerview Generation {api_version}",
        CONF_API_VERSION: api_version,
    }

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"Powerview Generation {api_version}"
    assert result2["data"] == {CONF_HOST: "1.2.3.4", CONF_API_VERSION: api_version}
    assert result2["result"].unique_id == "A1B2C3D4E5G6H7"

    assert len(mock_setup_entry.mock_calls) == 1

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source},
        data=discovery_info,
    )
    assert result3["type"] is FlowResultType.ABORT


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize(
    ("homekit_source", "homekit_discovery", "api_version"), HOMEKIT_DATA
)
@pytest.mark.parametrize(
    ("dhcp_source", "dhcp_discovery", "dhcp_api_version"), DHCP_DATA
)
async def test_discovered_by_homekit_and_dhcp(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    homekit_source: str,
    homekit_discovery: zeroconf.ZeroconfServiceInfo,
    api_version: int,
    dhcp_source: str,
    dhcp_discovery: dhcp.DhcpServiceInfo,
    dhcp_api_version: int,
) -> None:
    """Test we get the form with homekit and abort for dhcp source when we get both."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=homekit_discovery,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp_discovery,
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_form_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    api_version: int,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Simulate a timeout error
    with patch(
        "homeassistant.components.hunterdouglas_powerview.Hub.query_firmware",
        side_effect=TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.2.3.4"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    # Now try again without the patch in place to make sure we can recover
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == f"Powerview Generation {api_version}"
    assert result3["data"] == {CONF_HOST: "1.2.3.4", CONF_API_VERSION: api_version}
    assert result3["result"].unique_id == "A1B2C3D4E5G6H7"

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_form_no_data(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    api_version: int,
) -> None:
    """Test we handle no data being returned from the hub."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.hunterdouglas_powerview.Hub.request_raw_data",
            return_value={},
        ),
        patch(
            "homeassistant.components.hunterdouglas_powerview.Hub.request_home_data",
            return_value={},
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.2.3.4"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    # Now try again without the patch in place to make sure we can recover
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == f"Powerview Generation {api_version}"
    assert result3["data"] == {CONF_HOST: "1.2.3.4", CONF_API_VERSION: api_version}
    assert result3["result"].unique_id == "A1B2C3D4E5G6H7"

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1, 2, 3])
async def test_form_unknown_exception(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    api_version: int,
) -> None:
    """Test we handle unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Simulate a transient error
    with patch(
        "homeassistant.components.hunterdouglas_powerview.config_flow.Hub.query_firmware",
        side_effect=SyntaxError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.2.3.4"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    # Now try again without the patch in place to make sure we can recover
    result2 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"Powerview Generation {api_version}"
    assert result2["data"] == {CONF_HOST: "1.2.3.4", CONF_API_VERSION: api_version}
    assert result2["result"].unique_id == "A1B2C3D4E5G6H7"

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [3])  # only gen 3 present secondary hubs
async def test_form_unsupported_device(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    api_version: int,
) -> None:
    """Test unsupported device failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Simulate a gen 3 secondary hub
    with patch(
        "homeassistant.components.hunterdouglas_powerview.Hub.request_raw_data",
        return_value=load_json_object_fixture("gen3/gateway/secondary.json", DOMAIN),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.2.3.4"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unsupported_device"}

    # Now try again without the patch in place to make sure we can recover
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_HOST: "1.2.3.4"},
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == f"Powerview Generation {api_version}"
    assert result3["data"] == {CONF_HOST: "1.2.3.4", CONF_API_VERSION: api_version}
    assert result3["result"].unique_id == "A1B2C3D4E5G6H7"

    assert len(mock_setup_entry.mock_calls) == 1
