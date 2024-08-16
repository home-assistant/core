"""Constants for the AWS Data integration."""

import logging

DOMAIN = "aws_data"
DOMAIN_DATA = "aws_client"
DOMAIN_ENTRIES = "entries"
CONST_AWS_KEY = "aws_key"
CONST_AWS_SECRET = "aws_secret"
CONST_AWS_REGION = "aws_region"
CONST_AWS_SERVICES = "aws_services"
CONST_GENERAL_REGION = "aws_general_region"
CONST_SCAN_REGIONS = "aws_scan_regions"
CONST_REGION_LIST = "aws_region_list"
CONST_REGION_STR = "aws_region_str"
CONST_GENERIC_ID = "aws_id_generic"
CONST_ACCOUNT_ID = "aws_account_id"
CONST_ALL_REGIONS = "aws_all_regions"

GENERAL_REGION = "us-east-1"
DEFAULT_REGION = GENERAL_REGION

API_DATA = "api"

USER_INPUT_DATA = "USER_DATA"
USER_INPUT_ID = "INPUT_ID"
USER_INPUT_REGIONS = "INPUT_REGIONS"
USER_INPUT_SERVICES = "INPUTE_SERVICES"


_LOGGER = logging.getLogger(__name__)
