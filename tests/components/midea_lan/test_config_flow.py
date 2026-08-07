"""Tests for the Midea LAN config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from midealocal.const import DeviceType, ProtocolVersion
import pytest

from homeassistant.components.midea_lan.config_flow import (
    DEFAULT_CLOUD,
    LOGIN_MODE_ACCOUNT,
    LOGIN_MODE_PRESET,
)
from homeassistant.components.midea_lan.const import (
    CONF_ACCOUNT,
    CONF_KEY,
    CONF_SERVER,
    CONF_SUBTYPE,
    DOMAIN,
)
from homeassistant.components.midea_lan.device_catalog import MIDEA_DEVICE_NAMES
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TOKEN,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    BASE_DATA,
    DISCOVERY_RESULT,
    EXTENDED_DATA,
    TEST_DEVICE_ID,
    TEST_IP_ADDRESS,
    TEST_KEY,
    TEST_MODEL,
    TEST_PORT,
    TEST_PROTOCOL,
    TEST_SUBTYPE,
    TEST_TOKEN,
    TEST_TYPE,
)

from tests.common import MockConfigEntry, get_schema_suggested_value

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_manual_flow_success(hass: HomeAssistant) -> None:
    """Test a successful manual configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value=DISCOVERY_RESULT,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
        ) as mock_midea_device,
    ):
        mock_device = MagicMock()
        mock_device.connect.return_value = True
        mock_midea_device.return_value = mock_device

        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"next_step_id": "manually"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manually"

        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={**EXTENDED_DATA},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MIDEA_DEVICE_NAMES[TEST_TYPE]
    assert result["data"] == {
        CONF_NAME: MIDEA_DEVICE_NAMES[TEST_TYPE],
        CONF_DEVICE_ID: TEST_DEVICE_ID,
        CONF_TYPE: TEST_TYPE,
        CONF_PROTOCOL: TEST_PROTOCOL,
        CONF_IP_ADDRESS: TEST_IP_ADDRESS,
        CONF_PORT: TEST_PORT,
        CONF_MODEL: TEST_MODEL,
        CONF_SUBTYPE: TEST_SUBTYPE,
        CONF_TOKEN: TEST_TOKEN,
        CONF_KEY: TEST_KEY,
    }


