"""Test the Vitrea config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.vitrea.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_vitrea_client) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.vitrea.config_flow.VitreaClient",
        return_value=mock_vitrea_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 3000,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Vitrea (192.168.1.100)"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 3000,
    }


async def test_form_cannot_connect(hass: HomeAssistant, mock_vitrea_client) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_vitrea_client.connect.side_effect = ConnectionError

    with patch(
        "homeassistant.components.vitrea.config_flow.VitreaClient",
        return_value=mock_vitrea_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 3000,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_timeout(hass: HomeAssistant, mock_vitrea_client) -> None:
    """Test we handle timeout error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_vitrea_client.connect.side_effect = TimeoutError

    with patch(
        "homeassistant.components.vitrea.config_flow.VitreaClient",
        return_value=mock_vitrea_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 3000,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "timeout_connect"}


async def test_form_unknown_error(hass: HomeAssistant, mock_vitrea_client) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_vitrea_client.connect.side_effect = Exception("Unexpected error")

    with patch(
        "homeassistant.components.vitrea.config_flow.VitreaClient",
        return_value=mock_vitrea_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 3000,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we handle duplicate entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 3000,
        },
        unique_id="192.168.1.100",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.vitrea.config_flow.VitreaClient",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 3000,
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_vitrea_client, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with (
        patch(
            "homeassistant.components.vitrea.config_flow.VitreaClient",
            return_value=mock_vitrea_client,
        ),
        patch(
            "homeassistant.components.vitrea.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.200",
                CONF_PORT: 4000,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_HOST: "192.168.1.200",
        CONF_PORT: 4000,
    }


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant, mock_vitrea_client, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow with connection error."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_vitrea_client.connect.side_effect = ConnectionError

    with patch(
        "homeassistant.components.vitrea.config_flow.VitreaClient",
        return_value=mock_vitrea_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.200",
                CONF_PORT: 4000,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
