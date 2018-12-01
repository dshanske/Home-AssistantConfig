import datetime
import logging
import json
import requests
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_LONGITUDE, CONF_LATITUDE, CONF_NAME, CONF_TIME_ZONE
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Shabbat Time"
HAVDALAH_MINUTES = 'havdalah_minutes_after_sundown'
CANDLE_LIGHT_MINUTES = 'candle_lighting_minutes_before_sunset'

HAVDALAH_DEFAULT = 42
CANDLE_LIGHT_DEFAULT = 30
SCAN_INTERVAL = datetime.timedelta(seconds=60)

SHABBAT_START = 'shabbat_start'
SHABBAT_END = 'shabbat_end'
PARASHAT = 'parashat'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Inclusive(CONF_LATITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates',
'Latitude and longitude must exist together'): cv.longitude,
    vol.Optional(CONF_TIME_ZONE): cv.time_zone,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(HAVDALAH_MINUTES, default=HAVDALAH_DEFAULT): int,
    vol.Optional(CANDLE_LIGHT_MINUTES, default=CANDLE_LIGHT_DEFAULT): int,
    vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    havdalah = config.get(HAVDALAH_MINUTES)
    candle_light = config.get(CANDLE_LIGHT_MINUTES)
    name = config.get(CONF_NAME)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)    
    timezone = config.get(CONF_TIME_ZONE, hass.config.time_zone)

    add_devices([ShabbatTimes(hass, latitude, longitude, timezone, name, havdalah, candle_light)])


class ShabbatTimes(Entity):

    def __init__(self, hass, latitude, longitude, timezone, name, havdalah, candle_light):
        self._hass = hass
        self._latitude = latitude
        self._longitude = longitude
        self._timezone = timezone
        self._name = "Shabbat Times " + name
        self._havdalah = havdalah
        self._candle_light = candle_light
        self._state = 'Awaiting Update'
        self._shabbat_start = None
        self._shabbat_end = None
        self._parashat = None

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def device_state_attributes(self):
        return{
            SHABBAT_START: self._shabbat_start,
            SHABBAT_END: self._shabbat_end,
            HAVDALAH_MINUTES: self._havdalah,
            CANDLE_LIGHT_MINUTES: self._candle_light,
            PARASHAT: self._parashat
        }

    @Throttle(SCAN_INTERVAL)
    def update(self):
        self._state = 'Working'
        self.shabbat_start = None
        self._shabbat_end = None
        today = datetime.date.today()
        if (today.weekday() == 5):
            friday = today + datetime.timedelta(-1)
        else:
            friday = today + datetime.timedelta((4-today.weekday()) % 7)

        saturday = friday + datetime.timedelta(+1)

        year = str(friday.year)
        month = str(friday.month)

        hebcal_url = "http://www.hebcal.com/hebcal/?v=1&cfg=json&maj=off&min=off&mod=off&nx=off&s=on&year=" + year + "&month=" + month + "&ss=off&mf=off&c=on&geo=pos&latitude=" + str(self._latitude) + "&longitude=" + str(self._longitude) + "&tzid=" + str(self._timezone) + "&m=" + str(self._havdalah) + "&s=off&i=off&b=" + str(self._candle_light)
        hebcal_response = requests.get(hebcal_url)
        hebcal_json_input = hebcal_response.text
        hebcal_decoded = json.loads(hebcal_json_input)

        if 'error' in hebcal_decoded:
            self._state = hebcal_decoded['error']
            _LOGGER.error(hebcal_decoded['error'])
        else:
            for item in hebcal_decoded['items']:
                if (item['category'] == 'candles'):
                    ret_date = datetime.datetime.strptime(item['date'][0:-6].replace('T',' '), '%Y-%m-%d %H:%M:%S')
                    if (ret_date.date() == friday):
                        self._shabbat_start = ret_date
                elif (item['category'] == 'havdalah'):
                    ret_date = datetime.datetime.strptime(item['date'][0:-6].replace('T',' '), '%Y-%m-%d %H:%M:%S')
                    if (ret_date.date() == saturday):
                        self._shabbat_end = ret_date
                elif (item['category'] == 'parashat'):
                    ret_date = datetime.datetime.strptime(item['date'], '%Y-%m-%d')
                    if (ret_date.date() == saturday):
                        self._parashat = item['title']

            self._state = 'Updated'
