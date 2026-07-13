"""Button platform for Edifier infrared integration."""

from dataclasses import dataclass
from typing import override

from infrared_protocols.codes.edifier.models import EdifierCommandSet, EdifierModel
from infrared_protocols.codes.edifier.r1280db import EdifierR1280DBCode
from infrared_protocols.codes.edifier.r1700bt import EdifierR1700BTCode
from infrared_protocols.codes.edifier.rc20g import EdifierRC20GCode
from infrared_protocols.codes.edifier.s360db import EdifierS360DBCode
from infrared_protocols.codes.edifier.s3000pro import EdifierS3000ProCode

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_COMMAND_SET, CONF_INFRARED_ENTITY_ID, EdifierCode
from .entity import EdifierIrEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class EdifierIrButtonEntityDescription(ButtonEntityDescription):
    """Describes Edifier IR button entity."""

    command_code: EdifierCode


COMMAND_SET_BUTTONS: dict[
    EdifierCommandSet,
    tuple[EdifierIrButtonEntityDescription, ...],
] = {
    EdifierCommandSet.R1700BT: (
        EdifierIrButtonEntityDescription(
            key="bluetooth",
            translation_key="bluetooth",
            command_code=EdifierR1700BTCode.BLUETOOTH,
        ),
        EdifierIrButtonEntityDescription(
            key="line_1",
            translation_key="line_1",
            command_code=EdifierR1700BTCode.LINE_1,
        ),
        EdifierIrButtonEntityDescription(
            key="line_2",
            translation_key="line_2",
            command_code=EdifierR1700BTCode.LINE_2,
        ),
        EdifierIrButtonEntityDescription(
            key="fx_on",
            translation_key="fx_on",
            command_code=EdifierR1700BTCode.FX_ON,
        ),
        EdifierIrButtonEntityDescription(
            key="fx_off",
            translation_key="fx_off",
            command_code=EdifierR1700BTCode.FX_OFF,
        ),
    ),
    EdifierCommandSet.R1280DB: (
        EdifierIrButtonEntityDescription(
            key="bluetooth",
            translation_key="bluetooth",
            command_code=EdifierR1280DBCode.BLUETOOTH,
        ),
        EdifierIrButtonEntityDescription(
            key="line_1",
            translation_key="line_1",
            command_code=EdifierR1280DBCode.LINE_1,
        ),
        EdifierIrButtonEntityDescription(
            key="line_2",
            translation_key="line_2",
            command_code=EdifierR1280DBCode.LINE_2,
        ),
        EdifierIrButtonEntityDescription(
            key="optical",
            translation_key="optical",
            command_code=EdifierR1280DBCode.OPTICAL,
        ),
        EdifierIrButtonEntityDescription(
            key="coax",
            translation_key="coax",
            command_code=EdifierR1280DBCode.COAX,
        ),
    ),
    EdifierCommandSet.S360DB: (
        EdifierIrButtonEntityDescription(
            key="bluetooth",
            translation_key="bluetooth",
            command_code=EdifierS360DBCode.BLUETOOTH,
        ),
        EdifierIrButtonEntityDescription(
            key="optical",
            translation_key="optical",
            command_code=EdifierS360DBCode.OPTICAL,
        ),
        EdifierIrButtonEntityDescription(
            key="coax",
            translation_key="coax",
            command_code=EdifierS360DBCode.COAX,
        ),
        EdifierIrButtonEntityDescription(
            key="pc",
            translation_key="pc",
            command_code=EdifierS360DBCode.PC,
        ),
        EdifierIrButtonEntityDescription(
            key="aux",
            translation_key="aux",
            command_code=EdifierS360DBCode.AUX,
        ),
    ),
    EdifierCommandSet.RC20G: (
        EdifierIrButtonEntityDescription(
            key="bluetooth",
            translation_key="bluetooth",
            command_code=EdifierRC20GCode.BLUETOOTH,
        ),
        EdifierIrButtonEntityDescription(
            key="pc",
            translation_key="pc",
            command_code=EdifierRC20GCode.PC,
        ),
        EdifierIrButtonEntityDescription(
            key="aux",
            translation_key="aux",
            command_code=EdifierRC20GCode.AUX,
        ),
        EdifierIrButtonEntityDescription(
            key="optical",
            translation_key="optical",
            command_code=EdifierRC20GCode.OPTICAL,
        ),
        EdifierIrButtonEntityDescription(
            key="coax",
            translation_key="coax",
            command_code=EdifierRC20GCode.COAX,
        ),
    ),
    EdifierCommandSet.S3000PRO: (
        EdifierIrButtonEntityDescription(
            key="usb",
            translation_key="usb",
            command_code=EdifierS3000ProCode.USB,
        ),
        EdifierIrButtonEntityDescription(
            key="bluetooth",
            translation_key="bluetooth",
            command_code=EdifierS3000ProCode.BLUETOOTH,
        ),
        EdifierIrButtonEntityDescription(
            key="line_bal",
            translation_key="line_bal",
            command_code=EdifierS3000ProCode.LINE_BAL,
        ),
        EdifierIrButtonEntityDescription(
            key="opt_coax",
            translation_key="opt_coax",
            command_code=EdifierS3000ProCode.OPT_COAX,
        ),
        EdifierIrButtonEntityDescription(
            key="eq_monitor",
            translation_key="eq_monitor",
            command_code=EdifierS3000ProCode.EQ_MONITOR,
        ),
        EdifierIrButtonEntityDescription(
            key="eq_dynamic",
            translation_key="eq_dynamic",
            command_code=EdifierS3000ProCode.EQ_DYNAMIC,
        ),
        EdifierIrButtonEntityDescription(
            key="eq_classic",
            translation_key="eq_classic",
            command_code=EdifierS3000ProCode.EQ_CLASSIC,
        ),
        EdifierIrButtonEntityDescription(
            key="eq_vocal",
            translation_key="eq_vocal",
            command_code=EdifierS3000ProCode.EQ_VOCAL,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Edifier IR buttons from a config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    command_set = EdifierCommandSet(entry.data[CONF_COMMAND_SET])
    model = EdifierModel(entry.data[CONF_MODEL])
    async_add_entities(
        EdifierIrButton(entry, model, infrared_entity_id, description)
        for description in COMMAND_SET_BUTTONS.get(command_set, ())
    )


class EdifierIrButton(EdifierIrEntity, InfraredEmitterConsumerEntity, ButtonEntity):
    """Edifier IR button entity."""

    entity_description: EdifierIrButtonEntityDescription

    def __init__(
        self,
        entry: ConfigEntry,
        model: EdifierModel,
        infrared_entity_id: str,
        description: EdifierIrButtonEntityDescription,
    ) -> None:
        """Initialize Edifier IR button."""
        super().__init__(entry, model, unique_id_suffix=description.key)
        self._infrared_emitter_entity_id = infrared_entity_id
        self.entity_description = description

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self._send_command(self.entity_description.command_code.to_command())
