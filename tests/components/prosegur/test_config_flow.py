"""Test the Prosegur Alarm config flow."""
from unittest.mock import MagicMock, patch

from pytest import mark

from homeassistant import config_entries
from homeassistant.components.prosegur.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.prosegur.const import DOMAIN
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    install = MagicMock()
    install.contract = "123"

    with patch(
        "homeassistant.components.prosegur.config_flow.Installation.retrieve",
        return_value=install,
    ) as mock_retrieve, patch(
        "homeassistant.components.prosegur.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country": "PT",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Contract 123"
    assert result2["data"] == {
        "contract": "123",
        "username": "test-username",
        "password": "test-password",
        "country": "PT",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    assert len(mock_retrieve.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyprosegur.installation.Installation",
        side_effect=ConnectionRefusedError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country": "PT",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyprosegur.installation.Installation",
        side_effect=ConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country": "PT",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(hass):
    """Test we handle unknown exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyprosegur.installation.Installation",
        side_effect=ValueError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country": "PT",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_reauth_flow(hass):
    """Test a reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={
            "username": "test-username",
            "password": "test-password",
            "country": "PT",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": entry.unique_id,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    install = MagicMock()
    install.contract = "123"

    with patch(
        "homeassistant.components.prosegur.config_flow.Installation.retrieve",
        return_value=install,
    ) as mock_installation, patch(
        "homeassistant.components.prosegur.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "new_password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == {
        "country": "PT",
        "username": "test-username",
        "password": "new_password",
    }

    assert len(mock_installation.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@mark.parametrize(
    "exception, base_error",
    [
        (CannotConnect, "cannot_connect"),
        (InvalidAuth, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_flow_error(hass, exception, base_error):
    """Test a reauthentication flow with errors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={
            "username": "test-username",
            "password": "test-password",
            "country": "PT",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": entry.unique_id,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    with patch(
        "homeassistant.components.prosegur.config_flow.Installation.retrieve",
        side_effect=exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "new_password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == base_error
