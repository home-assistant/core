"""Helper script to update country list.

ISO does not publish a machine readable list free of charge, so the list is generated
with help of the pycountry package.
"""
import black
import pycountry

COUNTRIES = sorted({x.alpha_2 for x in pycountry.countries})

print(black.format_str("{" + ",".join(COUNTRIES) + "}", mode=black.Mode()))
