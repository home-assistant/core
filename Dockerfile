FROM python:3-onbuild
MAINTAINER Paulus Schoutsen <Paulus@PaulusSchoutsen.nl>

RUN apt-get update && apt-get install -y nodejs npm

RUN npm install -g bower vulcanize

# Debian installs nodejs as nodejs instead of node.
RUN ln -sf /usr/bin/nodejs /usr/sbin/node

# RUN ./build_polymer
RUN cd homeassistant/components/http/www_static/polymer && \
    bower install --allow-root && \
    vulcanize -o build.htm home-assistant-main.html

# Temporary fix while waiting for new version of phue to be released
RUN curl https://raw.githubusercontent.com/studioimaginaire/phue/master/phue.py -o phue.py


VOLUME /config

EXPOSE 8123

CMD [ "python", "./start.py", "--docker" ]
