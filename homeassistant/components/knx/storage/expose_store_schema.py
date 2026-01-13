"""KNX expose store schema."""

import voluptuous as vol

from homeassistant.components.knx.const import KNX_ADDRESS, ExposeType
from homeassistant.helpers.typing import VolDictType

from .. import ExposeSchema
from .knx_selector import GASelector

EXPOSE_TIME_SCHEMA: VolDictType = {
    vol.Required(ExposeSchema.CONF_KNX_EXPOSE_TYPE): ExposeType.TIME.value,
    vol.Required(KNX_ADDRESS): GASelector(state=False, passive=False, write_required=True, valid_dpt="10.001"),
}

EXPOSE_DATE_SCHEMA: VolDictType = {
    vol.Required(ExposeSchema.CONF_KNX_EXPOSE_TYPE): ExposeType.DATE.value,
    vol.Required(KNX_ADDRESS): GASelector(state=False, passive=False, write_required=True, valid_dpt="11.001"),
}

EXPOSE_DATETIME_SCHEMA: VolDictType = {
    vol.Required(ExposeSchema.CONF_KNX_EXPOSE_TYPE): ExposeType.DATETIME.value,
    vol.Required(KNX_ADDRESS): GASelector(state=False, passive=False, write_required=True, valid_dpt="19.001"),
}

KNX_SCHEMA_FOR_TYPE = {
    ExposeType.TIME: EXPOSE_TIME_SCHEMA,
    ExposeType.DATE: EXPOSE_DATE_SCHEMA,
    ExposeType.DATETIME: EXPOSE_DATETIME_SCHEMA,
}
