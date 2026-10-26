"""LLM tools for the Hass.io integration."""

from datetime import UTC, datetime, timedelta
import math
from typing import override

from homeassistant.components.llm import LLMTools
from homeassistant.components.system_log.llm import SystemLogGetLogsTool  # pylint: disable=home-assistant-component-root-import
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.llm import LLM_API_HOME_ASSISTANT, LLMContext

from .const import DATA_ADDONS_LIST, DATA_COMPONENT, DOMAIN
from .handler import HassioAPIError

APP_SOURCE_PREFIX = "app:"

# Core and Supervisor lines start with their own timestamp and level
_PLAIN_SOURCES = ["core", "supervisor"]
_SYSTEM_SOURCES = {
    "core": "Home Assistant",
    "supervisor": "the Supervisor",
    "host": "the operating system, records have no level",
    "dns": "the DNS plugin, records have no level",
    "audio": "the audio plugin, records have no level",
    "multicast": "the multicast plugin, records have no level",
}


def _journal_time(time: datetime) -> str:
    """Return the time in seconds with microseconds for the journal.

    The exact time lets the next page start within a second that has more
    lines than one read.
    """
    microseconds = (time - datetime(1970, 1, 1, tzinfo=UTC)) // timedelta(
        microseconds=1
    )
    return f"{microseconds // 1_000_000}.{microseconds % 1_000_000:06d}"


class SupervisorGetLogsTool(SystemLogGetLogsTool):
    """LLM Tool querying the logs of the system and apps from the Supervisor."""

    name = "hassio__get_logs"
    integration = DOMAIN

    def __init__(self, apps: dict[str, str]) -> None:
        """Initialize the tool with the names of the installed apps by slug."""
        super().__init__(
            {
                **_SYSTEM_SOURCES,
                **{
                    f"{APP_SOURCE_PREFIX}{slug}": (
                        f"the {name} app, records have no level"
                    )
                    for slug, name in apps.items()
                },
            },
            _PLAIN_SOURCES,
        )

    @override
    async def async_read_source(
        self,
        hass: HomeAssistant,
        source: str,
        start_time: datetime,
        end_time: datetime,
        lines: int,
    ) -> list[str]:
        """Return the oldest lines of the log of a source in the time window."""
        if source.startswith(APP_SOURCE_PREFIX):
            command = f"/addons/{source.removeprefix(APP_SOURCE_PREFIX)}/logs"
        else:
            command = f"/{source}/logs"
        try:
            text: str = await hass.data[DATA_COMPONENT].send_command(
                command,
                method="get",
                return_text=True,
                params={
                    # Verbose adds the timestamp and the process to each line
                    "format": "plain" if source in _PLAIN_SOURCES else "verbose",
                    "no_colors": "",
                },
                # The journal has lines received after the record was created,
                # so read until the next second and filter the rest out later
                range_header=(
                    f"realtime={_journal_time(start_time)}"
                    f":{math.floor(end_time.timestamp()) + 1}:{lines}"
                ),
            )
        except HassioAPIError as err:
            raise HomeAssistantError(f"Could not read the {source} log") from err
        return text.splitlines()


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the Hass.io LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None

    apps = {app.slug: app.name for app in hass.data.get(DATA_ADDONS_LIST) or []}
    return LLMTools(tools=[SupervisorGetLogsTool(apps)])
