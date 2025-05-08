import requests
import catalog.catalog_pb2 as catalog_pb2
import catalog.catalog_pb2_grpc as catalog_pb2_grpc
import order.order_pb2 as order_pb2
import order.order_pb2_grpc as order_pb2_grpc
import csv
import time
import grpc
import io
import sys
import os


#start the servers again (fresh) before running this script


FRONTENDPORT=8091
FRONTENDHOST = "localhost"
frontend_log = "logs/frontend.log"

CATALOGPORT = 8092
CATALOGHOST = "localhost"
catalog_csv_path = "catalog/catalog.csv"


order_services = {
    1: {
        "host": "locahost",
        "port": 8093, 
        "csv_path": "order/order_log_1.csv"
    }, 
    2: {
        "host": "locahost",
        "port": 8094, 
        "csv_path": "order/order_log_2.csv"
    },
    3: {
        "host": "locahost",
        "port": 8095, 
        "csv_path": "order/order_log_3.csv"
    }

}


#testing catalog 

def test_lookup_valid():
    stock_name = "GameStart"

    with grpc.insecure_channel(f"{CATALOGHOST}:{CATALOGPORT}") as channel:
        stub = catalog_pb2_grpc.CatalogServiceStub(channel)
        request = catalog_pb2.LookupRequest(stock_name=stock_name)
        response = stub.Lookup(request)

    assert response.code == 200
    assert response.name == stock_name

    with open(catalog_csv_path, newline="") as f:
        reader = csv.DictReader(f)
        catalog_data = {row["Name"]: row for row in reader}

    assert stock_name in catalog_data

    csv_entry = catalog_data[stock_name]
    csv_price = float(csv_entry["Price"])
    csv_quantity = int(csv_entry["Quantity"])

    assert abs(response.price - csv_price) < 1e-5
    assert response.quantity == csv_quantity

def test_lookup_invalid():
    with grpc.insecure_channel(f"{CATALOGHOST}:{CATALOGPORT}") as channel:
        stub = catalog_pb2_grpc.CatalogServiceStub(channel)
        request = catalog_pb2.LookupRequest(stock_name="WrongName")
        response = stub.Lookup(request)
        assert response.code == 404
        assert response.message == "stock not found"


def test_trade_buy_valid():

    stock = "GameStart"
    buy_amount = 1

    with open(catalog_csv_path, newline='') as f:
        reader = csv.DictReader(f)
        catalog_data = {row["Name"]: row for row in reader}

    old_quantity = int(catalog_data[stock]["Quantity"])
    old_volume = int(catalog_data[stock]["Volume"])

    with grpc.insecure_channel(f"{CATALOGHOST}:{CATALOGPORT}") as channel:
        stub = catalog_pb2_grpc.CatalogServiceStub(channel)
        trade_req = catalog_pb2.TradeRequest(name=stock, type="buy", number_of_items=buy_amount)
        trade_res = stub.Trade(trade_req)

    assert trade_res.code == 200

    time.sleep(1.5)

    with open(catalog_csv_path, newline='') as f:
        reader = csv.DictReader(f)
        updated = {row["Name"]: row for row in reader}

    new_quantity = int(updated[stock]["Quantity"])
    new_volume = int(updated[stock]["Volume"])

    assert new_quantity == old_quantity - buy_amount
    assert new_volume == old_volume + buy_amount

def test_trade_buy_invalid():
    stock = "GameStart"
    excessive_quantity = 1000000  

    with grpc.insecure_channel(f"{CATALOGHOST}:{CATALOGPORT}") as channel:
        stub = catalog_pb2_grpc.CatalogServiceStub(channel)
        trade_req = catalog_pb2.TradeRequest(name=stock, type="buy", number_of_items=excessive_quantity)
        trade_res = stub.Trade(trade_req)

    assert trade_res.code == 404

def test_trade_sell_valid():
    stock = "GameStart"
    sell_amount = 2

    with open(catalog_csv_path, newline="") as f:
        reader = csv.DictReader(f)
        catalog_data = {row["Name"]: row for row in reader}

    old_quantity = int(catalog_data[stock]["Quantity"])
    old_volume = int(catalog_data[stock]["Volume"])

    with grpc.insecure_channel(f"{CATALOGHOST}:{CATALOGPORT}") as channel:
        stub = catalog_pb2_grpc.CatalogServiceStub(channel)
        trade_req = catalog_pb2.TradeRequest(name=stock, type="sell", number_of_items=sell_amount)
        trade_res = stub.Trade(trade_req)

    assert trade_res.code == 200

    time.sleep(1.5)  # wait for async write

    with open(catalog_csv_path, newline="") as f:
        reader = csv.DictReader(f)
        updated = {row["Name"]: row for row in reader}

    new_quantity = int(updated[stock]["Quantity"])
    new_volume = int(updated[stock]["Volume"])

    assert new_quantity == old_quantity + sell_amount
    assert new_volume == old_volume + sell_amount



#Testing Frontend 


