"""Test the Avocent Direct PDU config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.avocent_dpdu.const import DOMAIN
from homeassistant.const import CONF_COUNT, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "avocentdpdu.avocentdpdu.AvocentDPDU.initialize",
        return_value=None,
    ):
        with patch(
            "avocentdpdu.avocentdpdu.AvocentDPDU.is_valid_login",
            return_value=True,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: "1.1.1.1",
                    CONF_USERNAME: "test-username",
                    CONF_PASSWORD: "test-password",
                    CONF_COUNT: 8,
                },
            )
            await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Avocent Direct PDU"
        assert result["data"] == {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_COUNT: 8,
        }
        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "avocentdpdu.avocentdpdu.AvocentDPDU.initialize",
        return_value=None,
    ):
        with patch(
            "avocentdpdu.avocentdpdu.AvocentDPDU.is_valid_login",
            return_value=False,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: "1.1.1.1",
                    CONF_USERNAME: "test-username",
                    CONF_PASSWORD: "test-password",
                    CONF_COUNT: 8,
                },
            )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "avocentdpdu.avocentdpdu.AvocentDPDU.initialize",
        return_value=None,
    ):
        with patch(
            "avocentdpdu.avocentdpdu.AvocentDPDU.is_valid_login",
            return_value=True,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: "1.1.1.1",
                    CONF_USERNAME: "test-username",
                    CONF_PASSWORD: "test-password",
                    CONF_COUNT: 8,
                },
            )
            await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Avocent Direct PDU"
        assert result["data"] == {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_COUNT: 8,
        }
        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "avocentdpdu.avocentdpdu.AvocentDPDU.initialize",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_COUNT: 8,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with patch(
        "avocentdpdu.avocentdpdu.AvocentDPDU.initialize",
        return_value=None,
    ):
        with patch(
            "avocentdpdu.avocentdpdu.AvocentDPDU.is_valid_login",
            return_value=True,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: "1.1.1.1",
                    CONF_USERNAME: "test-username",
                    CONF_PASSWORD: "test-password",
                    CONF_COUNT: 8,
                },
            )
            await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Avocent Direct PDU"
        assert result["data"] == {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_COUNT: 8,
        }
        assert len(mock_setup_entry.mock_calls) == 1
