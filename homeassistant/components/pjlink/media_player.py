"""Support for controlling projector via the PJLink protocol."""

from __future__ import annotations

from aiopjlink import PJLinkERR3, PJLinkException, PJLinkNoConnection, Power, Sources
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import PJLinkConfigEntry
from .const import CONF_ENCODING, DEFAULT_ENCODING, DEFAULT_PORT, DOMAIN

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the PJLink platform."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            breaks_in_ha_version="2026.11.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result.get('reason')}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "PJLink",
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2026.11.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "PJLink",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PJLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PJLink media player."""
    async_add_entities([PjLinkDevice(entry)], update_before_add=True)


def _format_input_source(input_source: tuple[Sources.Mode, int]) -> str:
    """Format input source for display in UI."""
    return f"{input_source[0].name} {input_source[1]}"


class PjLinkDevice(MediaPlayerEntity):
    """Representation of a PJLink device."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, entry: PJLinkConfigEntry) -> None:
        """Initialize the PJLink device."""
        self._projector = entry.runtime_data
        self._source_name_mapping: dict[str, tuple[Sources.Mode, int]] = {}

        self._attr_name = entry.title
        self._attr_is_volume_muted = False
        self._attr_state = MediaPlayerState.OFF
        self._attr_source = None
        self._attr_source_list = []
        self._attr_available = False
        self._attr_unique_id = entry.entry_id

    def _force_off(self):
        self._attr_state = MediaPlayerState.OFF
        self._attr_is_volume_muted = False
        self._attr_source = None

    async def _async_setup_projector(self):
        try:
            if not self._attr_name:
                self._attr_name = await self._projector.info.projector_name()
            inputs = await self._projector.sources.available()
        except PJLinkNoConnection:
            return False
        except PJLinkException:
            raise

        self._source_name_mapping = {_format_input_source(x): x for x in inputs}
        self._attr_source_list = sorted(self._source_name_mapping)
        return True

    async def async_update(self) -> None:
        """Get the latest state from the device."""

        if not self._attr_available:
            self._attr_available = await self._async_setup_projector()

        if not self._attr_available:
            self._force_off()
            return

        try:
            pwstate = await self._projector.power.get()
            if pwstate in (Power.State.ON, Power.State.WARMING):
                self._attr_state = MediaPlayerState.ON
                mute_status = await self._projector.mute.status()
                self._attr_is_volume_muted = mute_status[1]
                self._attr_source = _format_input_source(
                    await self._projector.sources.get()
                )
            else:
                self._force_off()
        except KeyError as e:
            if str(e) == "'OK'":
                self._force_off()
            else:
                raise
        except PJLinkERR3:
            self._force_off()
        except PJLinkNoConnection:
            self._attr_available = False
        except PJLinkException:
            raise

    async def async_turn_off(self) -> None:
        """Turn projector off."""
        await self._projector.power.turn_off()

    async def async_turn_on(self) -> None:
        """Turn projector on."""
        await self._projector.power.turn_on()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) of unmute (false) media player."""
        await self._projector.mute.audio(mute)

    async def async_select_source(self, source: str) -> None:
        """Set the input source."""
        source_dict = self._source_name_mapping[source]
        await self._projector.sources.set(source_dict[0], source_dict[1])
