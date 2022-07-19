FROM python:3.9-alpine
    MAINTAINER Savva Surenkov <savva@surenkov.space>

RUN apk update && apk add postgresql13-dev gcc python3-dev

WORKDIR /app
COPY ../ /app

RUN pip install -e .[dev,postgres,filters]
