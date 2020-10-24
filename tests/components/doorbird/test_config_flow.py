"""Test the DoorBird config flow."""
import urllib

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.doorbird import CONF_CUSTOM_URL, CONF_TOKEN
from homeassistant.components.doorbird.const import CONF_EVENTS, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME

from tests.async_mock import MagicMock, patch
from tests.common import MockConfigEntry, init_recorder_component

VALID_CONFIG = {
    CONF_HOST: "1.2.3.4",
    CONF_USERNAME: "friend",
    CONF_PASSWORD: "password",
    CONF_NAME: "mydoorbird",
}


def _get_mock_doorbirdapi_return_values(ready=None, info=None):
    doorbirdapi_mock = MagicMock()
    type(doorbirdapi_mock).ready = MagicMock(return_value=ready)
    type(doorbirdapi_mock).info = MagicMock(return_value=info)

    return doorbirdapi_mock


def _get_mock_doorbirdapi_side_effects(ready=None, info=None):
    doorbirdapi_mock = MagicMock()
    type(doorbirdapi_mock).ready = MagicMock(side_effect=ready)
    type(doorbirdapi_mock).info = MagicMock(side_effect=info)

    return doorbirdapi_mock


async def test_user_form(hass):
    """Test we get the user form."""
    await hass.async_add_executor_job(
        init_recorder_component, hass
    )  # force in memory db

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    doorbirdapi = _get_mock_doorbirdapi_return_values(
        ready=[True], info={"WIFI_MAC_ADDR": "macaddr"}
    )
    with patch(
        "homeassistant.components.doorbird.config_flow.DoorBird",
        return_value=doorbirdapi,
    ), patch(
        "homeassistant.components.doorbird.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.doorbird.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "1.2.3.4"
    assert result2["data"] == {
        "host": "1.2.3.4",
        "name": "mydoorbird",
        "password": "password",
        "username": "friend",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_import(hass):
    """Test we get the form with import source."""
    await hass.async_add_executor_job(
        init_recorder_component, hass
    )  # force in memory db

    await setup.async_setup_component(hass, "persistent_notification", {})

    import_config = VALID_CONFIG.copy()
    import_config[CONF_EVENTS] = ["event1", "event2", "event3"]
    import_config[CONF_TOKEN] = "imported_token"
    import_config[
        CONF_CUSTOM_URL
    ] = "http://legacy.custom.url/should/only/come/in/from/yaml"

    doorbirdapi = _get_mock_doorbirdapi_return_values(
        ready=[True], info={"WIFI_MAC_ADDR": "macaddr"}
    )
    with patch(
        "homeassistant.components.doorbird.config_flow.DoorBird",
        return_value=doorbirdapi,
    ), patch("homeassistant.components.logbook.async_setup", return_value=True), patch(
        "homeassistant.components.doorbird.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.doorbird.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=import_config,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "1.2.3.4"
    assert result["data"] == {
        "host": "1.2.3.4",
        "name": "mydoorbird",
        "password": "password",
        "username": "friend",
        "events": ["event1", "event2", "event3"],
        "token": "imported_token",
        # This will go away once we convert to cloud hooks
        "hass_url_override": "http://legacy.custom.url/should/only/come/in/from/yaml",
    }
    # It is not possible to import options at this time
    # so they end up in the config entry data and are
    # used a fallback when they are not in options
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_import_with_zeroconf_already_discovered(hass):
    """Test we get the form with import source."""
    await hass.async_add_executor_job(
        init_recorder_component, hass
    )  # force in memory db

    await setup.async_setup_component(hass, "persistent_notification", {})

    # Running the zeroconf init will make the unique id
    # in progress
    zero_conf = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            "properties": {"macaddress": "1CCAE3DOORBIRD"},
            "name": "Doorstation - abc123._axis-video._tcp.local.",
            "host": "192.168.1.5",
        },
    )
    assert zero_conf["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert zero_conf["step_id"] == "user"
    assert zero_conf["errors"] == {}

    import_config = VALID_CONFIG.copy()
    import_config[CONF_EVENTS] = ["event1", "event2", "event3"]
    import_config[CONF_TOKEN] = "imported_token"
    import_config[
        CONF_CUSTOM_URL
    ] = "http://legacy.custom.url/should/only/come/in/from/yaml"

    doorbirdapi = _get_mock_doorbirdapi_return_values(
        ready=[True], info={"WIFI_MAC_ADDR": "1CCAE3DOORBIRD"}
    )
    with patch(
        "homeassistant.components.doorbird.config_flow.DoorBird",
        return_value=doorbirdapi,
    ), patch("homeassistant.components.logbook.async_setup", return_value=True), patch(
        "homeassistant.components.doorbird.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.doorbird.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=import_config,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "1.2.3.4"
    assert result["data"] == {
        "host": "1.2.3.4",
        "name": "mydoorbird",
        "password": "password",
        "username": "friend",
        "events": ["event1", "event2", "event3"],
        "token": "imported_token",
        # This will go away once we convert to cloud hooks
        "hass_url_override": "http://legacy.custom.url/should/only/come/in/from/yaml",
    }
    # It is not possible to import options at this time
    # so they end up in the config entry data and are
    # used a fallback when they are not in options
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_zeroconf_wrong_oui(hass):
    """Test we abort when we get the wrong OUI via zeroconf."""
    await hass.async_add_executor_job(
        init_recorder_component, hass
    )  # force in memory db

    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            "properties": {"macaddress": "notdoorbirdoui"},
            "host": "192.168.1.8",
            "name": "Doorstation - abc123._axis-video._tcp.local.",
        },
    )
    assert result["type"] == "abort"
    assert result["reason"] == "not_doorbird_device"


async def test_form_zeroconf_link_local_ignored(hass):
    """Test we abort when we get a link local address via zeroconf."""
    await hass.async_add_executor_job(
        init_recorder_component, hass
    )  # force in memory db

    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            "properties": {"macaddress": "1CCAE3DOORBIRD"},
            "host": "169.254.103.61",
            "name": "Doorstation - abc123._axis-video._tcp.local.",
        },
    )
    assert result["type"] == "abort"
    assert result["reason"] == "link_local_address"


