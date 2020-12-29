"""Test the Terncy config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.terncy.config_flow import _get_discovered_devices
from homeassistant.components.terncy.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_IP,
    CONF_NAME,
    CONF_PORT,
    DOMAIN,
    TERNCY_HUB_SVC_NAME,
)

from tests.async_mock import Mock, patch

PATCH_MODULE = "homeassistant.components.terncy.config_flow"
HUB_DEV_ID = "box-12-34-56-78-90-ab"


async def _mock_request_token(username, name):
    return 200, 42, "abcd", 1


async def _mock_check_token_state_ok(token_id, token):
    return 200, 3


async def _mock_check_token_state_invalid(token_id, token):
    return 200, 1


async def _mock_check_token_state_fail(token_id, token):
    return 401, 0


mock_terncy_auth_ok = Mock()
mock_terncy_auth_ok.request_token = _mock_request_token
mock_terncy_auth_ok.check_token_state = _mock_check_token_state_ok
mock_terncy_auth_invalid = Mock()
mock_terncy_auth_invalid.request_token = _mock_request_token
mock_terncy_auth_invalid.check_token_state = _mock_check_token_state_invalid
mock_terncy_auth_fail = Mock()
mock_terncy_auth_fail.request_token = _mock_request_token
mock_terncy_auth_fail.check_token_state = _mock_check_token_state_fail


def _patch_start_discovery():
    def _mocked_start_discovery(mgr):
        pass

    return patch(
        f"{PATCH_MODULE}._start_discovery",
        side_effect=_mocked_start_discovery,
    )


def _patch_discovery(no_device=False):
    def _mocked_get_discovered_devices(mgr):
        if no_device:
            return {}
        return {
            HUB_DEV_ID: {
                CONF_NAME: "terncy hub",
                CONF_IP: "192.168.1.100",
                CONF_PORT: 443,
            }
        }

    return patch(
        f"{PATCH_MODULE}._get_discovered_devices",
        side_effect=_mocked_get_discovered_devices,
    )


def _patch_get_terncy_instance(state):
    def _mocked_get_terncy_instance(flow):
        if state == 0:
            return mock_terncy_auth_invalid
        elif state == 1:
            return mock_terncy_auth_fail
        else:
            return mock_terncy_auth_ok

    return patch(
        f"{PATCH_MODULE}._get_terncy_instance",
        side_effect=_mocked_get_terncy_instance,
    )


async def test_user_form_no_selection(hass):
    """Test we get the form."""
    with _patch_discovery(False):
        await setup.async_setup_component(hass, "persistent_notification", {})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=None
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == "user"


async def test_user_form(hass):
    """Test we get the form."""
    with _patch_discovery():
        await setup.async_setup_component(hass, "persistent_notification", {})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        uinput = {
            CONF_DEVICE: HUB_DEV_ID,
        }
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=uinput
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == "begin_pairing"


async def test_zeroconf(hass):
    """Test zeroconf."""
    with _patch_start_discovery():
        with _patch_discovery(True):
            await setup.async_setup_component(hass, "persistent_notification", {})
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_ZEROCONF},
                data={
                    "name": HUB_DEV_ID + "." + TERNCY_HUB_SVC_NAME,
                    CONF_HOST: "192.168.1.100",
                    "hostname": "terncy-123.local",
                    CONF_PORT: 443,
                    "properties": {
                        CONF_NAME: "terncy hub",
                        CONF_IP: "192.168.1.100",
                        CONF_PORT: 443,
                    },
                },
            )
            assert result["type"] == "form"
            assert result["step_id"] == "confirm"
            with _patch_get_terncy_instance(1):
                uinput = {}
                result2 = await hass.config_entries.flow.async_configure(
                    result["flow_id"], user_input=uinput
                )
                assert result2["type"] == "form"
                assert result2["step_id"] == "begin_pairing"


async def test_begin_pairing(hass):
    """Test pairing."""
    with _patch_discovery():
        await setup.async_setup_component(hass, "persistent_notification", {})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        uinput = {
            CONF_DEVICE: HUB_DEV_ID,
        }
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=uinput
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == "begin_pairing"
        with _patch_get_terncy_instance(0):
            result3 = await hass.config_entries.flow.async_configure(
                result2["flow_id"], user_input=None
            )
            assert result3["type"] == "form"
            assert result3["step_id"] == "begin_pairing"

        with _patch_get_terncy_instance(1):
            result3 = await hass.config_entries.flow.async_configure(
                result2["flow_id"], user_input=None
            )
            assert result3["type"] == "form"
            assert result3["step_id"] == "begin_pairing"

        with _patch_get_terncy_instance(2):
            result3 = await hass.config_entries.flow.async_configure(
                result2["flow_id"], user_input=None
            )
            assert result3["type"] == "create_entry"


async def test_get_discovered_hubs(hass):
    """Test discovery."""
    hubs = _get_discovered_devices(None)
    assert isinstance(hubs, dict)
