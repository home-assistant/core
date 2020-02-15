"""Integrate with AliDNS."""
import asyncio
from datetime import timedelta
import json
import logging
from re import search

from aliyunsdkalidns.request.v20150109.AddDomainRecordRequest import (
    AddDomainRecordRequest,
)
from aliyunsdkalidns.request.v20150109.DescribeSubDomainRecordsRequest import (
    DescribeSubDomainRecordsRequest,
)
from aliyunsdkalidns.request.v20150109.UpdateDomainRecordRequest import (
    UpdateDomainRecordRequest,
)
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
from aliyunsdkcore.client import AcsClient
import async_timeout
import voluptuous as vol

from homeassistant.const import CONF_DOMAIN, CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
TIMEOUT = 30  # seconds
INTERNET_IP_URL = "http://www.3322.org/dyndns/getip"

DEFAULT_INTERVAL = timedelta(minutes=10)
DOMAIN = "alidns"

CONF_ACCESS_ID = "access_id"
CONF_ACCESS_KEY = "access_key"
CONF_SUB_DOMAIN = "sub_domain"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ACCESS_ID): cv.string,
                vol.Required(CONF_ACCESS_KEY): cv.string,
                vol.Required(CONF_DOMAIN): cv.string,
                vol.Required(CONF_SUB_DOMAIN): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL): vol.All(
                    cv.time_period, cv.positive_timedelta
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Initialize the AliDNS component."""
    conf = config[DOMAIN]
    access_id = conf.get(CONF_ACCESS_ID)
    access_key = conf.get(CONF_ACCESS_KEY)
    domain = conf.get(CONF_DOMAIN)
    sub_domain = conf.get(CONF_SUB_DOMAIN)
    update_interval = conf[CONF_SCAN_INTERVAL]

    session = hass.helpers.aiohttp_client.async_get_clientsession()
    acs_client = AcsClient(access_id, access_key)

    result = await _update_alidns(hass, session, acs_client, domain, sub_domain)

    if result is False:
        return False

    async def update_domain_callback(now):
        """Update the AliDNS entry."""
        await _update_alidns(hass, session, acs_client, domain, sub_domain)

    hass.helpers.event.async_track_time_interval(
        update_domain_callback, update_interval
    )

    return True


async def _update_alidns(hass, session, acs_client, domain, sub_domain):
    """Update AliDNS."""
    try:
        with async_timeout.timeout(TIMEOUT):
            resp = await session.get(INTERNET_IP_URL)
            body = await resp.text()
            match = search(r"(\d+\.\d+\.\d+\.\d+)\n", body)

            if match:
                my_ip = match.group(1)

                dns_record = None
                request = DescribeSubDomainRecordsRequest()
                request.set_accept_format("json")

                request.set_SubDomain(sub_domain + "." + domain)

                response = acs_client.do_action_with_exception(request)

                response_json = json.loads(response)
                if response_json["TotalCount"] > 0:
                    dns_record = response_json["DomainRecords"]["Record"][0]

                if dns_record:
                    if my_ip != dns_record["Value"]:
                        _LOGGER.info("Update Domain Record")
                        request = UpdateDomainRecordRequest()
                        request.set_accept_format("json")

                        request.set_RecordId(dns_record["RecordId"])
                        request.set_RR(sub_domain)
                        request.set_Type("A")
                        request.set_Value(my_ip)

                        acs_client.do_action_with_exception(request)
                    _LOGGER.info("No need to Update")
                else:
                    request = AddDomainRecordRequest()
                    request.set_accept_format("json")

                    request.set_DomainName(domain)
                    request.set_RR(sub_domain)
                    request.set_Type("A")
                    request.set_Value(my_ip)

                    acs_client.do_action_with_exception(request)
                    _LOGGER.info("Add Domain Record")

                return True

            _LOGGER.warning(
                "Failed to update alidns. Get Internet IP Exception:%s", body
            )

    except ServerException as s_err:
        _LOGGER.warning("Failed to update alidns. Server Exception:%s", s_err)

    except ClientException as c_err:
        _LOGGER.warning("Failed to update alidns. Client Exception:%s", c_err)

    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout to update alidns")

    return False
