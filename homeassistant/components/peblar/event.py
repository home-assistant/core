"""Support for Peblar events."""

from typing import override

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PeblarAuthorizationDataUpdateCoordinator, PeblarConfigEntry
from .entity import PeblarEntity

# The coordinator does the talking; the entity only reads what it found.
PARALLEL_UPDATES = 0

ATTR_SESSION_NUMBER = "session_number"
ATTR_STARTED_AT = "started_at"
ATTR_TOKEN = "token"

EVENT_SESSION_AUTHORIZED = "session_authorized"

DESCRIPTION = EventEntityDescription(
    key="session_authorization",
    translation_key="session_authorization",
    event_types=[EVENT_SESSION_AUTHORIZED],
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Peblar events based on a config entry."""
    # A charger without a reader has no standalone list to authorize
    # against, so nobody is ever shown in.
    if not entry.runtime_data.system_information.hardware_has_rfid:
        return

    async_add_entities(
        [
            PeblarAuthorizationEventEntity(
                entry=entry,
                coordinator=entry.runtime_data.authorization_coordinator,
                description=DESCRIPTION,
            )
        ]
    )


class PeblarAuthorizationEventEntity(
    PeblarEntity[PeblarAuthorizationDataUpdateCoordinator], EventEntity
):
    """Reports a card being shown to start a charging session.

    The charger does not push this as it happens, so it is read back from
    the session the charger is on. A session already running when this
    entity starts is not reported: it was authorized before anyone here
    was watching, and dating it now would put the wrong time on it.
    """

    _session_number: int | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Take note of the session already running, without reporting it."""
        await super().async_added_to_hass()
        if (authorization := self.coordinator.data) is not None:
            self._session_number = authorization.session_number

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Report a session that was not there the last time we looked."""
        authorization = self.coordinator.data
        if (
            authorization is not None
            and authorization.session_number != self._session_number
        ):
            self._session_number = authorization.session_number
            self._trigger_event(
                EVENT_SESSION_AUTHORIZED,
                {
                    ATTR_SESSION_NUMBER: authorization.session_number,
                    # The charger's own start time, not the moment this
                    # was noticed: the two are seconds apart at best.
                    ATTR_STARTED_AT: authorization.started_at.isoformat(),
                    ATTR_TOKEN: authorization.token,
                },
            )

        super()._handle_coordinator_update()
