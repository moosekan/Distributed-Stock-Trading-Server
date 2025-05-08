#!/bin/bash

#BEGIN AI CODE: ChatGPT 4o. Prompt: Write a bash script to start multiple Python microservices natively with logging, and automatically kill all child processes on Ctrl+C.


# === Kill Previous Microservices ===
echo "[INFO] Cleaning up old Python microservices..."
pkill -f "python -u -m catalog.catalog"
pkill -f "python -u -m order.order"
pkill -f "python -u -m frontend.http_frontend"
sleep 1

# === Setup ===
mkdir -p logs

echo "Starting Stock Bazaar microservices natively..."

# === Track PIDs ===
PIDS=()

# === Trap: Kill all services on Ctrl+C ===
cleanup() {
  echo -e "\n Caught Ctrl+C. Shutting down all services..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null
  done
  wait
  echo " All services terminated."
  exit 0
}
trap cleanup INT

# === 1. Start Catalog Service ===
export CATALOG_PORT=8092
echo " Starting Catalog Service on port $CATALOG_PORT"
python -u -m catalog.catalog > logs/catalog.log 2>&1 &
PIDS+=($!)
sleep 1

# === 2. Start 3 Order Service Replicas ===
echo " Starting Order Service Replicas..."
for i in 1 2 3; do
  export ORDER_ID=$i
  export ORDER_PORT=$((8092 + i))
  export ORDER_REPLICAS="1:localhost:8093,2:localhost:8094,3:localhost:8095"
  export CATALOG_HOST="localhost"
  export CATALOG_PORT=8092
  echo " --> Order Replica $ORDER_ID on port $ORDER_PORT"
  python -u -m order.order > "logs/order_${ORDER_ID}.log" 2>&1 &
  PIDS+=($!)
  sleep 1
done

# === 3. Start Frontend Service ===
export FRONTEND_PORT=8091
export CATALOG_HOST="localhost"
export CATALOG_PORT=8092

export ORDER_ID_1=1
export ORDER_HOST_1="localhost"
export ORDER_PORT_1=8093

export ORDER_ID_2=2
export ORDER_HOST_2="localhost"
export ORDER_PORT_2=8094

export ORDER_ID_3=3
export ORDER_HOST_3="localhost"
export ORDER_PORT_3=8095

echo " Starting Frontend Service on port $FRONTEND_PORT"
python -u -m frontend.http_frontend > logs/frontend.log 2>&1 &
PIDS+=($!)

# === Wait for all processes to finish ===
wait

#END AI CODE: ChatGPT 4o. Prompt: Write a bash script to start multiple Python microservices natively with logging, and automatically kill all child processes on Ctrl+C.