"""Constants for the FireServiceRota integration."""

DOMAIN = "fireservicerota"

URL_LIST = {
    "www.brandweerrooster.nl": "BrandweerRooster",
    "www.fireservicerota.co.uk": "FireServiceRota",
}
WSS_BWRURL = "wss://{0}/cable?access_token={1}"

DATA_CLIENT = "client"
DATA_COORDINATOR = "coordinator"
