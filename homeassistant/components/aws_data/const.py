"""Constants for the AWS Data integration."""

import logging

DOMAIN = "aws_data"
DOMAIN_DATA = "aws_client"
CONST_FILTER = "filter"
CONST_SERVICE_NAME = "name"
CONST_ACCOUNT = "account"
CONST_SERVICE_ID = "id"
CONST_SERVICE_REASON = "reason"
CONST_INTERVAL = "interval"
CONST_SECONDS = "seconds"
CONST_AWS_KEY = "aws_key"
CONST_AWS_SECRET = "aws_secret"
CONST_AWS_REGION = "aws_region"
CONST_AWS_SERVICES = "aws_services"
CONST_CE_SELECT = "aws_ce_select"
CONST_SCAN_REGIONS = "aws_scan_regions"
CONST_GENERIC_ID = "aws_id_generic"
CONST_ACCOUNT_ID = "aws_account_id"
CONST_ERRORS = "aws_errors"
SERVICE_EC2 = "ec2"
SERVICE_S3 = "s3"
SERVICE_CE = "ce"
EC2_DEF_INTERVAL = 300
S3_DEF_INTERVAL = 86400
CE_DEF_INTERVAL = 86400

GENERAL_REGION = "us-east-1"
DEFAULT_REGION = GENERAL_REGION

EC2_METRIC_STATISTIC = [
    {"metric": "CPUUtilization", "unit": "Percent"},
    {"metric": "NetworkOut", "unit": "Bytes"},
    {"metric": "EBSWriteBytes", "unit": "Bytes"},
    {"metric": "EBSReadBytes", "unit": "Bytes"},
]
S3_METRIC_STATISTIC = [
    {"metric": "s3_objects", "unit": "count"},
    {"metric": "s3_size", "unit": "Bytes"},
]
CE_METRIC_STATISTIC = [
    {"metric": "monthly_cost", "unit": "sum"},
]
SUPPORTED_SERVICES = [SERVICE_EC2, SERVICE_S3, SERVICE_CE]
SUPPORTED_METRICS = {
    SERVICE_EC2: EC2_METRIC_STATISTIC,
    SERVICE_S3: S3_METRIC_STATISTIC,
    SERVICE_CE: CE_METRIC_STATISTIC,
}

API_DATA = "api"
USER_INPUT = "USER_DATA"
U_ID = "INPUT_ID"
U_SECRET = "INPUT_SECRET"
U_REGIONS = "INPUT_REGIONS"
U_SERVICES = "INPUTE_SERVICES"


_LOGGER = logging.getLogger(__name__)
