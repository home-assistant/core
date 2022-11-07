"""Helper script to update country list.

ISO does not publish a machine readable list free of charge, so the list is generated
with help of the pycountry package.
"""
import pycountry

COUNTRIES = sorted({x.alpha_2 for x in pycountry.countries})

print(
    '    {\n        "',
    '", \n        "'.join(COUNTRIES),
    '",\n    }',
    sep="",
)
