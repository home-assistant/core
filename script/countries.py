# Import only what is necessary
from pathlib import Path
from pycountry import countries
from .hassfest.serializer import format_python_namespace

# Create a set of alpha-2 country codes
country_codes = {country.alpha_2 for country in countries}

# Build the generator string
generator_string = """script.countries

The values are directly corresponding to the ISO 3166 standard. If you need changes
to the political situation in the world, please contact the ISO 3166 working group.
"""

# Build the Python namespace dictionary
namespace = {
    "COUNTRIES": country_codes,
}

# Combine content in memory
content = format_python_namespace(namespace, generator=generator_string)

# Write content to the file in one go
file_path = "homeassistant/generated/countries.py"
Path(file_path).write_text(content)
