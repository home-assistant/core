"""Test the ViCare config flow."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vicare.const import CONF_EXTENDED_API, DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

VALID_CONFIG = {
    CONF_USERNAME: "foo@bar.com",
    CONF_PASSWORD: "1234",
    CONF_CLIENT_ID: "5678",
}

VALID_OPTIONS = {
    CONF_EXTENDED_API: False,
}


async def test_user_options(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the option step works."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data=VALID_CONFIG,
        options=VALID_OPTIONS,
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_EXTENDED_API: True},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == snapshot
