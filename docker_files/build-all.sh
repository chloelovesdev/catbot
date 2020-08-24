#!/bin/bash

docker build -t catbot/java:16-slim catbot-java
docker build -t catbot/node:stretch-slim catbot-node
docker build -t catbot/python:3.7.9-slim catbot-python