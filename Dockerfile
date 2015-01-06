FROM python:3-onbuild
MAINTAINER Paulus Schoutsen <Paulus@PaulusSchoutsen.nl>

VOLUME /config

CMD [ "python", "-m", "homeassistant", "--config", "/config" ]