async def test_manual_flow_duplicate_unique_id(hass: HomeAssistant) -> None:
    """Test manual flow aborts when device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=str(TEST_DEVICE_ID),
        version=1,
        minor_version=1,
        data={CONF_DEVICE_ID: TEST_DEVICE_ID, CONF_IP_ADDRESS: TEST_IP_ADDRESS},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value=DISCOVERY_RESULT,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
        ) as mock_midea_device,
    ):
        mock_device = MagicMock()
        mock_device.connect.return_value = True
        mock_midea_device.return_value = mock_device

        await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"next_step_id": "manually"},
        )
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={**EXTENDED_DATA},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    (
        "user_input",
        "discover_result",
        "connect_return",
        "cloud_login_return",
        "cloud_keys_return",
        "default_keys_return",
        "pre_input",
        "expected_error",
    ),
    [
        pytest.param(
            {**EXTENDED_DATA, CONF_TOKEN: "zz"},
            None,
            None,
            True,
            {},
            {},
            None,
            "invalid_token",
            id="invalid_token",
        ),
        pytest.param(
            {**EXTENDED_DATA},
            {},
            None,
            True,
            {},
            {},
            None,
            "invalid_device_ip",
            id="discover_empty",
        ),
        pytest.param(
            {**EXTENDED_DATA},
            {TEST_DEVICE_ID + 1: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            None,
            True,
            {},
            {},
            None,
            "invalid_device_id_for_ip",
            id="discover_id_mismatch",
        ),
        pytest.param(
            {**EXTENDED_DATA},
            {
                TEST_DEVICE_ID: {
                    **BASE_DATA,
                    CONF_TYPE: TEST_TYPE,
                    CONF_IP_ADDRESS: "2.2.2.2",
                },
            },
            None,
            True,
            {},
            {},
            None,
            "ip_address_mismatch",
            id="ip_mismatch",
        ),
        pytest.param(
            {**EXTENDED_DATA},
            {
                TEST_DEVICE_ID: {
                    **BASE_DATA,
                    CONF_TYPE: TEST_TYPE,
                    CONF_PROTOCOL: ProtocolVersion.V2,
                },
            },
            None,
            True,
            {},
            {},
            None,
            "protocol_mismatch",
            id="protocol_mismatch",
        ),
        pytest.param(
            {**EXTENDED_DATA},
            {
                TEST_DEVICE_ID: {
                    **BASE_DATA,
                    CONF_TYPE: DeviceType.C3,
                },
            },
            None,
            True,
            {},
            {},
            None,
            "type_mismatch",
            id="type_mismatch",
        ),
        pytest.param(
            {**EXTENDED_DATA},
            {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            False,
            True,
            {},
            {},
            None,
            "device_auth_failed",
            id="connect_fails",
        ),
        pytest.param(
            {**EXTENDED_DATA, CONF_TOKEN: "", CONF_KEY: ""},
            {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            None,
            False,
            {},
            {},
            None,
            "preset_login_failed",
            id="preset_login_fails",
        ),
        pytest.param(
            {**EXTENDED_DATA, CONF_TOKEN: "", CONF_KEY: ""},
            {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            None,
            True,
            {},
            {},
            None,
            "token_unavailable",
            id="no_token_from_cloud",
        ),
    ],
)
async def test_manual_step_errors(
    hass: HomeAssistant,
    user_input: dict[str, object],
    discover_result: dict[int, dict[str, object]] | None,
    connect_return: bool | None,
    cloud_login_return: bool,
    cloud_keys_return: dict[str, dict[str, str]],
    default_keys_return: dict[str, dict[str, str]],
    pre_input: dict[str, object] | None,
    expected_error: str,
) -> None:
    """Test every async_step_manually error branch via one parametrized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "manually"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"

    dm = MagicMock()
    dm.connect.return_value = connect_return

    cloud = MagicMock()
    cloud.login = AsyncMock(return_value=cloud_login_return)
    cloud.get_cloud_keys = AsyncMock(return_value=cloud_keys_return)

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value=discover_result,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value=default_keys_return),
        ),
    ):
        if pre_input is not None:
            await hass.config_entries.flow.async_configure(
                flow_id,
                user_input=pre_input,
            )
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input=user_input,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"
    assert result["errors"] == {"base": expected_error}


