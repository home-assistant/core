"""Test the Shark IQ config flow."""
import aiohttp
from sharkiqpy import SharkIqAuthError

from homeassistant import config_entries, setup
from homeassistant.components.sharkiq.const import DOMAIN

from .const import CONFIG, TEST_PASSWORD, TEST_USERNAME, UNIQUE_ID

from tests.async_mock import MagicMock, PropertyMock, patch
from tests.common import MockConfigEntry


def _create_mocked_ayla(connect=None):
    """Create a mocked AylaApi object."""
    mocked_ayla = MagicMock()
    type(mocked_ayla).sign_in = PropertyMock(side_effect=connect)
    type(mocked_ayla).async_sign_in = PropertyMock(side_effect=connect)
    return mocked_ayla


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch("sharkiqpy.AylaApi.async_sign_in", return_value=True), patch(
        "homeassistant.components.sharkiq.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.sharkiq.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == f"{TEST_USERNAME:s}"
    assert result2["data"] == {
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mocked_ayla = _create_mocked_ayla(connect=SharkIqAuthError)

    with patch(
        "homeassistant.components.sharkiq.config_flow.get_ayla_api",
        return_value=mocked_ayla,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mocked_ayla = _create_mocked_ayla(connect=aiohttp.ClientError)

    with patch(
        "homeassistant.components.sharkiq.config_flow.get_ayla_api",
        return_value=mocked_ayla,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_other_error(hass):
    """Test we handle other errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mocked_ayla = _create_mocked_ayla(connect=TypeError)

    with patch(
        "homeassistant.components.sharkiq.config_flow.get_ayla_api",
        return_value=mocked_ayla,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_reauth(hass):
    """Test reauth flow."""
    with patch(
        "homeassistant.components.sharkiq.vacuum.async_setup_entry",
        return_value=True,
    ), patch("sharkiqpy.AylaApi.async_sign_in", return_value=True):
        mock_config = MockConfigEntry(domain=DOMAIN, unique_id=UNIQUE_ID, data=CONFIG)
        mock_config.add_to_hass(hass)
        hass.config_entries.async_update_entry(mock_config, data=CONFIG)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reauth", "unique_id": UNIQUE_ID}, data=CONFIG
        )

        assert result["type"] == "abort"
        assert result["reason"] == "reauth_successful"

    with patch("sharkiqpy.AylaApi.async_sign_in", side_effect=SharkIqAuthError):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "unique_id": UNIQUE_ID},
            data=CONFIG,
        )
        assert result["type"] == "form"
        assert result["errors"] == {"base": "invalid_auth"}

    with patch("sharkiqpy.AylaApi.async_sign_in", side_effect=RuntimeError):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "unique_id": UNIQUE_ID},
            data=CONFIG,
        )

        assert result["type"] == "abort"
        assert result["reason"] == "unknown"
