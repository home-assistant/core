"""Test the lg_soundbar config flow."""
from unittest.mock import DEFAULT, MagicMock, Mock, call, patch

from homeassistant import config_entries
from homeassistant.components.lg_soundbar.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.temescal",
        return_value=MagicMock(),
    ), patch(
        "homeassistant.components.lg_soundbar.config_flow.test_connect",
        return_value={"uuid": "uuid", "name": "name"},
    ), patch(
        "homeassistant.components.lg_soundbar.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "name"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_PORT,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_uuid_missing_from_mac_info(hass):
    """Test we get the form, but uuid is missing from the initial get_mac_info function call."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.temescal", return_value=Mock()
    ) as mock_temescal, patch(
        "homeassistant.components.lg_soundbar.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        tmock = mock_temescal.temescal
        tmock.return_value = Mock()
        instance = tmock.return_value

        def temescal_side_effect(addr, port, callback):
            product_info = {"msg": "PRODUCT_INFO", "data": {"s_uuid": "uuid"}}
            instance.get_product_info.side_effect = lambda: callback(product_info)
            info = {"msg": "SPK_LIST_VIEW_INFO", "data": {"s_user_name": "name"}}
            instance.get_info.side_effect = lambda: callback(info)
            return DEFAULT

        tmock.side_effect = temescal_side_effect

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "name"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_PORT,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_uuid_present_in_both_functions_uuid_q_empty(hass):
    """Get the form, uuid present in both get_mac_info and get_product_info calls.

    Value from get_mac_info is not added to uuid_q before get_product_info is run.
    """

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_uuid_q = MagicMock()
    mock_name_q = MagicMock()

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.temescal", return_value=Mock()
    ) as mock_temescal, patch(
        "homeassistant.components.lg_soundbar.config_flow.Queue",
        return_value=MagicMock(),
    ) as mock_q, patch(
        "homeassistant.components.lg_soundbar.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        mock_q.side_effect = [mock_uuid_q, mock_name_q]
        mock_uuid_q.empty.return_value = True
        mock_uuid_q.get.return_value = "uuid"
        mock_name_q.get.return_value = "name"
        tmock = mock_temescal.temescal
        tmock.return_value = Mock()
        instance = tmock.return_value

        def temescal_side_effect(addr, port, callback):
            mac_info = {"msg": "MAC_INFO_DEV", "data": {"s_uuid": "uuid"}}
            instance.get_mac_info.side_effect = lambda: callback(mac_info)
            product_info = {"msg": "PRODUCT_INFO", "data": {"s_uuid": "uuid"}}
            instance.get_product_info.side_effect = lambda: callback(product_info)
            info = {"msg": "SPK_LIST_VIEW_INFO", "data": {"s_user_name": "name"}}
            instance.get_info.side_effect = lambda: callback(info)
            return DEFAULT

        tmock.side_effect = temescal_side_effect

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "name"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_PORT,
    }
    assert len(mock_setup_entry.mock_calls) == 1
    mock_uuid_q.empty.assert_called_once()
    mock_uuid_q.put_nowait.has_calls([call("uuid"), call("uuid")])
    mock_uuid_q.get.assert_called_once()


async def test_form_uuid_present_in_both_functions_uuid_q_not_empty(hass):
    """Get the form, uuid present in both get_mac_info and get_product_info calls.

    Value from get_mac_info is added to uuid_q before get_product_info is run.
    """

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_uuid_q = MagicMock()
    mock_name_q = MagicMock()

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.temescal", return_value=Mock()
    ) as mock_temescal, patch(
        "homeassistant.components.lg_soundbar.config_flow.Queue",
        return_value=MagicMock(),
    ) as mock_q, patch(
        "homeassistant.components.lg_soundbar.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        mock_q.side_effect = [mock_uuid_q, mock_name_q]
        mock_uuid_q.empty.return_value = False
        mock_uuid_q.get.return_value = "uuid"
        mock_name_q.get.return_value = "name"
        tmock = mock_temescal.temescal
        tmock.return_value = Mock()
        instance = tmock.return_value

        def temescal_side_effect(addr, port, callback):
            mac_info = {"msg": "MAC_INFO_DEV", "data": {"s_uuid": "uuid"}}
            instance.get_mac_info.side_effect = lambda: callback(mac_info)
            info = {"msg": "SPK_LIST_VIEW_INFO", "data": {"s_user_name": "name"}}
            instance.get_info.side_effect = lambda: callback(info)
            return DEFAULT

        tmock.side_effect = temescal_side_effect

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "name"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_PORT,
    }
    assert len(mock_setup_entry.mock_calls) == 1
    mock_uuid_q.empty.assert_called_once()
    mock_uuid_q.put_nowait.assert_called_once()
    mock_uuid_q.get.assert_called_once()


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.test_connect",
        side_effect=ConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_already_configured(hass):
    """Test we handle already configured error."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 0000,
        },
        unique_id="uuid",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.lg_soundbar.config_flow.test_connect",
        return_value={"uuid": "uuid", "name": "name"},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
