"""Test the Network UPS Tools (NUT) config flow."""
from asynctest import MagicMock, patch

from homeassistant import config_entries, setup
from homeassistant.components.nut.const import DOMAIN

from tests.common import MockConfigEntry


def _get_mock_pynutclient(list_vars=None):
    pynutclient = MagicMock()
    type(pynutclient).list_ups = MagicMock(return_value=["ups1"])
    type(pynutclient).list_vars = MagicMock(return_value=list_vars)
    return pynutclient


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_pynut = _get_mock_pynutclient(list_vars={"battery.voltage": "voltage"})

    with patch(
        "homeassistant.components.nut.PyNUTClient", return_value=mock_pynut,
    ), patch(
        "homeassistant.components.nut.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.nut.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "port": 2222,
                "alias": "ups1",
                "resources": ["battery.charge"],
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "ups1@1.1.1.1:2222"
    assert result2["data"] == {
        "alias": "ups1",
        "host": "1.1.1.1",
        "name": "NUT UPS",
        "password": "test-password",
        "port": 2222,
        "resources": ["battery.charge"],
        "username": "test-username",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_import(hass):
    """Test we get the form with import source."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "2.2.2.2", "port": 123, "resources": ["battery.charge"]},
    )
    config_entry.add_to_hass(hass)

    mock_pynut = _get_mock_pynutclient(list_vars={"battery.voltage": "serial"})

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
    assert len(mock_setup_entry.mock_calls) == 2


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
                "alias": "ups1",
                "resources": ["battery.charge"],
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
