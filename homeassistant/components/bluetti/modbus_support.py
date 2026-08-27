"""Model-to-Modbus-device-type mapping for the optional local Modbus data source."""

# Matches bluetti_modbus_lib.devices.getter.get_device()'s recognized device
# types. "smeter" is deliberately excluded - it's a standalone smart-meter
# accessory, never a power station's own `UserProduct.model` value.
MODBUS_CAPABLE_DEV_TYPES = {"balco260", "ep2000"}


def modbus_dev_type_for_model(model: str | None) -> str | None:
    """Return the bluetti_modbus_lib device type for a cloud model string, or None."""
    # Not always a bare "balco260"/"ep2000": a real BLUETTI cloud account's
    # UserProduct.model has been observed as "Balco260-Balco260" - confirmed
    # via a real diagnostics dump, not assumed. The suffix after the first
    # hyphen is a custom device name the user can set in the BLUETTI phone
    # app (it happened to match the model name here), not a fixed
    # duplication, so it can be anything - including, in principle, another
    # model's name. Only the part before the first hyphen is the real model,
    # so match that exactly rather than checking the whole string by
    # containment (which would misclassify e.g. "AC200L-EP2000").
    normalized = (model or "").strip().lower()
    model_part = normalized.split("-", 1)[0]
    return model_part if model_part in MODBUS_CAPABLE_DEV_TYPES else None
