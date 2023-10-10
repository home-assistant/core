"""Constants for the La Marzocco integration."""

DOMAIN = "lamarzocco"

"""Set polling interval at 20s."""
POLLING_INTERVAL = 30

""" Delay to wait before refreshing state"""
UPDATE_DELAY = 3

"""Configuration parameters"""
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_USE_WEBSOCKET = "use_websocket"
CONF_DEFAULT_CLIENT_ID = "7_1xwei9rtkuckso44ks4o8s0c0oc4swowo00wgw0ogsok84kosg"
CONF_DEFAULT_CLIENT_SECRET = "2mgjqpikbfuok8g4s44oo4gsw0ks44okk4kc4kkkko0c8soc8s"

DEFAULT_PORT_CLOUD = 8081

MODEL_GS3_AV = "GS3 AV"
MODEL_GS3_MP = "GS3 MP"
MODEL_LM = "Linea Mini"
MODEL_LMU = "Micra"

DATE_RECEIVED = "date_received"
BREW_ACTIVE = "brew_active"

GLOBAL = "global"
MON = "mon"
TUE = "tue"
WED = "wed"
THU = "thu"
FRI = "fri"
SAT = "sat"
SUN = "sun"

DAYS = [MON, TUE, WED, THU, FRI, SAT, SUN]
