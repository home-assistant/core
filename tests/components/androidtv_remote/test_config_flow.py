"""Test the Android TV Remote config flow."""
from unittest.mock import AsyncMock, MagicMock

from androidtvremote2 import CannotConnect, ConnectionClosed, InvalidAuth

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.androidtv_remote.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_api: MagicMock,
) -> None:
    """Test the full user flow from start to finish without any exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "host" in result["data_schema"].schema
    assert not result["errors"]

    host = "1.2.3.4"
    name = "My Android TV"
    mac = "1A:2B:3C:4D:5E:6F"
    unique_id = "1a:2b:3c:4d:5e:6f"
    pin = "123456"

    mock_api.async_get_name_and_mac = AsyncMock(return_value=(name, mac))
    mock_api.async_generate_cert_if_missing = AsyncMock(return_value=True)
    mock_api.async_start_pairing = AsyncMock(return_value=None)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": host}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert "pin" in result["data_schema"].schema
    assert not result["errors"]

    mock_api.async_generate_cert_if_missing.assert_called()
    mock_api.async_start_pairing.assert_called()

    mock_api.async_finish_pairing = AsyncMock(return_value=None)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": pin}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == name
    assert result["data"] == {"host": host, "name": name, "mac": mac}
    assert result["context"]["source"] == "user"
    assert result["context"]["unique_id"] == unique_id

    mock_api.async_finish_pairing.assert_called_with(pin)

    await hass.async_block_till_done()
    assert len(mock_unload_entry.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_api: MagicMock,
) -> None:
    """Test async_get_name_and_mac raises CannotConnect.

    This is when the user entered an invalid IP address so we stay
    in the user step allowing the user to enter a different host.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "host" in result["data_schema"].schema
    assert not result["errors"]

    host = "1.2.3.4"

    mock_api.async_get_name_and_mac = AsyncMock(side_effect=CannotConnect())

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": host}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "host" in result["data_schema"].schema
    assert result["errors"] == {"base": "cannot_connect"}

    mock_api.async_get_name_and_mac.assert_called()
    mock_api.async_start_pairing.assert_not_called()

    await hass.async_block_till_done()
    assert len(mock_unload_entry.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_user_flow_pairing_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_api: MagicMock,
) -> None:
    """Test async_finish_pairing raises InvalidAuth.

    This is when the user entered an invalid PIN. We stay in the pair step
    allowing the user to enter a different PIN.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "host" in result["data_schema"].schema
    assert not result["errors"]

    host = "1.2.3.4"
    name = "My Android TV"
    mac = "1A:2B:3C:4D:5E:6F"
    pin = "123456"

    mock_api.async_get_name_and_mac = AsyncMock(return_value=(name, mac))
    mock_api.async_generate_cert_if_missing = AsyncMock(return_value=True)
    mock_api.async_start_pairing = AsyncMock(return_value=None)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": host}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert "pin" in result["data_schema"].schema
    assert not result["errors"]

    mock_api.async_generate_cert_if_missing.assert_called()
    mock_api.async_start_pairing.assert_called()

    mock_api.async_finish_pairing = AsyncMock(side_effect=InvalidAuth())

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": pin}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert "pin" in result["data_schema"].schema
    assert result["errors"] == {"base": "invalid_auth"}

    mock_api.async_finish_pairing.assert_called_with(pin)

    assert mock_api.async_get_name_and_mac.call_count == 1
    assert mock_api.async_start_pairing.call_count == 1
    assert mock_api.async_finish_pairing.call_count == 1

    await hass.async_block_till_done()
    assert len(mock_unload_entry.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_user_flow_pairing_connection_closed(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_api: MagicMock,
) -> None:
    """Test async_finish_pairing raises ConnectionClosed.

    This is when the user canceled pairing on the Android TV itself before calling async_finish_pairing.
    We call async_start_pairing again which succeeds and we have a chance to enter a new PIN.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "host" in result["data_schema"].schema
    assert not result["errors"]

    host = "1.2.3.4"
    name = "My Android TV"
    mac = "1A:2B:3C:4D:5E:6F"
    pin = "123456"

    mock_api.async_get_name_and_mac = AsyncMock(return_value=(name, mac))
    mock_api.async_generate_cert_if_missing = AsyncMock(return_value=True)
    mock_api.async_start_pairing = AsyncMock(return_value=None)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": host}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert "pin" in result["data_schema"].schema
    assert not result["errors"]

    mock_api.async_generate_cert_if_missing.assert_called()
    mock_api.async_start_pairing.assert_called()

    mock_api.async_finish_pairing = AsyncMock(side_effect=ConnectionClosed())

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": pin}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert "pin" in result["data_schema"].schema
    assert not result["errors"]

    mock_api.async_finish_pairing.assert_called_with(pin)

    assert mock_api.async_get_name_and_mac.call_count == 1
    assert mock_api.async_start_pairing.call_count == 2
    assert mock_api.async_finish_pairing.call_count == 1

    await hass.async_block_till_done()
    assert len(mock_unload_entry.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_user_flow_pairing_connection_closed_followed_by_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_api: MagicMock,
) -> None:
    """Test async_finish_pairing raises ConnectionClosed and then async_start_pairing raises CannotConnect.

    This is when the user unplugs the Android TV before calling async_finish_pairing.
    We call async_start_pairing again which fails with CannotConnect so we abort.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "host" in result["data_schema"].schema
    assert not result["errors"]

    host = "1.2.3.4"
    name = "My Android TV"
    mac = "1A:2B:3C:4D:5E:6F"
    pin = "123456"

    mock_api.async_get_name_and_mac = AsyncMock(return_value=(name, mac))
    mock_api.async_generate_cert_if_missing = AsyncMock(return_value=True)
    mock_api.async_start_pairing = AsyncMock(side_effect=[None, CannotConnect()])

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": host}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert "pin" in result["data_schema"].schema
    assert not result["errors"]

    mock_api.async_generate_cert_if_missing.assert_called()
    mock_api.async_start_pairing.assert_called()

    mock_api.async_finish_pairing = AsyncMock(side_effect=ConnectionClosed())

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": pin}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

    mock_api.async_finish_pairing.assert_called_with(pin)

    assert mock_api.async_get_name_and_mac.call_count == 1
    assert mock_api.async_start_pairing.call_count == 2
    assert mock_api.async_finish_pairing.call_count == 1

    await hass.async_block_till_done()
    assert len(mock_unload_entry.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_user_flow_already_configured_host_changed_reloads_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_api: MagicMock,
) -> None:
    """Test we abort the user flow if already configured and reload if host changed."""
    host = "1.2.3.4"
    name = "My Android TV"
    mac = "1A:2B:3C:4D:5E:6F"
    unique_id = "1a:2b:3c:4d:5e:6f"
    name_existing = "existing name if different is from discovery and should not change"
    host_existing = "1.2.3.45"
    assert host_existing != host

    mock_config_entry = MockConfigEntry(
        title=name,
        domain=DOMAIN,
        data={
            "host": host_existing,
            "name": name_existing,
            "mac": mac,
        },
        unique_id=unique_id,
        state=ConfigEntryState.LOADED,
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "host" in result["data_schema"].schema
    assert not result["errors"]

    mock_api.async_get_name_and_mac = AsyncMock(return_value=(name, mac))

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": host}
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"

    mock_api.async_get_name_and_mac.assert_called()
    mock_api.async_start_pairing.assert_not_called()

    await hass.async_block_till_done()
    assert len(mock_unload_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert hass.config_entries.async_entries(DOMAIN)[0].data == {
        "host": host,
        "name": name_existing,
        "mac": mac,
    }


async def test_user_flow_already_configured_host_not_changed_no_reload_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_api: MagicMock,
) -> None:
    """Test we abort the user flow if already configured and no reload if host not changed."""
    host = "1.2.3.4"
    name = "My Android TV"
    mac = "1A:2B:3C:4D:5E:6F"
    unique_id = "1a:2b:3c:4d:5e:6f"
    name_existing = "existing name if different is from discovery and should not change"
    host_existing = host

    mock_config_entry = MockConfigEntry(
        title=name,
        domain=DOMAIN,
        data={
            "host": host_existing,
            "name": name_existing,
            "mac": mac,
        },
        unique_id=unique_id,
        state=ConfigEntryState.LOADED,
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "host" in result["data_schema"].schema
    assert not result["errors"]

    mock_api.async_get_name_and_mac = AsyncMock(return_value=(name, mac))

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": host}
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"

    mock_api.async_get_name_and_mac.assert_called()
    mock_api.async_start_pairing.assert_not_called()

    await hass.async_block_till_done()
    assert len(mock_unload_entry.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0
    assert hass.config_entries.async_entries(DOMAIN)[0].data == {
        "host": host,
        "name": name_existing,
        "mac": mac,
    }


async def test_zeroconf_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_api: MagicMock,
) -> None:
    """Test the full zeroconf flow from start to finish without any exceptions."""
    host = "1.2.3.4"
    name = "My Android TV"
    mac = "1A:2B:3C:4D:5E:6F"
    unique_id = "1a:2b:3c:4d:5e:6f"
    pin = "123456"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host=host,
            addresses=[host],
            port=6466,
            hostname=host,
            type="mock_type",
            name=name + "._androidtvremote2._tcp.local.",
            properties={"bt": mac},
        ),
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert not result["data_schema"]

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "zeroconf_confirm"
    assert result["context"]["source"] == "zeroconf"
    assert result["context"]["unique_id"] == unique_id
    assert result["context"]["title_placeholders"] == {"name": name}

    mock_api.async_generate_cert_if_missing = AsyncMock(return_value=True)
    mock_api.async_start_pairing = AsyncMock(return_value=None)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert "pin" in result["data_schema"].schema
    assert not result["errors"]

    mock_api.async_generate_cert_if_missing.assert_called()
    mock_api.async_start_pairing.assert_called()

    mock_api.async_finish_pairing = AsyncMock(return_value=None)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": pin}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == name
    assert result["data"] == {
        "host": host,
        "name": name,
        "mac": mac,
    }
    assert result["context"]["source"] == "zeroconf"
    assert result["context"]["unique_id"] == unique_id

    mock_api.async_finish_pairing.assert_called_with(pin)

    await hass.async_block_till_done()
    assert len(mock_unload_entry.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_flow_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_api: MagicMock,
) -> None:
    """Test async_start_pairing raises CannotConnect in the zeroconf flow.

    This is when the Android TV became network unreachable after discovery.
    We abort and let discovery find it again later.
    """
    host = "1.2.3.4"
    name = "My Android TV"
    mac = "1A:2B:3C:4D:5E:6F"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host=host,
            addresses=[host],
            port=6466,
            hostname=host,
            type="mock_type",
            name=name + "._androidtvremote2._tcp.local.",
            properties={"bt": mac},
        ),
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert not result["data_schema"]

    mock_api.async_generate_cert_if_missing = AsyncMock(return_value=True)
    mock_api.async_start_pairing = AsyncMock(side_effect=CannotConnect())

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

    mock_api.async_generate_cert_if_missing.assert_called()
    mock_api.async_start_pairing.assert_called()

    await hass.async_block_till_done()
    assert len(mock_unload_entry.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_zeroconf_flow_pairing_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_api: MagicMock,
) -> None:
    """Test async_finish_pairing raises InvalidAuth in the zeroconf flow.

    This is when the user entered an invalid PIN. We stay in the pair step
    allowing the user to enter a different PIN.
    """
    host = "1.2.3.4"
    name = "My Android TV"
    mac = "1A:2B:3C:4D:5E:6F"
    pin = "123456"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host=host,
            addresses=[host],
            port=6466,
            hostname=host,
            type="mock_type",
            name=name + "._androidtvremote2._tcp.local.",
            properties={"bt": mac},
        ),
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert not result["data_schema"]

    mock_api.async_generate_cert_if_missing = AsyncMock(return_value=True)
    mock_api.async_start_pairing = AsyncMock(return_value=None)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert "pin" in result["data_schema"].schema
    assert not result["errors"]

    mock_api.async_generate_cert_if_missing.assert_called()
    mock_api.async_start_pairing.assert_called()

    mock_api.async_finish_pairing = AsyncMock(side_effect=InvalidAuth())

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": pin}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert "pin" in result["data_schema"].schema
    assert result["errors"] == {"base": "invalid_auth"}

    mock_api.async_finish_pairing.assert_called_with(pin)

    assert mock_api.async_get_name_and_mac.call_count == 0
    assert mock_api.async_start_pairing.call_count == 1
    assert mock_api.async_finish_pairing.call_count == 1

    await hass.async_block_till_done()
    assert len(mock_unload_entry.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_zeroconf_flow_already_configured_host_changed_reloads_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_api: MagicMock,
) -> None:
    """Test we abort the zeroconf flow if already configured and reload if host or name changed."""
    host = "1.2.3.4"
    name = "My Android TV"
    mac = "1A:2B:3C:4D:5E:6F"
    unique_id = "1a:2b:3c:4d:5e:6f"
    name_existing = "existing name should change since we prefer one from discovery"
    host_existing = "1.2.3.45"
    assert host_existing != host
    assert name_existing != name

    mock_config_entry = MockConfigEntry(
        title=name,
        domain=DOMAIN,
        data={
            "host": host_existing,
            "name": name_existing,
            "mac": mac,
        },
        unique_id=unique_id,
        state=ConfigEntryState.LOADED,
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host=host,
            addresses=[host],
            port=6466,
            hostname=host,
            type="mock_type",
            name=name + "._androidtvremote2._tcp.local.",
            properties={"bt": mac},
        ),
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    await hass.async_block_till_done()
    assert hass.config_entries.async_entries(DOMAIN)[0].data == {
        "host": host,
        "name": name,
        "mac": mac,
    }
    assert len(mock_unload_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_flow_already_configured_host_not_changed_no_reload_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_api: MagicMock,
) -> None:
    """Test we abort the zeroconf flow if already configured and no reload if host and name not changed."""
    host = "1.2.3.4"
    name = "My Android TV"
    mac = "1A:2B:3C:4D:5E:6F"
    unique_id = "1a:2b:3c:4d:5e:6f"
    name_existing = name
    host_existing = host

    mock_config_entry = MockConfigEntry(
        title=name,
        domain=DOMAIN,
        data={
            "host": host_existing,
            "name": name_existing,
            "mac": mac,
        },
        unique_id=unique_id,
        state=ConfigEntryState.LOADED,
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host=host,
            addresses=[host],
            port=6466,
            hostname=host,
            type="mock_type",
            name=name + "._androidtvremote2._tcp.local.",
            properties={"bt": mac},
        ),
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    await hass.async_block_till_done()
    assert hass.config_entries.async_entries(DOMAIN)[0].data == {
        "host": host,
        "name": name,
        "mac": mac,
    }
    assert len(mock_unload_entry.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_api: MagicMock,
) -> None:
    """Test the full reauth flow from start to finish without any exceptions."""
    host = "1.2.3.4"
    name = "My Android TV"
    mac = "1A:2B:3C:4D:5E:6F"
    unique_id = "1a:2b:3c:4d:5e:6f"
    pin = "123456"

    mock_config_entry = MockConfigEntry(
        title=name,
        domain=DOMAIN,
        data={
            "host": host,
            "name": name,
            "mac": mac,
        },
        unique_id=unique_id,
        state=ConfigEntryState.LOADED,
    )
    mock_config_entry.add_to_hass(hass)

    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "reauth_confirm"
    assert result["context"]["source"] == "reauth"
    assert result["context"]["unique_id"] == unique_id
    assert result["context"]["title_placeholders"] == {"name": name}

    mock_api.async_generate_cert_if_missing = AsyncMock(return_value=True)
    mock_api.async_start_pairing = AsyncMock(return_value=None)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert "pin" in result["data_schema"].schema
    assert not result["errors"]

    mock_api.async_get_name_and_mac.assert_not_called()
    mock_api.async_generate_cert_if_missing.assert_called()
    mock_api.async_start_pairing.assert_called()

    mock_api.async_finish_pairing = AsyncMock(return_value=None)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": pin}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    mock_api.async_finish_pairing.assert_called_with(pin)

    await hass.async_block_till_done()
    assert hass.config_entries.async_entries(DOMAIN)[0].data == {
        "host": host,
        "name": name,
        "mac": mac,
    }
    assert len(mock_unload_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_flow_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_api: MagicMock,
) -> None:
    """Test async_start_pairing raises CannotConnect in the reauth flow."""
    host = "1.2.3.4"
    name = "My Android TV"
    mac = "1A:2B:3C:4D:5E:6F"
    unique_id = "1a:2b:3c:4d:5e:6f"

    mock_config_entry = MockConfigEntry(
        title=name,
        domain=DOMAIN,
        data={
            "host": host,
            "name": name,
            "mac": mac,
        },
        unique_id=unique_id,
        state=ConfigEntryState.LOADED,
    )
    mock_config_entry.add_to_hass(hass)

    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "reauth_confirm"
    assert result["context"]["source"] == "reauth"
    assert result["context"]["unique_id"] == unique_id
    assert result["context"]["title_placeholders"] == {"name": name}

    mock_api.async_generate_cert_if_missing = AsyncMock(return_value=True)
    mock_api.async_start_pairing = AsyncMock(side_effect=CannotConnect())

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_api.async_get_name_and_mac.assert_not_called()
    mock_api.async_generate_cert_if_missing.assert_called()
    mock_api.async_start_pairing.assert_called()

    await hass.async_block_till_done()
    assert len(mock_unload_entry.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0
