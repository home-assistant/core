"""Test the Voice app config flow."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.hassio import AddonError, AddonState
from homeassistant.components.voice_support.const import (
    API_VERSION,
    DOMAIN,
    REPOSITORY_URL,
)
from homeassistant.config_entries import SOURCE_HASSIO, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .conftest import FakeApp

DISCOVERY = HassioServiceInfo(
    config={CONF_HOST: "f1b2c3d4-voice", CONF_PORT: 10800},
    name="Voice",
    slug="f1b2c3d4_voice",
    uuid="0123456789abcdef",
)


async def test_the_app_announcing_itself(hass: HomeAssistant) -> None:
    """Test the app is set up with nothing to fill in."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Voice"
    assert result["data"] == {CONF_HOST: "f1b2c3d4-voice", CONF_PORT: 10800}
    assert result["result"].unique_id == "0123456789abcdef"


async def test_the_same_app_twice(hass: HomeAssistant) -> None:
    """Test a second announcement updates where the app is, and stops."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789abcdef",
        data={CONF_HOST: "old-host", CONF_PORT: 10800},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=DISCOVERY
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # ...and the app's new address is taken from it, in case it moved
    assert entry.data[CONF_HOST] == "f1b2c3d4-voice"


async def test_installing_the_app_for_someone_who_has_none(
    hass: HomeAssistant,
    app_manager: MagicMock,
    install_app: MagicMock,
    discovered_app: AsyncMock,
) -> None:
    """Test adding Voice with no app installed installs and starts one."""
    app_manager.async_get_addon_info.return_value.state = AddonState.NOT_INSTALLED

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "install_app"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_app"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_app.call_count == 1
    assert app_manager.async_start_addon.call_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "f1b2c3d4-voice", CONF_PORT: 10800}
    # Keyed on the app's own announcement, so uninstalling the app removes it
    assert result["result"].unique_id == "0123456789abcdef"


async def test_an_installed_app_is_only_started(
    hass: HomeAssistant,
    app_manager: MagicMock,
    install_app: MagicMock,
    discovered_app: AsyncMock,
) -> None:
    """Test an app that is there but stopped is not installed again."""
    app_manager.async_get_addon_info.return_value.state = AddonState.NOT_RUNNING

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "start_app"

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert install_app.call_count == 0
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "0123456789abcdef"


@pytest.mark.usefixtures("app_manager")
async def test_a_running_app_is_taken_as_it_is(
    hass: HomeAssistant, discovered_app: AsyncMock
) -> None:
    """Test an app already running, whose announcement was never acted on."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert discovered_app.call_count == 0
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "f1b2c3d4-voice", CONF_PORT: 10800}
    assert result["result"].unique_id == "0123456789abcdef"


async def test_an_app_the_store_has_never_heard_of(
    hass: HomeAssistant, app_manager: MagicMock
) -> None:
    """Test the repository being missing is said plainly."""
    app_manager.async_get_addon_info.return_value.state = AddonState.NOT_INSTALLED
    app_manager.async_get_addon_info.return_value.available = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "repository_missing"
    assert result["description_placeholders"]["repository"] == REPOSITORY_URL


