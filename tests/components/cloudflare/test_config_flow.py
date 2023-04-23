"""Test the Cloudflare config flow."""
from pycfdns.exceptions import (
    CloudflareAuthenticationException,
    CloudflareConnectionException,
    CloudflareZoneException,
)

from homeassistant.components.cloudflare.const import CONF_RECORDS, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_API_TOKEN, CONF_SOURCE, CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    ENTRY_CONFIG,
    USER_INPUT,
    USER_INPUT_RECORDS,
    USER_INPUT_ZONE,
    _patch_async_setup_entry,
)

from tests.common import MockConfigEntry


async def test_user_form(hass: HomeAssistant, cfupdate_flow) -> None:
    """Test we get the user initiated form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zone"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_ZONE,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "records"
    assert result["errors"] is None

    with _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT_RECORDS,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == USER_INPUT_ZONE[CONF_ZONE]

    assert result["data"]
    assert result["data"][CONF_API_TOKEN] == USER_INPUT[CONF_API_TOKEN]
    assert result["data"][CONF_ZONE] == USER_INPUT_ZONE[CONF_ZONE]
    assert result["data"][CONF_RECORDS] == USER_INPUT_RECORDS[CONF_RECORDS]

    assert result["result"]
    assert result["result"].unique_id == USER_INPUT_ZONE[CONF_ZONE]

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_form_cannot_connect(hass: HomeAssistant, cfupdate_flow) -> None:
    """Test we handle cannot connect error."""
    instance = cfupdate_flow.return_value

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    instance.get_zones.side_effect = CloudflareConnectionException()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_form_invalid_auth(hass: HomeAssistant, cfupdate_flow) -> None:
    """Test we handle invalid auth error."""
    instance = cfupdate_flow.return_value

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    instance.get_zones.side_effect = CloudflareAuthenticationException()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_form_invalid_zone(hass: HomeAssistant, cfupdate_flow) -> None:
    """Test we handle invalid zone error."""
    instance = cfupdate_flow.return_value

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    instance.get_zones.side_effect = CloudflareZoneException()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_zone"}


async def test_user_form_unexpected_exception(
    hass: HomeAssistant, cfupdate_flow
) -> None:
    """Test we handle unexpected exception."""
    instance = cfupdate_flow.return_value

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    instance.get_zones.side_effect = Exception()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_user_form_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test that configuring more than one instance is rejected."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=USER_INPUT,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_reauth_flow(hass: HomeAssistant, cfupdate_flow) -> None:
    """Test the reauthentication configuration flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": entry.unique_id,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "other_token"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert entry.data[CONF_API_TOKEN] == "other_token"
    assert entry.data[CONF_ZONE] == ENTRY_CONFIG[CONF_ZONE]
    assert entry.data[CONF_RECORDS] == ENTRY_CONFIG[CONF_RECORDS]

    assert len(mock_setup_entry.mock_calls) == 1