async def test_manual_step_retains_user_input_on_error(hass: HomeAssistant) -> None:
    """Test the manual form keeps the user's entered values after a validation error.

    Previously, any error re-render fell back to the (possibly empty)
    found_device defaults, discarding everything the user had just typed.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    flow_id = result["flow_id"]
    await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "manually"},
    )

    submitted = {**EXTENDED_DATA, CONF_TOKEN: "zz"}
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input=submitted,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"
    assert result["errors"] == {"base": "invalid_token"}
    data_schema = result["data_schema"].schema
    assert (
        get_schema_suggested_value(data_schema, CONF_DEVICE_ID)
        == (submitted[CONF_DEVICE_ID])
    )
    assert (
        get_schema_suggested_value(data_schema, CONF_IP_ADDRESS)
        == (submitted[CONF_IP_ADDRESS])
    )
    assert get_schema_suggested_value(data_schema, CONF_TOKEN) == "zz"


async def test_manual_step_retries_discovery_after_mismatch(
    hass: HomeAssistant,
) -> None:
    """Test resubmitting corrected data triggers a fresh discovery.

    Previously, once self.devices held a stale entry from a failed attempt,
    any later submission would fail forever with "invalid_device_id" without
    ever retrying discover(), even if the resubmitted data was correct.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    flow_id = result["flow_id"]
    await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "manually"},
    )

    dm = MagicMock()
    dm.connect.return_value = True

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            side_effect=[
                {TEST_DEVICE_ID + 1: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
                DISCOVERY_RESULT,
            ],
        ) as mock_discover,
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        # first attempt: discovery finds a different device than requested
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={**EXTENDED_DATA},
        )
        assert result["errors"] == {"base": "invalid_device_id_for_ip"}

        # resubmitting the same (now correct) data must retry discovery
        # rather than dead-ending on the stale result from the first attempt
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={**EXTENDED_DATA},
        )

    assert mock_discover.call_count == 2
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_search_flow_no_new_devices_found(hass: HomeAssistant) -> None:
    """Test the search step reports no_devices when discovery only finds already-configured devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE_ID: TEST_DEVICE_ID, CONF_IP_ADDRESS: TEST_IP_ADDRESS},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=DISCOVERY_RESULT,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: TEST_IP_ADDRESS},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"
    assert result["errors"] == {"base": "no_devices"}


async def test_auto_flow_cloud_device_info_overrides_name_and_subtype(
    hass: HomeAssistant,
) -> None:
    """Test cloud device_info overrides the entry title and subtype on creation."""
    mock_devices = {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=mock_devices,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["step_id"] == "auth_method"

    cloud = MagicMock()
    cloud.login = AsyncMock(return_value=True)
    cloud.get_device_info = AsyncMock(
        return_value={"name": "Cloud Device Name", "model_number": 3}
    )
    cloud.get_cloud_keys = AsyncMock(
        return_value={"method": {"token": TEST_TOKEN, "key": TEST_KEY}}
    )

    dm = MagicMock()
    dm.connect.return_value = True

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"login_mode": LOGIN_MODE_PRESET},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cloud Device Name"
    assert result["data"][CONF_SUBTYPE] == 3
    assert result["data"][CONF_TOKEN] == TEST_TOKEN
    assert result["data"][CONF_KEY] == TEST_KEY


async def test_auto_flow_v3_preset_phase1_cloud_keys_success(
    hass: HomeAssistant,
) -> None:
    """Test phase 1 cloud keys succeed immediately after a preset login."""
    mock_devices = {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=mock_devices,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["step_id"] == "auth_method"

    cloud = MagicMock()
    cloud.login = AsyncMock(return_value=True)
    cloud.get_device_info = AsyncMock(return_value=None)
    cloud.get_cloud_keys = AsyncMock(
        return_value={"method": {"token": TEST_TOKEN, "key": TEST_KEY}}
    )

    dm = MagicMock()
    dm.connect.return_value = True

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"login_mode": LOGIN_MODE_PRESET},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == TEST_DEVICE_ID
    assert result["data"][CONF_TOKEN] == TEST_TOKEN
    assert result["data"][CONF_KEY] == TEST_KEY


async def test_auto_flow_v3_preset_phase1_default_key_success(
    hass: HomeAssistant,
) -> None:
    """Test phase 1 falls back to the well-known default key when cloud keys are empty."""
    mock_devices = {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=mock_devices,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["step_id"] == "auth_method"

    cloud = MagicMock()
    cloud.login = AsyncMock(return_value=True)
    cloud.get_device_info = AsyncMock(return_value=None)
    cloud.get_cloud_keys = AsyncMock(return_value={})

    dm = MagicMock()
    dm.connect.return_value = True

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={"builtin": {"token": TEST_TOKEN, "key": TEST_KEY}}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"login_mode": LOGIN_MODE_PRESET},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == TEST_DEVICE_ID
    assert result["data"][CONF_TOKEN] == TEST_TOKEN
    assert result["data"][CONF_KEY] == TEST_KEY


async def test_auto_flow_v3_token_retrieval_exhausted(hass: HomeAssistant) -> None:
    """Test both phase 1 and phase 2 key retrieval failing surfaces token_unavailable."""
    mock_devices = {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=mock_devices,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["step_id"] == "auth_method"

    cloud = MagicMock()
    cloud.login = AsyncMock(return_value=True)
    cloud.get_device_info = AsyncMock(return_value=None)
    cloud.get_cloud_keys = AsyncMock(
        side_effect=[
            {
                "keyA": {"token": TEST_TOKEN, "key": TEST_KEY},
                "keyB": {"token": TEST_TOKEN, "key": TEST_KEY},
            },
            {"keyC": {"token": TEST_TOKEN, "key": TEST_KEY}},
        ]
    )

    dm = MagicMock()
    dm.connect.side_effect = [False, False, False, False]

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={"builtin": {"token": TEST_TOKEN, "key": TEST_KEY}}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"login_mode": LOGIN_MODE_PRESET},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"
    assert result["errors"] == {"base": "token_unavailable"}
    assert dm.connect.call_count == 4


async def test_auto_flow_v3_phase2_login_failed(hass: HomeAssistant) -> None:
    """Test phase 2's forced preset re-login failing surfaces preset_login_failed."""
    mock_devices = {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=mock_devices,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["step_id"] == "auth_method"

    cloud = MagicMock()
    cloud.login = AsyncMock(side_effect=[True, False])
    cloud.get_device_info = AsyncMock(return_value=None)
    cloud.get_cloud_keys = AsyncMock(return_value={})

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={}),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"login_mode": LOGIN_MODE_PRESET},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"
    assert result["errors"] == {"base": "preset_login_failed"}
    assert cloud.login.call_count == 2


