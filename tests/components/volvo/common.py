"""Common test utils for Volvo."""

from functools import lru_cache
import pathlib

from homeassistant.components.volvo.const import DOMAIN
from homeassistant.util.json import JsonObjectType, json_loads_object


@lru_cache
def load_json_object_fixture(name: str, model: str) -> JsonObjectType:
    """Load a JSON object from a fixture."""

    name = f"{name}.json"

    fixtures_path = (
        pathlib.Path().cwd().joinpath("tests", "components", DOMAIN, "fixtures")
    )

    model_path = fixtures_path.joinpath(model)

    if not model_path.exists():
        raise FileNotFoundError

    data_path = model_path.joinpath(name)

    # Check if the requested data is available for this model.
    # If not, fallback to the default data.
    if data_path.exists():
        fixture = data_path.read_text(encoding="utf8")
    else:
        fixture = fixtures_path.joinpath(name).read_text(encoding="utf8")

    return json_loads_object(fixture)
