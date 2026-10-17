"""SenseCAP models and their official catalog coverage."""

from sensecap_lorawan import S2101, S2102, S2103, S2104, S2105, S2106, S2107, S2120

MODELS = (
    S2101,
    S2102,
    S2103,
    S2104,
    S2105,
    S2106,
    S2107,
    S2120,
)
CATALOG_MODELS = [(stack, model) for model in MODELS for stack in model.identifiers]
