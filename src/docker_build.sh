#!/bin/bash

NETWORK_NAME="src_mumanet"

echo "Building Docker images of microservices"
docker-compose build

echo "Spinning up the microservices in their containers on network $NETWORK_NAME"
docker-compose up 