def test_frontend_lookup_valid():
    stock = "GameStart"
    response = requests.get(f"http://{FRONTENDHOST}:{FRONTENDPORT}/stocks/{stock}")

    assert response.status_code == 200
    json_data = response.json()
    assert "data" in json_data
    assert json_data["data"]["name"] == stock
    assert isinstance(json_data["data"]["price"], float)
    assert isinstance(json_data["data"]["quantity"], int)


def test_frontend_lookup_invalid():
    stock = "WrongName"
    response = requests.get(f"http://{FRONTENDHOST}:{FRONTENDPORT}/stocks/{stock}")

    assert response.status_code == 404
    json_data = response.json()
    assert "error" in json_data


#tested cache hit, miss, invalidation
def test_frontend_cache_hit():
    stock = "AMZN"

    #delete entry from cache first
    requests.delete(f"http://{FRONTENDHOST}:{FRONTENDPORT}/delete/{stock}")

    # cachemiss should happen now
    requests.get(f"http://{FRONTENDHOST}:{FRONTENDPORT}/stocks/{stock}")
    time.sleep(0.5) 
  

    requests.get(f"http://{FRONTENDHOST}:{FRONTENDPORT}/stocks/{stock}")
    time.sleep(0.5)

    with open(frontend_log, "r", encoding="utf-8") as f:
        logs = f.read()

    #for the cache miss in the first time    
    assert f"Could not find {stock} in cache calling catalog microservice" in logs  
    #next time same call should fetch from cache
    assert f"Fetched {stock} from cache" in logs



#test lru cache eviction
def test_frontend_cache_eviction():

    stocks = ["AAPL", "AMZN", "GOOGL", "META", "NVDA", "NFLX"]

    for stock in stocks:
        requests.delete(f"http://{FRONTENDHOST}:{FRONTENDPORT}/delete/{stock}")

    #cache size is 5, add the first five stocks to the cache
    for stock in stocks[:5]:
        requests.get(f"http://{FRONTENDHOST}:{FRONTENDPORT}/stocks/{stock}")
        time.sleep(0.1)

    
    # get 6th stock to evict the first stock 
    requests.get(f"http://{FRONTENDHOST}:{FRONTENDPORT}/stocks/{stocks[5]}")
    time.sleep(0.1)

    # this is should cause cache miss now as the first stock got evicted
    requests.get(f"http://{FRONTENDHOST}:{FRONTENDPORT}/stocks/{stocks[0]}")
    time.sleep(0.5)

    with open(frontend_log, "r", encoding="utf-8") as f:
        logs = f.read()

    #causes eviction
    assert f"Could not find {stocks[5]} in cache calling catalog microservice" in logs
    #confirms eviction
    assert f"Could not find {stocks[0]} in cache calling catalog microservice" in logs


def test_get_wrong_stockname():
    get_url = f"http://{FRONTENDHOST}:{FRONTENDPORT}/stocks/"
    response = requests.get(f"{get_url}WrongName")
    json_data = response.json()
    assert "error" in json_data
    assert json_data["error"]["message"] == "stock not found"


def test_post():
    post_url = f"http://{FRONTENDHOST}:{FRONTENDPORT}/orders/"
    order = {"name": "RottenFishCo", "quantity": 1,"type": "sell" }
    response = requests.post(post_url, json=order)
    assert response.status_code == 200
    json_data = response.json()
    assert "data" in json_data
    assert isinstance(json_data["data"]["transaction_number"], int)

def test_post_invalid_url():
    post_invalid_url = f"http://{FRONTENDHOST}:{FRONTENDPORT}/orders_Wrong/"
    order = {"name": "RottenFishCo", "quantity": 1,"type": "sell" }
    response = requests.post(post_invalid_url,json=order)
    assert response.status_code == 404
    json_data = response.json()
    assert "error" in json_data
    assert json_data["error"]["message"] == "Invalid path sent"

def test_post_wrong_stockname():

    post_url = f"http://{FRONTENDHOST}:{FRONTENDPORT}/orders/"
    order = {"name": "WrongRottenFishCo", "quantity": 1,"type": "sell" }
    response = requests.post(post_url,json=order)
    assert response.status_code == 404
    json_data = response.json()
    assert "error" in json_data
    assert json_data["error"]["message"] == "invalid stock name"

def test_post_wrong_type():
    post_url = f"http://{FRONTENDHOST}:{FRONTENDPORT}/orders/"
    order = {"name": "BoarCo", "quantity": 1,"type": "Wrongsell" }
    response = requests.post(post_url,json=order)
    assert response.status_code == 404
    json_data = response.json()
    assert "error" in json_data
    assert json_data["error"]["message"] == "invalid transaction type"

def test_post_negative_quantity():
    post_url = f"http://{FRONTENDHOST}:{FRONTENDPORT}/orders/"
    order = {"name": "MenhirCo", "quantity": -100,"type": "sell" }
    response = requests.post(post_url,json=order)
    assert response.status_code == 404
    json_data = response.json()
    assert "error" in json_data
    assert json_data["error"]["message"] == "num stocks traded should be non negative"

