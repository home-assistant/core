"""Test the Nightscout config flow."""
from aiohttp import ClientConnectionError

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.nightscout.const import DOMAIN
from homeassistant.components.nightscout.utils import hash_from_url
from homeassistant.const import CONF_URL

from tests.async_mock import patch
from tests.common import MockConfigEntry
from tests.components.nightscout import GLUCOSE_READINGS, SERVER_STATUS

CONFIG = {CONF_URL: "https://some.url:1234"}


async def test_form(hass):
    """Test we get the user initiated form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with _patch_glucose_readings(), _patch_server_status(), _patch_async_setup() as mock_setup, _patch_async_setup_entry() as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG,
        )

        assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result2["title"] == SERVER_STATUS.name  # pylint: disable=maybe-no-member
        assert result2["data"] == CONFIG
        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1


async def test_user_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nightscout.NightscoutAPI.get_server_status",
        side_effect=ClientConnectionError(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: "https://some.url:1234"},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_form_unexpected_exception(hass):
    """Test we handle unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nightscout.NightscoutAPI.get_server_status",
        side_effect=Exception(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: "https://some.url:1234"},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_user_form_duplicate(hass):
    """Test duplicate entries."""
    with _patch_glucose_readings(), _patch_server_status():
        unique_id = hash_from_url(CONFIG[CONF_URL])
        entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id)
        await hass.config_entries.async_add(entry)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=CONFIG,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


def _patch_async_setup():
    return patch("homeassistant.components.nightscout.async_setup", return_value=True)


def _patch_async_setup_entry():
    return patch(
        "homeassistant.components.nightscout.async_setup_entry", return_value=True,
    )


def _patch_glucose_readings():
    return patch(
        "homeassistant.components.nightscout.NightscoutAPI.get_sgvs",
        return_value=GLUCOSE_READINGS,
    )


def _patch_server_status():
    return patch(
        "homeassistant.components.nightscout.NightscoutAPI.get_server_status",
        return_value=SERVER_STATUS,
    )
