"""Test the FireServiceRota config flow."""
from homeassistant import config_entries, setup
from pyfireservicerota import FireServiceRota, InvalidAuthError
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_URL, CONF_USERNAME
from homeassistant import data_entry_flow
from homeassistant.components.fireservicerota.const import DOMAIN, URL_LIST  # pylint: disable=unused-import

from tests.async_mock import patch
import pytest

MOCK_CONF = {
    CONF_USERNAME: "my@email.address",
    CONF_PASSWORD: "mypassw0rd",
    CONF_URL: "https://brandweerrooster.nl"
}

@pytest.fixture(name="mock_fireservicerota")
def mock_fireservicerota():
    """Mock FireServiceRota."""
    with patch("homeassistant.components.fireservicerota.config_flow.FireServiceRota",) as fireservice:
        fireservice.return_value.get_full_name.return_value = MOCK_CONF[CONF_ID]
        yield fireservice.return_value

async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_user(hass, mock_fireservicerota):
    """Test registering an integration and finishing flow works."""

    with patch(
        "homeassistant.components.fireservicerota.async_setup_entry", return_value=True
    ), patch("homeassistant.components.fireservicerota.async_setup", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_CONF
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == MOCK_CONF



# async def test_full_flow(hass, aiohttp_client, aioclient_mock):
#     """Check full flow."""
#     assert await setup.async_setup_component(
#         hass,
#         "fireservicerota",
#         {
#             "fireservicerota": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
#             "http": {"base_url": "https://example.com"},
#         },
#     )

#     result = await hass.config_entries.flow.async_init(
#         "fireservicerota", context={"source": config_entries.SOURCE_USER}
#     )
#     state = config_entry_oauth2_flow._encode_jwt(hass, {"flow_id": result["flow_id"]})

#     assert result["url"] == (
#         f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
#         "&redirect_uri=https://example.com/auth/external/callback"
#         f"&state={state}"
#     )

#     client = await aiohttp_client(hass.http.app)
#     resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
#     assert resp.status == 200
#     assert resp.headers["content-type"] == "text/html; charset=utf-8"

#     aioclient_mock.post(
#         OAUTH2_TOKEN,
#         json={
#             "refresh_token": "mock-refresh-token",
#             "access_token": "mock-access-token",
#             "type": "Bearer",
#             "expires_in": 60,
#         },
#     )

#     with patch(
#         "homeassistant.components.fireservicerota.async_setup_entry", return_value=True
#     ) as mock_setup:
#         await hass.config_entries.flow.async_configure(result["flow_id"])

#     assert len(hass.config_entries.async_entries(DOMAIN)) == 1
#     assert len(mock_setup.mock_calls) == 1
