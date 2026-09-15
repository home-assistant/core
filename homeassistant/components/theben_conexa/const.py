"""Constants for the Theben Conexa Smartmeter gateway integration."""

DOMAIN = "theben_conexa"

# The pypi package theben_conexa_smgw returns the raw OBIS codes
# according to the EN IEC 62056-61:2024 standard as a string of 12 hex digits.
# The more human readable A-B:C.D.E*F could be extracted from the hex string which is AABBCCDDEEFF
OBIS_IN = "0100010800ff"
OBIS_OUT = "0100020800ff"