async def test_an_install_that_fails(
    hass: HomeAssistant, app_manager: MagicMock, discovered_app: AsyncMock
) -> None:
    """Test a failed install ends the flow rather than hanging."""
    app_manager.async_get_addon_info.return_value.state = AddonState.NOT_INSTALLED

    async def _fail() -> None:
        await asyncio.sleep(0)
        raise AddonError("no")

    app_manager.async_schedule_install_addon = MagicMock(
        side_effect=lambda *_, **__: hass.async_create_task(_fail())
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "install_failed"


async def test_an_app_that_starts_but_never_says_where_it_is(
    hass: HomeAssistant, app_manager: MagicMock
) -> None:
    """Test the flow stops rather than guessing the app's address."""
    app_manager.async_get_addon_info.return_value.state = AddonState.NOT_RUNNING

    with patch(
        "homeassistant.components.voice_support.config_flow.async_wait_for_discovery",
        AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "start_failed"


@pytest.mark.usefixtures("app_manager")
async def test_adding_it_twice(hass: HomeAssistant) -> None:
    """Test there is nothing to add when the app is already set up."""
    MockConfigEntry(domain=DOMAIN, unique_id="0123456789abcdef").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("socket_enabled")
async def test_without_a_supervisor_the_address_is_asked_for(
    hass: HomeAssistant, fake_app: FakeApp
) -> None:
    """Test an app running somewhere else can be set up by hand."""
    assert fake_app.server is not None

    with patch(
        "homeassistant.components.voice_support.config_flow.is_hassio",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: fake_app.server.host, CONF_PORT: fake_app.server.port},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Voice"
    assert result["data"] == {
        CONF_HOST: fake_app.server.host,
        CONF_PORT: fake_app.server.port,
    }
    # An address typed in by hand has no announcement to be keyed on
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("socket_enabled")
async def test_an_address_with_nothing_behind_it(
    hass: HomeAssistant, fake_app: FakeApp
) -> None:
    """Test a wrong address is reported, and the right one still works."""
    assert fake_app.server is not None

    with patch(
        "homeassistant.components.voice_support.config_flow.is_hassio",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: fake_app.server.host, CONF_PORT: 1}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manual"
        assert result["errors"] == {"base": "cannot_connect"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: fake_app.server.host, CONF_PORT: fake_app.server.port},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("socket_enabled")
async def test_an_app_speaking_a_protocol_we_do_not_know(
    hass: HomeAssistant, fake_app: FakeApp
) -> None:
    """Test an app from the future is refused at the form, not set up mute."""
    assert fake_app.server is not None
    fake_app.info["api_version"] = API_VERSION + 1
    address = {CONF_HOST: fake_app.server.host, CONF_PORT: fake_app.server.port}

    with patch(
        "homeassistant.components.voice_support.config_flow.is_hassio",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], address
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unsupported_version"}

        # ...and an app it can talk to is set up from the same form
        fake_app.info["api_version"] = API_VERSION
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], address
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None


async def test_an_app_configured_by_hand_that_later_announces_itself(
    hass: HomeAssistant,
) -> None:
    """Test the announcement does not add a second entry beside it."""
    MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "f1b2c3d4-voice", CONF_PORT: 10800}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_a_start_that_fails(hass: HomeAssistant, app_manager: MagicMock) -> None:
    """Test a Supervisor that refuses to start the app."""
    app_manager.async_get_addon_info.return_value.state = AddonState.NOT_RUNNING
    app_manager.async_start_addon = AsyncMock(side_effect=AddonError("no"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "start_failed"


@pytest.mark.usefixtures("app_manager")
@pytest.mark.usefixtures("socket_enabled")
async def test_a_running_app_that_never_announced_itself(
    hass: HomeAssistant, fake_app: FakeApp, app_manager: MagicMock
) -> None:
    """Test an app the Supervisor runs but never passed an announcement on.

    The Supervisor only forwards the services it knows the names of, so
    where the container is has to do instead.
    """
    assert fake_app.server is not None
    app_manager.async_get_addon_info.return_value.hostname = fake_app.server.host

    with (
        patch(
            "homeassistant.components.voice_support.config_flow.async_get_discovery",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.voice_support.config_flow.DEFAULT_PORT",
            fake_app.server.port,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: fake_app.server.host,
        CONF_PORT: fake_app.server.port,
    }
    assert result["result"].unique_id == "542a9043_voice"


async def test_a_running_app_that_is_not_answering(
    hass: HomeAssistant, app_manager: MagicMock
) -> None:
    """Test an app the Supervisor runs that cannot be reached where it says."""
    with (
        patch(
            "homeassistant.components.voice_support.config_flow.async_get_discovery",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.voice_support.client.VoiceSupportClient.async_update_info",
            AsyncMock(side_effect=TimeoutError),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_discovery"


async def test_a_running_app_the_supervisor_cannot_place(
    hass: HomeAssistant, app_manager: MagicMock
) -> None:
    """Test an app with no announcement and no hostname either."""
    app_manager.async_get_addon_info.return_value.hostname = None

    with patch(
        "homeassistant.components.voice_support.config_flow.async_get_discovery",
        AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_discovery"


async def test_a_supervisor_that_will_not_say(
    hass: HomeAssistant, app_manager: MagicMock
) -> None:
    """Test being unable to read the app's state at all."""
    app_manager.async_get_addon_info = AsyncMock(side_effect=AddonError("no"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "app_info_failed"
