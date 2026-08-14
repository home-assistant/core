"""System health — the three numbers that answer "is this working?".

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

Home Assistant's system health page is the first place a user looks when something is wrong, and for
this integration the useful facts are unusual ones. Most integrations report "can I reach the
service?"; this one cannot reach anything — the panels reach *it*. So the questions are: is the port
actually bound, how many panels are talking, and how long ago did anything arrive.

**Age of the last frame, not "connected".** A TCP socket stays open long after the box at the far
end has lost power, so a connection count alone will happily report three healthy panels that all
went dark twenty minutes ago.

Nothing here identifies the installation: no serial, no MAC, no address. The page is a screenshot
people paste into forums.
"""

from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import DOMAIN


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register the health callback."""
    register.async_register_info(_system_health_info)


async def _system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Summarise every listener this integration is running."""
    entries = [
        entry
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if getattr(entry, "runtime_data", None) is not None
    ]
    if not entries:
        return {"listeners": 0}

    ports: list[str] = []
    known = connected = 0
    newest = None
    for entry in entries:
        runtime = entry.runtime_data
        ports.append(
            str(runtime.server.port) + ("" if runtime.server.is_running else " (down)")
        )
        for coordinator in runtime.coordinators.values():
            known += 1
            if coordinator.link.connected:
                connected += 1
            seen = coordinator.data.last_seen_at
            if seen is not None and (newest is None or seen > newest):
                newest = seen

    return {
        "listening_on": ", ".join(ports),
        "panels_configured": known,
        "panels_connected": connected,
        # The honest liveness signal. "Never" is a real answer and a common one: it means no panel
        # has been programmed to report here yet, which is the integration's most frequent problem.
        "last_frame": (
            f"{round((dt_util.utcnow() - newest).total_seconds())} s ago"
            if newest
            else "never"
        ),
    }