def test_post_large_quantity():
    post_url = f"http://{FRONTENDHOST}:{FRONTENDPORT}/orders/"
    order = {"name": "MenhirCo", "quantity": 999999999,"type": "buy" }
    response = requests.post(post_url,json=order)
    assert response.status_code == 404
    json_data = response.json()
    assert "error" in json_data
    assert json_data["error"]["message"] == "not enough stocks left to buy"

def test_post_transaction_increments():
    post_url = f"http://{FRONTENDHOST}:{FRONTENDPORT}/orders/"
    order = {"name": "RottenFishCo", "quantity": 1, "type": "sell"}

    response1 = requests.post(post_url, json=order)
    json_data1 = response1.json()
    transaction_number1 = json_data1["data"]["transaction_number"]

    response2 = requests.post(post_url, json=order)
    json_data2 = response2.json()
    transaction_number2 = json_data2["data"]["transaction_number"]

    # check if transaction number is getting incremented
    assert transaction_number2 > transaction_number1


def test_get_order_valid():
    post_url = f"http://{FRONTENDHOST}:{FRONTENDPORT}/orders/"
    order = {"name": "RottenFishCo", "quantity": 1, "type": "sell"}

    post_response = requests.post(post_url, json=order)
    assert post_response.status_code == 200
    post_data = post_response.json()
    txn_id = post_data["data"]["transaction_number"]

    get_url = f"http://{FRONTENDHOST}:{FRONTENDPORT}/orders/{txn_id}"
    get_response = requests.get(get_url)
    assert get_response.status_code == 200

    get_data = get_response.json()
    assert "data" in get_data
    assert get_data["data"]["name"] == "RottenFishCo"
    assert get_data["data"]["type"] == "sell"
    assert get_data["data"]["quantity"] == 1



#test order services 

def test_leader_logs_trade_replicates_followers():

    def read_csv(path):
        with open(path, newline="") as f:
            return list(csv.DictReader(f))
    
    post_url = f"http://{FRONTENDHOST}:{FRONTENDPORT}/orders/"
    order = {"name": "GameStart", "quantity": 1, "type": "sell"}


    response = requests.post(post_url, json=order)
    assert response.status_code == 200
    transaction_num = response.json()["data"]["transaction_number"]

    time.sleep(3)

    after_csvs = {rid: read_csv(address["csv_path"]) for rid, address in order_services.items()}

    is_present = []
    for rid in order_services:
        if any(int(entry["TransactionNumber"]) == transaction_num for entry in after_csvs[rid]):
            is_present.append(rid)

    assert len(is_present) == 3

def test_order_csvs_same():

    time.sleep(1)

    def read_csv(path):
        with open(path, newline="") as f:
            return list(csv.DictReader(f))

    csvs = {rid: read_csv(address["csv_path"]) for rid, address in order_services.items()}

    golden_csv = csvs[1]

    for rid, csv_replica in csvs.items():
        assert csv_replica == golden_csv


def test_replica_sync_after_crash():

    rid = 2
    csv_path = f"order/order_log_{rid}.csv"

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        transaction_before = {int(row["TransactionNumber"]) for row in reader}

    os.system(f"./simulate_crashes.sh {rid}")

    order = {"name": "GameStart", "quantity": 1, "type": "sell"}
    post_url = f"http://localhost:8091/orders/"
    response = requests.post(post_url, json=order)
    assert response.status_code == 200
    new_transaction = response.json()["data"]["transaction_number"]

    time.sleep(5)

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        transaction_nums = {int(row["TransactionNumber"]) for row in rows}

    assert new_transaction in transaction_nums

    matched = [row for row in rows if int(row["TransactionNumber"]) == new_transaction]
    assert len(matched) == 1
    txn = matched[0]
    assert txn["Name"] == "GameStart"
    assert txn["Type"] == "sell"
    assert int(txn["VolumeTraded"]) == 1


def test_leader_crash_and_recovery():

    order = {"name": "GameStart", "quantity": 1, "type": "sell"}
    post_url = f"http://localhost:8091/orders/"
    response = requests.post(post_url, json=order)
    assert response.status_code == 200
    transaction_number_before = response.json()["data"]["transaction_number"]

    os.system("./simulate_crashes.sh 3")

    #this trade likely invokes new leader which should be 2 
    order2 = {"name": "GameStart", "quantity": 2, "type": "sell"}
    response2 = requests.post(post_url, json=order2)
    assert response2.status_code == 200
    transaction_number_after = response2.json()["data"]["transaction_number"]
    assert transaction_number_after > transaction_number_before

    time.sleep(4)

    #check if the transaction appears in the crashed replica 3
    for replica_id in [1, 3]:
        log_path = f"order/order_log_{replica_id}.csv"
        with open(log_path, newline="") as f:
            reader = csv.DictReader(f)
            transaction_numbers = {int(row["TransactionNumber"]) for row in reader}
        assert transaction_number_after in transaction_numbers