async def test_form_zeroconf_correct_oui(hass):
    """Test we can setup from zeroconf with the correct OUI source."""
    await hass.async_add_executor_job(
        init_recorder_component, hass
    )  # force in memory db

    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            "properties": {"macaddress": "1CCAE3DOORBIRD"},
            "name": "Doorstation - abc123._axis-video._tcp.local.",
            "host": "192.168.1.5",
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    doorbirdapi = _get_mock_doorbirdapi_return_values(
        ready=[True], info={"WIFI_MAC_ADDR": "macaddr"}
    )
    with patch(
        "homeassistant.components.doorbird.config_flow.DoorBird",
        return_value=doorbirdapi,
    ), patch("homeassistant.components.logbook.async_setup", return_value=True), patch(
        "homeassistant.components.doorbird.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.doorbird.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_CONFIG
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "1.2.3.4"
    assert result2["data"] == {
        "host": "1.2.3.4",
        "name": "mydoorbird",
        "password": "password",
        "username": "friend",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_cannot_connect(hass):
    """Test we handle cannot connect error."""
    await hass.async_add_executor_job(
        init_recorder_component, hass
    )  # force in memory db

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    doorbirdapi = _get_mock_doorbirdapi_side_effects(ready=OSError)
    with patch(
        "homeassistant.components.doorbird.config_flow.DoorBird",
        return_value=doorbirdapi,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_user_invalid_auth(hass):
    """Test we handle cannot invalid auth error."""
    await hass.async_add_executor_job(
        init_recorder_component, hass
    )  # force in memory db

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_urllib_error = urllib.error.HTTPError(
        "http://xyz.tld", 401, "login failed", {}, None
    )
    doorbirdapi = _get_mock_doorbirdapi_side_effects(ready=mock_urllib_error)
    with patch(
        "homeassistant.components.doorbird.config_flow.DoorBird",
        return_value=doorbirdapi,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_options_flow(hass):
    """Test config flow options."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="abcde12345",
        data=VALID_CONFIG,
        options={CONF_EVENTS: ["event1", "event2", "event3"]},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.doorbird.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_EVENTS: "eventa,   eventc,    eventq"}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {CONF_EVENTS: ["eventa", "eventc", "eventq"]}
