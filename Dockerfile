FROM python:3-onbuild
MAINTAINER Paulus Schoutsen <Paulus@PaulusSchoutsen.nl>

# Temporary fix while waiting for new version of phue to be released
RUN curl https://raw.githubusercontent.com/studioimaginaire/phue/master/phue.py -o phue.py

VOLUME /config

EXPOSE 8123

CMD [ "python", "./start.py", "--docker" ]
