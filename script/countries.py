"""Helper script to update country list.

ISO does not publish a machine readable list free of charge, so the list is generated
with help of the pycountry package.
"""
from pathlib import Path

import pycountry

from .hassfest.serializer import format_python_namespace

countries = {x.alpha_2 for x in pycountry.countries}

generator_string = """script.countries

The values are directly corresponding to the ISO 3166 standard. If you need changes
to the political situation in the world, please contact the ISO 3166 working group.
"""

Path("homeassistant/generated/countries.py").write_text(
    format_python_namespace(
        {
            "COUNTRIES": countries,
        },
        generator=generator_string,
    )
)
