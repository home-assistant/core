"""Test the Network UPS Tools (NUT) config flow."""

from ipaddress import ip_address
from unittest.mock import patch

from aionut import NUTError, NUTLoginError

from homeassistant import config_entries
from homeassistant.components.nut.config_flow import PASSWORD_NOT_CHANGED
from homeassistant.components.nut.const import DOMAIN
from homeassistant.const import (
    CONF_ALIAS,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .util import _get_mock_nutclient, async_init_integration

from tests.common import MockConfigEntry

VALID_CONFIG = {
    CONF_HOST: "localhost",
    CONF_PORT: 123,
    CONF_NAME: "name",
    CONF_RESOURCES: ["battery.charge"],
}


async def test_form_zeroconf(hass: HomeAssistant) -> None:
    """Test we can setup from zeroconf."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.5"),
            ip_addresses=[ip_address("192.168.1.5")],
            hostname="mock_hostname",
            name="mock_name",
            port=1234,
            properties={},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_pynut = _get_mock_nutclient(
        list_vars={"battery.voltage": "voltage", "ups.status": "OL"}, list_ups=["ups1"]
    )

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient",
            return_value=mock_pynut,
        ),
        patch(
            "homeassistant.components.nut.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "192.168.1.5:1234"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.5",
        CONF_PASSWORD: "test-password",
        CONF_PORT: 1234,
        CONF_USERNAME: "test-username",
    }
    assert result2["result"].unique_id is None
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_one_alias(hass: HomeAssistant) -> None:
    """Test we can configure a device with one alias."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_pynut = _get_mock_nutclient(
        list_vars={"battery.voltage": "voltage", "ups.status": "OL"}, list_ups=["ups1"]
    )

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient",
            return_value=mock_pynut,
        ),
        patch(
            "homeassistant.components.nut.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_PORT: 2222,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.1.1.1:2222"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test-password",
        CONF_PORT: 2222,
        CONF_USERNAME: "test-username",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_multiple_aliases(hass: HomeAssistant) -> None:
    """Test we can configure device with multiple aliases."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "2.2.2.2", CONF_PORT: 123, CONF_RESOURCES: ["battery.charge"]},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_pynut = _get_mock_nutclient(
        list_vars={"battery.voltage": "voltage"},
        list_ups={"ups1": "UPS 1", "ups2": "UPS2"},
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_PORT: 2222,
            },
        )

    assert result2["step_id"] == "ups"
    assert result2["type"] is FlowResultType.FORM

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient",
            return_value=mock_pynut,
        ),
        patch(
            "homeassistant.components.nut.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_ALIAS: "ups2"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "ups2@1.1.1.1:2222"
    assert result3["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test-password",
        CONF_ALIAS: "ups2",
        CONF_PORT: 2222,
        CONF_USERNAME: "test-username",
    }
    assert len(mock_setup_entry.mock_calls) == 2


async def test_form_user_one_alias_with_ignored_entry(hass: HomeAssistant) -> None:
    """Test we can setup a new one when there is an ignored one."""
    ignored_entry = MockConfigEntry(
        domain=DOMAIN, data={}, source=config_entries.SOURCE_IGNORE
    )
    ignored_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_pynut = _get_mock_nutclient(
        list_vars={"battery.voltage": "voltage", "ups.status": "OL"}, list_ups=["ups1"]
    )

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient",
            return_value=mock_pynut,
        ),
        patch(
            "homeassistant.components.nut.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_PORT: 2222,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.1.1.1:2222"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test-password",
        CONF_PORT: 2222,
        CONF_USERNAME: "test-username",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_no_aliases_found(hass: HomeAssistant) -> None:
    """Test we abort when the NUT server has no aliases."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_pynut = _get_mock_nutclient()

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_PORT: 2222,
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "no_ups_found"


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient.list_ups",
            side_effect=NUTError("no route to host"),
        ),
        patch(
            "homeassistant.components.nut.AIONUTClient.list_vars",
            side_effect=NUTError("no route to host"),
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_PORT: 2222,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    assert result2["description_placeholders"] == {"error": "no route to host"}

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient.list_ups",
            return_value={"ups1"},
        ),
        patch(
            "homeassistant.components.nut.AIONUTClient.list_vars",
            side_effect=Exception,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_PORT: 2222,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    mock_pynut = _get_mock_nutclient(
        list_vars={"battery.voltage": "voltage", "ups.status": "OL"}, list_ups=["ups1"]
    )
    with (
        patch(
            "homeassistant.components.nut.AIONUTClient",
            return_value=mock_pynut,
        ),
        patch(
            "homeassistant.components.nut.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_PORT: 2222,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.1.1.1:2222"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test-password",
        CONF_PORT: 2222,
        CONF_USERNAME: "test-username",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_auth_failures(hass: HomeAssistant) -> None:
    """Test authentication failures."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient.list_ups",
            side_effect=NUTLoginError,
        ),
        patch(
            "homeassistant.components.nut.AIONUTClient.list_vars",
            side_effect=NUTLoginError,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_PORT: 2222,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"password": "invalid_auth"}

    mock_pynut = _get_mock_nutclient(
        list_vars={"battery.voltage": "voltage", "ups.status": "OL"}, list_ups=["ups1"]
    )
    with (
        patch(
            "homeassistant.components.nut.AIONUTClient",
            return_value=mock_pynut,
        ),
        patch(
            "homeassistant.components.nut.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_PORT: 2222,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.1.1.1:2222"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test-password",
        CONF_PORT: 2222,
        CONF_USERNAME: "test-username",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauth flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 123,
            CONF_RESOURCES: ["battery.voltage"],
        },
    )
    config_entry.add_to_hass(hass)
    config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    flow = flows[0]

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient.list_ups",
            side_effect=NUTLoginError,
        ),
        patch(
            "homeassistant.components.nut.AIONUTClient.list_vars",
            side_effect=NUTLoginError,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"password": "invalid_auth"}

    mock_pynut = _get_mock_nutclient(
        list_vars={"battery.voltage": "voltage", "ups.status": "OL"}, list_ups=["ups1"]
    )
    with (
        patch(
            "homeassistant.components.nut.AIONUTClient",
            return_value=mock_pynut,
        ),
        patch(
            "homeassistant.components.nut.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if component is already setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 123,
            CONF_RESOURCES: ["battery.voltage"],
        },
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_pynut = _get_mock_nutclient(
        list_vars={"battery.voltage": "voltage"},
        list_ups={"ups1": "UPS 1"},
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 123,
            },
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "already_configured"


async def test_abort_duplicate_unique_ids(hass: HomeAssistant) -> None:
    """Test we abort if unique_id is already setup."""

    list_vars = {
        "device.mfr": "Some manufacturer",
        "device.model": "Some model",
        "device.serial": "0000-1",
    }
    await async_init_integration(
        hass,
        list_ups={"ups1": "UPS 1"},
        list_vars=list_vars,
    )

    mock_pynut = _get_mock_nutclient(list_ups={"ups2": "UPS 2"}, list_vars=list_vars)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 2222,
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "already_configured"


async def test_abort_multiple_aliases_duplicate_unique_ids(hass: HomeAssistant) -> None:
    """Test we abort on multiple aliases if unique_id is already setup."""

    list_vars = {
        "device.mfr": "Some manufacturer",
        "device.model": "Some model",
        "device.serial": "0000-1",
    }

    mock_pynut = _get_mock_nutclient(
        list_ups={"ups2": "UPS 2", "ups3": "UPS 3"}, list_vars=list_vars
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 2222,
            },
        )
        await hass.async_block_till_done()

        assert result2["step_id"] == "ups"
        assert result2["type"] is FlowResultType.FORM

    await async_init_integration(
        hass,
        list_ups={"ups1": "UPS 1"},
        list_vars=list_vars,
    )

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient",
            return_value=mock_pynut,
        ),
        patch(
            "homeassistant.components.nut.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ALIAS: "ups2"},
        )
        await hass.async_block_till_done()

        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "already_configured"


async def test_abort_if_already_setup_alias(hass: HomeAssistant) -> None:
    """Test we abort if component is already setup with same alias."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 123,
            CONF_RESOURCES: ["battery.voltage"],
            CONF_ALIAS: "ups1",
        },
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_pynut = _get_mock_nutclient(
        list_vars={"battery.voltage": "voltage"},
        list_ups={"ups1": "UPS 1", "ups2": "UPS 2"},
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 123,
            },
        )

    assert result2["step_id"] == "ups"
    assert result2["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_ALIAS: "ups1"},
        )

        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "already_configured"


async def test_reconfigure_one_alias_successful(hass: HomeAssistant) -> None:
    """Test reconfigure one alias successful."""
    entry = await async_init_integration(
        hass,
        host="1.1.1.1",
        port=123,
        username="test-username",
        password="test-password",
        list_ups={"ups1": "UPS 1"},
        list_vars={"battery.voltage": "voltage"},
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_pynut = _get_mock_nutclient(
        list_vars={"battery.voltage": "voltage"},
        list_ups={"ups1": "UPS 1"},
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "2.2.2.2",
                CONF_PORT: 456,
                CONF_USERNAME: "test-new-username",
                CONF_PASSWORD: "test-new-password",
            },
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "reconfigure_successful"

        assert entry.data[CONF_HOST] == "2.2.2.2"
        assert entry.data[CONF_PORT] == 456
        assert entry.data[CONF_USERNAME] == "test-new-username"
        assert entry.data[CONF_PASSWORD] == "test-new-password"


async def test_reconfigure_one_alias_nochange(hass: HomeAssistant) -> None:
    """Test reconfigure one alias when there is no change."""
    entry = await async_init_integration(
        hass,
        host="1.1.1.1",
        port=123,
        username="test-username",
        password="test-password",
        list_ups={"ups1": "UPS 1"},
        list_vars={"battery.voltage": "voltage"},
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_pynut = _get_mock_nutclient(
        list_ups={"ups1": "UPS 1"},
        list_vars={"battery.voltage": "voltage"},
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: entry.data[CONF_HOST],
                CONF_PORT: int(entry.data[CONF_PORT]),
                CONF_USERNAME: entry.data[CONF_USERNAME],
                CONF_PASSWORD: entry.data[CONF_PASSWORD],
            },
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "reconfigure_successful"

        assert entry.data[CONF_HOST] == "1.1.1.1"
        assert entry.data[CONF_PORT] == 123
        assert entry.data[CONF_USERNAME] == "test-username"
        assert entry.data[CONF_PASSWORD] == "test-password"


async def test_reconfigure_one_alias_password_nochange(hass: HomeAssistant) -> None:
    """Test reconfigure one alias when there is no password change."""
    entry = await async_init_integration(
        hass,
        host="1.1.1.1",
        port=123,
        username="test-username",
        password="test-password",
        list_ups={"ups1": "UPS 1"},
        list_vars={"battery.voltage": "voltage"},
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_pynut = _get_mock_nutclient(
        list_vars={"battery.voltage": "voltage"},
        list_ups={"ups1": "UPS 1"},
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "2.2.2.2",
                CONF_PORT: 456,
                CONF_USERNAME: "test-new-username",
                CONF_PASSWORD: PASSWORD_NOT_CHANGED,
            },
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "reconfigure_successful"

        assert entry.data[CONF_HOST] == "2.2.2.2"
        assert entry.data[CONF_PORT] == 456
        assert entry.data[CONF_USERNAME] == "test-new-username"
        assert entry.data[CONF_PASSWORD] == "test-password"


async def test_reconfigure_one_alias_already_configured(hass: HomeAssistant) -> None:
    """Test reconfigure when config changed to an existing host/port/alias."""
    entry = await async_init_integration(
        hass,
        host="1.1.1.1",
        port=123,
        username="test-username",
        password="test-password",
        list_ups={"ups1": "UPS 1"},
        list_vars={"battery.voltage": "voltage"},
    )

    entry2 = await async_init_integration(
        hass,
        host="2.2.2.2",
        port=456,
        username="test-username",
        password="test-password",
        list_ups={"ups1": "UPS 1"},
        list_vars={"battery.voltage": "voltage"},
    )

    result = await entry2.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_pynut = _get_mock_nutclient(
        list_ups={"ups1": "UPS 1"},
        list_vars={"battery.voltage": "voltage"},
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: entry.data[CONF_HOST],
                CONF_PORT: int(entry.data[CONF_PORT]),
                CONF_USERNAME: entry.data[CONF_USERNAME],
                CONF_PASSWORD: entry.data[CONF_PASSWORD],
            },
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "already_configured"

        assert entry.data[CONF_HOST] == "1.1.1.1"
        assert entry.data[CONF_PORT] == 123
        assert entry.data[CONF_USERNAME] == "test-username"
        assert entry.data[CONF_PASSWORD] == "test-password"

        assert entry2.data[CONF_HOST] == "2.2.2.2"
        assert entry2.data[CONF_PORT] == 456
        assert entry2.data[CONF_USERNAME] == "test-username"
        assert entry2.data[CONF_PASSWORD] == "test-password"


async def test_reconfigure_one_alias_unique_id_change(hass: HomeAssistant) -> None:
    """Test reconfigure when the unique ID is changed."""
    entry = await async_init_integration(
        hass,
        host="1.1.1.1",
        port=123,
        username="test-username",
        password="test-password",
        list_ups={"ups1": "UPS 1"},
        list_vars={
            "device.mfr": "Some manufacturer",
            "device.model": "Some model",
            "device.serial": "0000-1",
        },
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_pynut = _get_mock_nutclient(
        list_ups={"ups1": "UPS 1"},
        list_vars={
            "device.mfr": "Another manufacturer",
            "device.model": "Another model",
            "device.serial": "0000-2",
        },
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: entry.data[CONF_HOST],
                CONF_PORT: entry.data[CONF_PORT],
                CONF_USERNAME: entry.data[CONF_USERNAME],
                CONF_PASSWORD: entry.data[CONF_PASSWORD],
            },
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "unique_id_mismatch"


async def test_reconfigure_one_alias_duplicate_unique_ids(hass: HomeAssistant) -> None:
    """Test reconfigure that results in a duplicate unique ID."""

    list_vars = {
        "device.mfr": "Some manufacturer",
        "device.model": "Some model",
        "device.serial": "0000-1",
    }

    await async_init_integration(
        hass,
        host="1.1.1.1",
        port=123,
        username="test-username",
        password="test-password",
        list_ups={"ups1": "UPS 1"},
        list_vars=list_vars,
    )

    entry2 = await async_init_integration(
        hass,
        host="2.2.2.2",
        port=456,
        username="test-username",
        password="test-password",
        list_ups={"ups2": "UPS 2"},
        list_vars={
            "device.mfr": "Another manufacturer",
            "device.model": "Another model",
            "device.serial": "0000-2",
        },
    )

    result = await entry2.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_pynut = _get_mock_nutclient(
        list_ups={"ups2": "UPS 2"},
        list_vars=list_vars,
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "3.3.3.3",
                CONF_PORT: 789,
                CONF_USERNAME: "test-new-username",
                CONF_PASSWORD: "test-new-password",
            },
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "unique_id_mismatch"


async def test_reconfigure_multiple_aliases_successful(hass: HomeAssistant) -> None:
    """Test reconfigure with multiple aliases is successful."""
    entry = await async_init_integration(
        hass,
        host="1.1.1.1",
        port=123,
        username="test-username",
        password="test-password",
        list_ups={"ups1": "UPS 1"},
        list_vars={"battery.voltage": "voltage"},
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_pynut = _get_mock_nutclient(
        list_ups={
            "ups1": "UPS 1",
            "ups2": "UPS 2",
        },
        list_vars={"battery.voltage": "voltage"},
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "2.2.2.2",
                CONF_PORT: 456,
                CONF_USERNAME: "test-new-username",
                CONF_PASSWORD: "test-new-password",
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "reconfigure_ups"

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient",
            return_value=mock_pynut,
        ),
        patch(
            "homeassistant.components.nut.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_ALIAS: "ups2"},
        )
        await hass.async_block_till_done()

        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "reconfigure_successful"

        assert entry.data[CONF_HOST] == "2.2.2.2"
        assert entry.data[CONF_PORT] == 456
        assert entry.data[CONF_USERNAME] == "test-new-username"
        assert entry.data[CONF_PASSWORD] == "test-new-password"
        assert entry.data[CONF_ALIAS] == "ups2"


async def test_reconfigure_multiple_aliases_nochange(hass: HomeAssistant) -> None:
    """Test reconfigure with multiple aliases and no change."""
    entry = await async_init_integration(
        hass,
        host="1.1.1.1",
        port=123,
        username="test-username",
        password="test-password",
        list_ups={"ups1": "UPS 1"},
        list_vars={"battery.voltage": "voltage"},
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_pynut = _get_mock_nutclient(
        list_ups={
            "ups1": "UPS 1",
            "ups2": "UPS 2",
        },
        list_vars={"battery.voltage": "voltage"},
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: entry.data[CONF_HOST],
                CONF_PORT: entry.data[CONF_PORT],
                CONF_USERNAME: entry.data[CONF_USERNAME],
                CONF_PASSWORD: entry.data[CONF_PASSWORD],
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "reconfigure_ups"

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient",
            return_value=mock_pynut,
        ),
        patch(
            "homeassistant.components.nut.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_ALIAS: "ups1"},
        )
        await hass.async_block_till_done()

        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "reconfigure_successful"

        assert entry.data[CONF_HOST] == "1.1.1.1"
        assert entry.data[CONF_PORT] == 123
        assert entry.data[CONF_USERNAME] == "test-username"
        assert entry.data[CONF_PASSWORD] == "test-password"
        assert entry.data[CONF_ALIAS] == "ups1"


async def test_reconfigure_multiple_aliases_password_nochange(
    hass: HomeAssistant,
) -> None:
    """Test reconfigure with multiple aliases when no password change."""
    entry = await async_init_integration(
        hass,
        host="1.1.1.1",
        port=123,
        username="test-username",
        password="test-password",
        list_ups={"ups1": "UPS 1"},
        list_vars={"battery.voltage": "voltage"},
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_pynut = _get_mock_nutclient(
        list_ups={
            "ups1": "UPS 1",
            "ups2": "UPS 2",
        },
        list_vars={"battery.voltage": "voltage"},
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "2.2.2.2",
                CONF_PORT: 456,
                CONF_USERNAME: "test-new-username",
                CONF_PASSWORD: PASSWORD_NOT_CHANGED,
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "reconfigure_ups"

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient",
            return_value=mock_pynut,
        ),
        patch(
            "homeassistant.components.nut.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_ALIAS: "ups2"},
        )
        await hass.async_block_till_done()

        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "reconfigure_successful"

        assert entry.data[CONF_HOST] == "2.2.2.2"
        assert entry.data[CONF_PORT] == 456
        assert entry.data[CONF_USERNAME] == "test-new-username"
        assert entry.data[CONF_PASSWORD] == "test-password"
        assert entry.data[CONF_ALIAS] == "ups2"


async def test_reconfigure_multiple_aliases_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test reconfigure multi aliases changed to existing host/port/alias."""
    entry = await async_init_integration(
        hass,
        host="1.1.1.1",
        port=123,
        alias="ups1",
        username="test-username",
        password="test-password",
        list_ups={"ups1": "UPS 1", "ups2": "UPS 2"},
        list_vars={"battery.voltage": "voltage"},
    )

    entry2 = await async_init_integration(
        hass,
        host="2.2.2.2",
        port=456,
        alias="ups2",
        username="test-username",
        password="test-password",
        list_ups={"ups1": "UPS 1"},
        list_vars={"battery.voltage": "voltage"},
    )

    assert entry2.data[CONF_HOST] == "2.2.2.2"
    assert entry2.data[CONF_PORT] == 456
    assert entry2.data[CONF_USERNAME] == "test-username"
    assert entry2.data[CONF_PASSWORD] == "test-password"

    result = await entry2.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_pynut = _get_mock_nutclient(
        list_ups={
            "ups1": "UPS 1",
            "ups2": "UPS 2",
        },
        list_vars={"battery.voltage": "voltage"},
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: entry.data[CONF_HOST],
                CONF_PORT: entry.data[CONF_PORT],
                CONF_USERNAME: entry.data[CONF_USERNAME],
                CONF_PASSWORD: entry.data[CONF_PASSWORD],
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "reconfigure_ups"

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient",
            return_value=mock_pynut,
        ),
        patch(
            "homeassistant.components.nut.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_ALIAS: entry.data[CONF_ALIAS]},
        )
        await hass.async_block_till_done()

        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "already_configured"

        assert entry.data[CONF_HOST] == "1.1.1.1"
        assert entry.data[CONF_PORT] == 123
        assert entry.data[CONF_USERNAME] == "test-username"
        assert entry.data[CONF_PASSWORD] == "test-password"
        assert entry.data[CONF_ALIAS] == "ups1"

        assert entry2.data[CONF_HOST] == "2.2.2.2"
        assert entry2.data[CONF_PORT] == 456
        assert entry2.data[CONF_USERNAME] == "test-username"
        assert entry2.data[CONF_PASSWORD] == "test-password"
        assert entry2.data[CONF_ALIAS] == "ups2"


async def test_reconfigure_multiple_aliases_unique_id_change(
    hass: HomeAssistant,
) -> None:
    """Test reconfigure with multiple aliases and the unique ID is changed."""
    entry = await async_init_integration(
        hass,
        host="1.1.1.1",
        port=123,
        alias="ups1",
        username="test-username",
        password="test-password",
        list_ups={"ups1": "UPS 1", "ups2": "UPS 2"},
        list_vars={"battery.voltage": "voltage"},
    )

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_pynut = _get_mock_nutclient(
        list_ups={
            "ups1": "UPS 1",
            "ups2": "UPS 2",
        },
        list_vars={
            "device.mfr": "Another manufacturer",
            "device.model": "Another model",
            "device.serial": "0000-2",
        },
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: entry.data[CONF_HOST],
                CONF_PORT: entry.data[CONF_PORT],
                CONF_USERNAME: entry.data[CONF_USERNAME],
                CONF_PASSWORD: entry.data[CONF_PASSWORD],
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "reconfigure_ups"

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient",
            return_value=mock_pynut,
        ),
        patch(
            "homeassistant.components.nut.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_ALIAS: entry.data[CONF_ALIAS]},
        )
        await hass.async_block_till_done()

        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "unique_id_mismatch"


async def test_reconfigure_multiple_aliases_duplicate_unique_ids(
    hass: HomeAssistant,
) -> None:
    """Test reconfigure multi aliases that results in duplicate unique ID."""

    list_vars = {
        "device.mfr": "Some manufacturer",
        "device.model": "Some model",
        "device.serial": "0000-1",
    }

    entry = await async_init_integration(
        hass,
        host="1.1.1.1",
        port=123,
        alias="ups1",
        username="test-username",
        password="test-password",
        list_ups={"ups1": "UPS 1", "ups2": "UPS 2"},
        list_vars=list_vars,
    )

    entry2 = await async_init_integration(
        hass,
        host="2.2.2.2",
        port=456,
        alias="ups2",
        username="test-username",
        password="test-password",
        list_ups={"ups1": "UPS 1"},
        list_vars={
            "device.mfr": "Another manufacturer",
            "device.model": "Another model",
            "device.serial": "0000-2",
        },
    )

    result = await entry2.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_pynut = _get_mock_nutclient(
        list_ups={
            "ups1": "UPS 1",
            "ups2": "UPS 2",
        },
        list_vars=list_vars,
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "3.3.3.3",
                CONF_PORT: 789,
                CONF_USERNAME: "test-new-username",
                CONF_PASSWORD: "test-new-password",
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "reconfigure_ups"

    with (
        patch(
            "homeassistant.components.nut.AIONUTClient",
            return_value=mock_pynut,
        ),
        patch(
            "homeassistant.components.nut.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_ALIAS: entry.data[CONF_ALIAS]},
        )
        await hass.async_block_till_done()

        assert result3["type"] is FlowResultType.ABORT
        assert result3["reason"] == "unique_id_mismatch"