async def test_auto_flow_v3_phase2_no_keys_available(hass: HomeAssistant) -> None:
    """Test phase 2 succeeding to log in but still finding no keys surfaces token_unavailable."""
    mock_devices = {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=mock_devices,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["step_id"] == "auth_method"

    cloud = MagicMock()
    cloud.login = AsyncMock(side_effect=[True, True])
    cloud.get_device_info = AsyncMock(return_value=None)
    cloud.get_cloud_keys = AsyncMock(return_value={})

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={}),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"login_mode": LOGIN_MODE_PRESET},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"
    assert result["errors"] == {"base": "token_unavailable"}
    assert cloud.get_cloud_keys.call_count == 2


async def test_auto_flow_v3_phase2_success_after_phase1_failure(
    hass: HomeAssistant,
) -> None:
    """Test the two-phase fallback: phase 1 finds no usable key, phase 2's forced preset re-login yields a working key.

    Phase 1 (the key lookup using the already-authenticated cloud) must
    return no usable token/key here, so that only phase 2 (re-login with
    the preset account, then a second key lookup) can produce the
    successful entry. The call-count assertions ensure the phase 2 path
    actually executed rather than short-circuiting on phase 1.
    """
    mock_devices = {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=mock_devices,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["step_id"] == "auth_method"

    cloud = MagicMock()
    cloud.login = AsyncMock(side_effect=[True, True])
    cloud.get_device_info = AsyncMock(return_value=None)
    cloud.get_cloud_keys = AsyncMock(
        side_effect=[
            {},
            {"method": {"token": TEST_TOKEN, "key": TEST_KEY}},
        ]
    )

    dm = MagicMock()
    dm.connect.return_value = True

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"login_mode": LOGIN_MODE_PRESET},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == TEST_DEVICE_ID
    assert result["data"][CONF_TOKEN] == TEST_TOKEN
    assert result["data"][CONF_KEY] == TEST_KEY
    assert cloud.login.call_count == 2
    assert cloud.get_cloud_keys.call_count == 2


async def test_auto_flow_recovers_after_preset_login_error(
    hass: HomeAssistant,
) -> None:
    """Test the auto flow returns to auth_method after a login/key failure.

    Previously, a failed preset-login retry inside async_step_auto left
    self._login_data and self.cloud populated with the broken credentials,
    so re-selecting the device would skip auth_method entirely and keep
    retrying with the same stale login, failing forever.
    """
    mock_devices = {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=mock_devices,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["step_id"] == "auth_method"

    cloud = MagicMock()
    cloud.login = AsyncMock(side_effect=[True, False])
    cloud.get_device_info = AsyncMock(return_value=None)
    cloud.get_cloud_keys = AsyncMock(return_value={})

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={}),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"login_mode": LOGIN_MODE_PRESET},
        )
        assert result["step_id"] == "auto"
        assert result["errors"] == {"base": "preset_login_failed"}

        # re-selecting the device must route back through auth_method
        # instead of silently retrying with the stale login state
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_DEVICE: TEST_DEVICE_ID},
        )

    assert result["step_id"] == "auth_method"


@pytest.mark.parametrize(
    "protocol",
    [
        pytest.param(ProtocolVersion.V1, id="v1"),
        pytest.param(ProtocolVersion.V2, id="v2"),
    ],
)
async def test_auto_flow_v1_v2_success_when_cloud_down(
    hass: HomeAssistant,
    protocol: ProtocolVersion,
) -> None:
    """Test v1/v2 devices are added without ever using the cloud, even if it is down."""
    mock_devices = {
        TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE, CONF_PROTOCOL: protocol},
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"

    dm = MagicMock()
    dm.connect.return_value = True

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value=mock_devices,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            side_effect=AssertionError("cloud must not be used"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "auto"

        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_DEVICE: TEST_DEVICE_ID},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == TEST_DEVICE_ID
    assert result["data"][CONF_PROTOCOL] == protocol


