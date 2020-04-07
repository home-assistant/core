"""Test the Network UPS Tools (NUT) config flow."""
from asynctest import MagicMock, patch

from homeassistant import config_entries, setup
from homeassistant.components.nut.const import DOMAIN


def _get_mock_pynutclient(list_vars=None, list_ups=None):
    pynutclient = MagicMock()
    type(pynutclient).list_ups = MagicMock(return_value=list_ups)
    type(pynutclient).list_vars = MagicMock(return_value=list_vars)
    return pynutclient


async def test_form_user_one_ups(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_pynut = _get_mock_pynutclient(
        list_vars={"battery.voltage": "voltage"}, list_ups=["ups1"]
    )

    with patch(
        "homeassistant.components.nut.PyNUTClient", return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "port": 2222,
            },
        )

    assert result2["step_id"] == "resources"
    assert result2["type"] == "form"

    with patch(
        "homeassistant.components.nut.PyNUTClient", return_value=mock_pynut,
    ), patch(
        "homeassistant.components.nut.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.nut.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"resources": ["battery.voltage"]},
        )

    assert result3["type"] == "create_entry"
    assert result3["title"] == "1.1.1.1:2222"
    assert result3["data"] == {
        "host": "1.1.1.1",
        "password": "test-password",
        "port": 2222,
        "resources": ["battery.voltage"],
        "username": "test-username",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_multiple_ups(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_pynut = _get_mock_pynutclient(
        list_vars={"battery.voltage": "voltage"}, list_ups=["ups1", "ups2"]
    )

    with patch(
        "homeassistant.components.nut.PyNUTClient", return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "port": 2222,
            },
        )

    assert result2["step_id"] == "ups"
    assert result2["type"] == "form"

    with patch(
        "homeassistant.components.nut.PyNUTClient", return_value=mock_pynut,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"alias": "ups2"},
        )

    assert result3["step_id"] == "resources"
    assert result3["type"] == "form"

    with patch(
        "homeassistant.components.nut.PyNUTClient", return_value=mock_pynut,
    ), patch(
        "homeassistant.components.nut.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.nut.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], {"resources": ["battery.voltage"]},
        )

    assert result4["type"] == "create_entry"
    assert result4["title"] == "ups2@1.1.1.1:2222"
    assert result4["data"] == {
        "host": "1.1.1.1",
        "password": "test-password",
        "alias": "ups2",
        "port": 2222,
        "resources": ["battery.voltage"],
        "username": "test-username",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_import(hass):
    """Test we get the form with import source."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    mock_pynut = _get_mock_pynutclient(
        list_vars={"battery.voltage": "serial"}, list_ups=["ups1"]
    )

    with patch(
        "homeassistant.components.nut.PyNUTClient", return_value=mock_pynut,
    ), patch(
        "homeassistant.components.nut.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.nut.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "localhost",
                "port": 123,
                "name": "name",
                "resources": ["battery.charge"],
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "localhost:123"
    assert result["data"] == {
        "host": "localhost",
        "port": 123,
        "name": "name",
        "resources": ["battery.charge"],
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_pynut = _get_mock_pynutclient()

    with patch(
        "homeassistant.components.nut.PyNUTClient", return_value=mock_pynut,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "port": 2222,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
