"""Test the Nobø Ecohub config flow."""

from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.nobo_hub.const import (
    CONF_AUTO_DISCOVERED,
    CONF_OVERRIDE_TYPE,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import SERIAL

from tests.common import MockConfigEntry


async def test_configure_with_discover(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test configure with discover."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "device": "1.1.1.1",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {}
    assert result2["step_id"] == "selected"

    with (
        patch("pynobo.nobo.async_connect_hub", return_value=True) as mock_connect,
        patch(
            "pynobo.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "serial_suffix": "012",
            },
        )
        await hass.async_block_till_done()

        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert result3["title"] == "My Nobø Ecohub"
        assert result3["data"] == {
            "ip_address": "1.1.1.1",
            "serial": "123456789012",
            "auto_discovered": True,
        }
        mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")
        mock_setup_entry.assert_awaited_once()


async def test_configure_manual(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test manual configuration when no hubs are discovered."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        assert result["step_id"] == "manual"

    with (
        patch("pynobo.nobo.async_connect_hub", return_value=True) as mock_connect,
        patch(
            "pynobo.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "serial": "123456789012",
                "ip_address": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "My Nobø Ecohub"
        assert result2["data"] == {
            "serial": "123456789012",
            "ip_address": "1.1.1.1",
            "auto_discovered": False,
        }
        mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")
        mock_setup_entry.assert_awaited_once()


async def test_configure_user_selected_manual(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test configuration when user selects manual."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "device": "manual",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {}
    assert result2["step_id"] == "manual"

    with (
        patch("pynobo.nobo.async_connect_hub", return_value=True) as mock_connect,
        patch(
            "pynobo.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "serial": "123456789012",
                "ip_address": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "My Nobø Ecohub"
        assert result2["data"] == {
            "serial": "123456789012",
            "ip_address": "1.1.1.1",
            "auto_discovered": False,
        }
        mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")
        mock_setup_entry.assert_awaited_once()


async def test_configure_invalid_serial_suffix(hass: HomeAssistant) -> None:
    """Test we handle invalid serial suffix error."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "device": "1.1.1.1",
        },
    )
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {"serial_suffix": "ABC"},
    )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_serial"}


async def test_configure_invalid_serial_undiscovered(hass: HomeAssistant) -> None:
    """Test we handle invalid serial error."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "1.1.1.1", "serial": "123456789"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_serial"}


async def test_configure_invalid_ip_address(hass: HomeAssistant) -> None:
    """Test we handle invalid ip address error."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"serial": "123456789012", "ip_address": "ABCD"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_ip"}


async def test_configure_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "device": "1.1.1.1",
        },
    )

    with patch(
        "pynobo.nobo.async_connect_hub",
        return_value=False,
    ) as mock_connect:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"serial_suffix": "012"},
        )
        assert result3["type"] is FlowResultType.FORM
        assert result3["errors"] == {"base": "cannot_connect"}
        mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")


async def test_reconfigure_flow_connected_toggle_off(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
) -> None:
    """Test toggling auto-discovery off on a connected hub does not reconnect."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_AUTO_DISCOVERED: True,
        },
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["description_placeholders"] == {CONF_SERIAL: SERIAL}

    # The frontend does not submit read-only fields — simulate that by only
    # sending CONF_AUTO_DISCOVERED. The schema's default fills in the IP.
    with patch("pynobo.nobo.async_connect_hub") as mock_connect:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_AUTO_DISCOVERED: False},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert config_entry.data == {
        CONF_SERIAL: SERIAL,
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_AUTO_DISCOVERED: False,
    }
    mock_connect.assert_not_awaited()
    # Connected toggle change must not reconnect.
    mock_unload_entry.assert_not_awaited()


async def test_reconfigure_flow_connected_ignores_ip_change(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
) -> None:
    """Test the IP field is read-only while connected; submitted IP is ignored."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_AUTO_DISCOVERED: False,
        },
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Even if a malicious client bypasses the read-only attribute and submits
    # an IP, it must be ignored while connected.
    result = await config_entry.start_reconfigure_flow(hass)
    with patch("pynobo.nobo.async_connect_hub") as mock_connect:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "9.9.9.9", CONF_AUTO_DISCOVERED: True},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert config_entry.data[CONF_IP_ADDRESS] == "1.1.1.1"
    assert config_entry.data[CONF_AUTO_DISCOVERED] is True
    mock_connect.assert_not_awaited()


async def test_reconfigure_flow_disconnected_changes_ip(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test IP can be changed (and tested) while the hub is not connected."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_AUTO_DISCOVERED: True,
        },
    )
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    with (
        patch("pynobo.nobo.async_connect_hub", return_value=True) as mock_connect,
        patch(
            "pynobo.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "2.2.2.2", CONF_AUTO_DISCOVERED: False},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert config_entry.data == {
        CONF_SERIAL: SERIAL,
        CONF_IP_ADDRESS: "2.2.2.2",
        CONF_AUTO_DISCOVERED: False,
    }
    mock_connect.assert_awaited_once_with("2.2.2.2", SERIAL)


async def test_reconfigure_flow_disconnected_enable_auto_skips_test(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test enabling auto-discovery on a disconnected entry skips the IP probe.

    When the user enables auto-discovery, the integration will rediscover the
    IP on the next setup attempt, so the (possibly stale) IP shouldn't block
    the reconfigure.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_AUTO_DISCOVERED: False,
        },
    )
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    with patch("pynobo.nobo.async_connect_hub") as mock_connect:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "1.1.1.1", CONF_AUTO_DISCOVERED: True},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_AUTO_DISCOVERED] is True
    mock_connect.assert_not_awaited()


@pytest.mark.parametrize(
    "connect_outcome",
    [{"return_value": False}, {"side_effect": ConnectionRefusedError(61, "")}],
    ids=["returns_false", "raises_oserror"],
)
async def test_reconfigure_flow_disconnected_cannot_connect(
    hass: HomeAssistant, connect_outcome: dict[str, object]
) -> None:
    """Test reconfigure flow surfaces a connection failure as a form error.

    pynobo's async_connect_hub may either return False (on protocol-level
    failures) or raise OSError (e.g., ConnectionRefusedError when the port
    is closed at the new IP). Both paths must produce 'cannot_connect'.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_AUTO_DISCOVERED: False,
        },
    )
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    with patch("pynobo.nobo.async_connect_hub", **connect_outcome):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "2.2.2.2", CONF_AUTO_DISCOVERED: False},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reconfigure"
    assert result2["errors"] == {"base": "cannot_connect_ip"}
    assert config_entry.data[CONF_IP_ADDRESS] == "1.1.1.1"


@pytest.mark.parametrize("submitted_auto_discovered", [False, True])
async def test_reconfigure_flow_disconnected_invalid_ip(
    hass: HomeAssistant, submitted_auto_discovered: bool
) -> None:
    """Test reconfigure flow rejects a malformed IP regardless of toggle state.

    Even when auto-discovery is enabled, the typed IP must parse — otherwise
    we'd persist garbage that the next setup attempt has to repeatedly fail
    on before falling through to rediscovery.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_AUTO_DISCOVERED: False,
        },
    )
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "not-an-ip",
            CONF_AUTO_DISCOVERED: submitted_auto_discovered,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_ip"}
    assert config_entry.data[CONF_IP_ADDRESS] == "1.1.1.1"
    assert config_entry.data[CONF_AUTO_DISCOVERED] is False


async def test_options_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
) -> None:
    """Test the options flow."""
    config_entry = MockConfigEntry(
        domain="nobo_hub",
        unique_id="123456789012",
        data={"serial": "123456789012", "ip_address": "1.1.1.1", "auto_discover": True},
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_setup_entry.reset_mock()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_OVERRIDE_TYPE: "constant",
        },
    )
    await hass.async_block_till_done()

    assert mock_unload_entry.await_count == 1
    assert mock_setup_entry.await_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_OVERRIDE_TYPE: "constant"}
    mock_unload_entry.reset_mock()
    mock_setup_entry.reset_mock()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_OVERRIDE_TYPE: "now",
        },
    )
    await hass.async_block_till_done()

    assert mock_unload_entry.await_count == 1
    assert mock_setup_entry.await_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_OVERRIDE_TYPE: "now"}