async def test_login_credentials_step_renders_with_cloud_servers(
    hass: HomeAssistant,
) -> None:
    """Test login_credentials step renders form regardless of cloud server list shape."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=DISCOVERY_RESULT,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"

    with patch(
        "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
        AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"login_mode": LOGIN_MODE_ACCOUNT},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login_credentials"


async def test_login_credentials_step_login_failed_sets_error(
    hass: HomeAssistant,
) -> None:
    """Test login_credentials failures stay on the step with proper error state."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=DISCOVERY_RESULT,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"login_mode": LOGIN_MODE_ACCOUNT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login_credentials"

    cloud = MagicMock()
    cloud.login = AsyncMock(return_value=False)

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={
                CONF_SERVER: DEFAULT_CLOUD,
                CONF_ACCOUNT: "user",
                CONF_PASSWORD: "pass",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login_credentials"
    assert result["errors"] == {"base": "login_failed"}

    data_schema = result["data_schema"].schema
    assert get_schema_suggested_value(data_schema, CONF_ACCOUNT) == "user"
    assert get_schema_suggested_value(data_schema, CONF_SERVER) == DEFAULT_CLOUD


async def test_login_credentials_step_recovers_after_failed_login(
    hass: HomeAssistant,
) -> None:
    """Test the user can correct a failed login and complete the flow.

    This is the config-flow-test-coverage error-recovery scenario: the flow
    hits an error (a wrong password), the user resubmits corrected data on
    the same form, and the flow proceeds all the way to CREATE_ENTRY.
    """
    discovered_device = {
        TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE},
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=discovered_device,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"login_mode": LOGIN_MODE_ACCOUNT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login_credentials"

    cloud = MagicMock()
    cloud.login = AsyncMock(side_effect=[False, True])
    cloud.get_device_info = AsyncMock(return_value=None)
    cloud.get_cloud_keys = AsyncMock(
        return_value={"method": {"token": TEST_TOKEN, "key": TEST_KEY}}
    )

    dm = MagicMock()
    dm.connect.return_value = True

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        # first attempt: wrong password
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={
                CONF_SERVER: DEFAULT_CLOUD,
                CONF_ACCOUNT: "user",
                CONF_PASSWORD: "wrong-pass",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "login_credentials"
        assert result["errors"] == {"base": "login_failed"}

        # user corrects the password and resubmits; the flow must complete
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={
                CONF_SERVER: DEFAULT_CLOUD,
                CONF_ACCOUNT: "user",
                CONF_PASSWORD: "correct-pass",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == TEST_DEVICE_ID
    assert result["data"][CONF_TOKEN] == TEST_TOKEN
    assert result["data"][CONF_KEY] == TEST_KEY


@pytest.mark.parametrize(
    ("all_devices", "expected_table_fragment"),
    [
        pytest.param({}, "Not found", id="empty"),
        pytest.param(
            {
                TEST_DEVICE_ID: {
                    CONF_TYPE: TEST_TYPE,
                    CONF_IP_ADDRESS: TEST_IP_ADDRESS,
                    "sn": "abc",
                }
            },
            "YES",
            id="single_device",
        ),
    ],
)
async def test_list_step_shows_discovery_table(
    hass: HomeAssistant,
    all_devices: dict[int, dict[str, object]],
    expected_table_fragment: str,
) -> None:
    """Test list step shows either table output or not-found message."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=all_devices,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"next_step_id": "list"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "list"
    assert expected_table_fragment in result["description_placeholders"]["table"]


async def test_list_step_submit_returns_to_user_menu(hass: HomeAssistant) -> None:
    """Test submitting list step returns user menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"next_step_id": "list"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "list"

        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"ok": True},
        )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"


async def test_manual_step_v3_missing_token_key_sets_retrieved_values(
    hass: HomeAssistant,
) -> None:
    """Test manual step writes cloud-provided token/key into user_input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "manually"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"

    device = {
        **BASE_DATA,
        CONF_TYPE: TEST_TYPE,
        CONF_PROTOCOL: ProtocolVersion.V3,
        CONF_IP_ADDRESS: TEST_IP_ADDRESS,
        CONF_SUBTYPE: TEST_SUBTYPE,
    }
    user_input: dict[str, object] = {
        **EXTENDED_DATA,
        CONF_PROTOCOL: ProtocolVersion.V3,
        CONF_TOKEN: "",
        CONF_KEY: "",
    }
    dm = MagicMock()
    # First connect call is the cloud key candidate check (must succeed to
    # select the key); second is the final entry creation attempt, which
    # must fail to exercise the device_auth_failed branch.
    dm.connect.side_effect = [True, False]

    cloud = MagicMock()
    cloud.login = AsyncMock(return_value=True)
    cloud.get_cloud_keys = AsyncMock(
        return_value={"method": {"token": TEST_TOKEN, "key": TEST_KEY}}
    )

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value={TEST_DEVICE_ID: device},
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
        ) as mock_midea_device,
    ):
        mock_midea_device.return_value = dm
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input=user_input,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"
    assert result["errors"] == {"base": "device_auth_failed"}

    assert mock_midea_device.call_args.kwargs["token"] == TEST_TOKEN
    assert mock_midea_device.call_args.kwargs["key"] == TEST_KEY


async def test_manually_flow_success(hass: HomeAssistant) -> None:
    """Test the full manual configuration flow through to entry creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "manually"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value=DISCOVERY_RESULT,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
        ) as mock_midea_device,
    ):
        mock_device = MagicMock()
        mock_device.connect.return_value = True
        mock_midea_device.return_value = mock_device

        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={
                CONF_DEVICE_ID: TEST_DEVICE_ID,
                CONF_TYPE: TEST_TYPE,
                CONF_IP_ADDRESS: TEST_IP_ADDRESS,
                CONF_PORT: TEST_PORT,
                CONF_PROTOCOL: TEST_PROTOCOL,
                CONF_MODEL: TEST_MODEL,
                CONF_SUBTYPE: TEST_SUBTYPE,
                CONF_TOKEN: TEST_TOKEN,
                CONF_KEY: TEST_KEY,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MIDEA_DEVICE_NAMES[TEST_TYPE]
    assert result["data"][CONF_DEVICE_ID] == TEST_DEVICE_ID
    assert result["data"][CONF_IP_ADDRESS] == TEST_IP_ADDRESS
    assert result["data"][CONF_TOKEN] == TEST_TOKEN
    assert result["data"][CONF_KEY] == TEST_KEY


async def test_login_credentials_step_falls_back_to_default_cloud(
    hass: HomeAssistant,
) -> None:
    """Test login_credentials step falls back to DEFAULT_CLOUD with no cloud servers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=DISCOVERY_RESULT,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"

    with patch(
        "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
        AsyncMock(return_value={}),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"login_mode": LOGIN_MODE_ACCOUNT},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login_credentials"


async def test_login_credentials_step_success_resumes_auto_flow(
    hass: HomeAssistant,
) -> None:
    """Test login_credentials step stores login data and resumes device processing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"

    discovered_device = {
        TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE},
    }
    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=discovered_device,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"login_mode": LOGIN_MODE_ACCOUNT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login_credentials"

    cloud = MagicMock()
    cloud.login = AsyncMock(return_value=True)
    cloud.get_device_info = AsyncMock(return_value=None)
    cloud.get_cloud_keys = AsyncMock(
        return_value={"method": {"token": TEST_TOKEN, "key": TEST_KEY}}
    )

    dm = MagicMock()
    dm.connect.return_value = True

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ) as mock_session,
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ) as mock_get_midea_cloud,
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={
                CONF_SERVER: DEFAULT_CLOUD,
                CONF_ACCOUNT: "user",
                CONF_PASSWORD: "pass",
            },
        )

    mock_get_midea_cloud.assert_called_once_with(
        DEFAULT_CLOUD, mock_session.return_value, "user", "pass"
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == TEST_DEVICE_ID


async def test_auth_method_account_mode_redirects_to_login_credentials(
    hass: HomeAssistant,
) -> None:
    """Test auth_method step routes to login_credentials when account mode is chosen."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=DISCOVERY_RESULT,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"login_mode": LOGIN_MODE_ACCOUNT},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login_credentials"


async def test_auth_method_preset_login_failed(hass: HomeAssistant) -> None:
    """Test auth_method step surfaces preset_login_failed when preset login fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=DISCOVERY_RESULT,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"

    cloud = MagicMock()
    cloud.login = AsyncMock(return_value=False)

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"login_mode": LOGIN_MODE_PRESET},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"
    assert result["errors"] == {"base": "preset_login_failed"}
