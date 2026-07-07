"""Constants for the Marantz IR integration."""

from infrared_protocols.codes.marantz import models as marantz_models

from homeassistant.util import slugify

DOMAIN = "marantz_infrared"
CONF_INFRARED_EMITTER_ENTITY_ID = "infrared_emitter_entity_id"

MODELS: dict[str, marantz_models.MarantzModel] = {
    slugify(model.name): model for model in marantz_models.ALL_MODELS
}
