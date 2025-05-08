#!/bin/bash

# BEGIN AI CODE: ChatGPT 4o. Prompt: Write a script that kills and restarts a specific order service replica based on passed argument.

if [[ -z "$1" ]]; then
  echo "Usage: $0 <ORDER_ID (1|2|3)>"
  exit 1
fi

ORDER_ID=$1
ORDER_PORT=$((8092 + ORDER_ID))

# Kill any process using this port
PIDS=$(lsof -ti tcp:$ORDER_PORT)
if [[ -n "$PIDS" ]]; then
  echo "Crashing Order Replica $ORDER_ID on port $ORDER_PORT (PIDs: $PIDS)"
  for pid in $PIDS; do
    kill -9 "$pid"
  done
  sleep 2
else
  echo "No replica running on port $ORDER_PORT"
fi


# Restart
export ORDER_ID
export ORDER_PORT
export ORDER_REPLICAS="1:localhost:8093,2:localhost:8094,3:localhost:8095"
export CATALOG_HOST="localhost"
export CATALOG_PORT=8092

echo "Restarting Order Replica $ORDER_ID on port $ORDER_PORT"
python -u -m order.order >> "logs/order_${ORDER_ID}.log" 2>&1 &

# END AI CODE: ChatGPT 4o. Prompt: Write a script that kills and restarts a specific order service replica based on passed argument.
