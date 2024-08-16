"""Constants for the AWS Data integration."""

import logging

DOMAIN = "aws_data"
DOMAIN_DATA = "aws_client"
DOMAIN_ENTRIES = "entries"
<<<<<<< HEAD
=======
CONST_COORD_EC2 = "aws_coordinator_ec2"
CONST_COORD_S3 = "aws_coordinator_s3"
CONST_COORD_SERVICES = "aws_coordinator_services"
>>>>>>> 833ac3afab (Setup Coordinates)
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
<<<<<<< HEAD

GENERAL_REGION = "us-east-1"
DEFAULT_REGION = GENERAL_REGION

API_DATA = "api"

USER_INPUT_DATA = "USER_DATA"
USER_INPUT_ID = "INPUT_ID"
=======
CONST_ERRORS = "aws_errors"

DESC_COMPUTE = "compute"
DESC_STORAGE = "storage"
DESC_NETWORK = "network"
DESC_OBJECTS = "s3_objects"
DESC_SIZE = "s3_size"
DESC_COST = "ce_cost"

SERVICE_EC2 = "ec2"
SERVICE_S3 = "s3"
SERVICE_CE = "ce"
EC2_DEF_INTERVAL = 300
S3_DEF_INTERVAL = 86400
CE_DEF_INTERVAL = 86400

GENERAL_REGION = "us-east-1"
DEFAULT_REGION = GENERAL_REGION
SUPPORTED_SERVICES = [SERVICE_EC2, SERVICE_S3, SERVICE_CE]
SUPPORTED_METRICS = {
    SERVICE_EC2: {DESC_COMPUTE, DESC_STORAGE, DESC_NETWORK},
    SERVICE_S3: {DESC_OBJECTS, DESC_SIZE},
    SERVICE_CE: {DESC_COST},
}
EC2_METRIC_STATISTIC = [
    {"metric": "CPUUtilization", "unit": "Percent"},
    {"metric": "NetworkOut", "unit": "Bytes"},
    {"metric": "EBSWriteBytes", "unit": "Bytes"},
    {"metric": "EBSReadBytes", "unit": "Bytes"},
]

S3_METRIC_STATISTIC = [
    {"metric": "CPUUtilization", "unit": "Percent"},
    {"metric": "NetworkOut", "unit": "Bytes"},
    {"metric": "EBSWriteBytes", "unit": "Bytes"},
    {"metric": "EBSReadBytes", "unit": "Bytes"},
]

API_DATA = "api"
USER_INPUT_DATA = "USER_DATA"
USER_INPUT_ID = "INPUT_ID"
USER_INPUT_SECRET = "INPUT_SECRET"
>>>>>>> 833ac3afab (Setup Coordinates)
USER_INPUT_REGIONS = "INPUT_REGIONS"
USER_INPUT_SERVICES = "INPUTE_SERVICES"


_LOGGER = logging.getLogger(__name__)
