import json
import requests
from datetime import datetime, timedelta
import logging

PROVINCES = ["groningen", "friesland", "drenthe", "overijssel", "gelderland", "utrecht", "noord-holland", "zuid-holland", "zeeland", "noord-brabant", "limburg", "flevoland"]
UPDATEHOUR = 12
RESETHOUR = 3 
_LOGGER = logging.getLogger(__name__)

class stookalert(object):

    def __init__(self, province):
        self._state = None
        self._alerts = {}
        self._province = self.check_province(province)
        self._last_updated = None

        if self._province is not None: 
            _LOGGER.info(f"Setting up Stookalert for province {province}")
        else:
            _LOGGER.info(f"Invalid province {province}. Please select one of the following: {PROVINCES}")
    
    def get_alert(self):
        alerts = self.request()
        
        if alerts is None:
            return

        for a in alerts:
            province = a.get("naam", "").lower()
            value = a.get("waarde", None)

            if not self.check_province(province):
                continue

            self._alerts[province] = value

            if province == self._province:
                self._state = value

    def request(self):
        try:            
            response = requests.get(self.get_url())
            
            self._last_updated = datetime.now()
            json_response = json.loads(response.text)

            return sorted(json_response, key = lambda i: i['naam']) 
        except requests.exceptions.RequestException:
            _LOGGER.error("Error getting Stookalert data")

    def get_url(self):
        updateDay = datetime.now()

        if updateDay.hour < RESETHOUR:
            updateDay = updateDay - timedelta(days=1)
        elif updateDay.hour < UPDATEHOUR:
            return f"https://www.rivm.nl/media/lml/stookalert/stookalert_noalert.json"

        return f"https://www.rivm.nl/media/lml/stookalert/stookalert_{updateDay.strftime('%Y%m%d')}.json"
    
    def check_province(self, province):
        find_province = province.lower()
        
        if find_province in PROVINCES:
            return find_province
        else:
            return None