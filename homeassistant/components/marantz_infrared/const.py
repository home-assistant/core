"""Constants for the Marantz IR integration."""

from infrared_protocols.codes.marantz import models as marantz_models

from homeassistant.util import slugify

DOMAIN = "marantz_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_MODEL = "model"

MODELS: dict[str, marantz_models.MarantzModel] = {
    slugify(model.name): model for model in marantz_models.ALL_MODELS
}
