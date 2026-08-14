"""Two buttons: ask the panel for a fresh status frame, and read its programming.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

**This works in read-only mode, and that is deliberate.** `0x4D` asks the panel a question; it
changes nothing on the panel and cannot arm, disarm, bypass or switch anything. Read-only means the
integration never *writes*, not that it never speaks — and since the panel does not volunteer its
status, refusing to ask for it would leave a read-only installation with nothing to read.

`PARALLEL_UPDATES = 0` because pressing this queues one frame; it is not an update in the sense the
setting is about.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pyjfl import PanelNotConnectedError

from .const import CONF_SERIAL, DOMAIN, SUBENTRY_TYPE_PANEL
from .entity import JflEntity

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import JflConfigEntry
    from .coordinator import JflPanelCoordinator

PARALLEL_UPDATES = 0

REFRESH = ButtonEntityDescription(
    key="refresh_status",
    translation_key="refresh_status",
    entity_category=EntityCategory.DIAGNOSTIC,
)

READ_PROGRAMMING = ButtonEntityDescription(
    key="read_programming",
    translation_key="read_programming",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JflConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the status refresh button for every configured panel."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_PANEL:
            continue
        coordinator = entry.runtime_data.coordinators[str(subentry.data[CONF_SERIAL])]
        async_add_entities(
            [JflRefreshButton(coordinator), JflReadProgrammingButton(coordinator)],
            config_subentry_id=subentry.subentry_id,
        )


class JflRefreshButton(JflEntity, ButtonEntity):
    """Ask the panel for a status frame now, instead of waiting for the next poll."""

    entity_description = REFRESH

    def __init__(self, coordinator: JflPanelCoordinator) -> None:
        """Create the refresh button for this panel."""
        super().__init__(coordinator, REFRESH.key)

    @property
    def available(self) -> bool:
        """Stay available even while the panel is silent.

        Every other entity here goes unavailable with the panel, which is the convention and is
        right for them: they report state, and there is no state to report. This one is an
        *action*, and the moment somebody reaches for it is precisely when the panel looks wrong.
        A greyed-out button explains nothing; pressing it and being told "panel 000… is not
        connected" explains exactly what is wrong.
        """
        return True

    async def async_press(self) -> None:
        """Send `0x4D`. Fails loudly if the panel is not connected — never silently."""
        try:
            await self.coordinator.async_refresh_status()
        except PanelNotConnectedError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="panel_not_connected",
                translation_placeholders={"serial": self.coordinator.serial},
            ) from err


class JflReadProgrammingButton(JflEntity, ButtonEntity):
    """Read the panel's programming, which is where the real zone and partition names live.

    **A read, and only a read.** `0x44` asks; nothing in this integration sends `0x45`, the write.
    So this runs in read-only mode for the same reason the status refresh does.

    The coordinator already runs this automatically — once when a panel first connects, and again
    on the configured interval, but only when `KP` (the programming checksum in the status frame)
    shows something actually changed, and never again at all once a panel has proven it will not
    answer `0x44`. This button is the on-demand supplement: forcing a read right now, without
    waiting for the next tick, is useful right after reprogramming the panel from its own keypad.
    """

    entity_description = READ_PROGRAMMING

    def __init__(self, coordinator: JflPanelCoordinator) -> None:
        """Create the programming-read button for this panel."""
        super().__init__(coordinator, READ_PROGRAMMING.key)

    @property
    def available(self) -> bool:
        """Available while the panel is, unlike the refresh button.

        The difference is that this one has nothing useful to say when the panel is away: there is
        no cached answer it could refresh, and the error would repeat what the connectivity sensor
        already shows.
        """
        return super().available

    async def async_press(self) -> None:
        """Read the whole programming map. Takes a few seconds; the panel is paced deliberately."""
        try:
            await self.coordinator.async_read_programming()
        except PanelNotConnectedError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="panel_not_connected",
                translation_placeholders={"serial": self.coordinator.serial},
            ) from err
