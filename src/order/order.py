import csv 
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from concurrent import futures
import threading
import order.order_pb2 as order_pb2
import order.order_pb2_grpc as order_pb2_grpc
import grpc
import catalog.catalog_pb2 as catalog_pb2
import catalog.catalog_pb2_grpc as catalog_pb2_grpc
from readerwriterlock import rwlock
import time
import os 
from dotenv import load_dotenv



class OrderServicer(order_pb2_grpc.OrderServiceServicer):
    def __init__(self, replicas, transaction_num):
        #use fair lock so don't starve readers and writers, don't priortize anyone 
        self.lock  = rwlock.RWLockFair()
        self.read_lock = self.lock.gen_rlock()
        self.write_lock = self.lock.gen_wlock()
        self.order_logs = {}
        self.leader_id = None
        self.transaction_num = transaction_num
        self.replicas = replicas

    
    def Order(self, request, context):
        print(f"[{threading.current_thread().name}] is running")     
        print(f"(Order {SERVICE_ID}): Trade Request Received")
        print(request)
        
        tradeType=request.type
        tradeName=request.name
        no_of_items= request.number_of_items

        # if stock name is wrong
        if tradeName not in ["GameStart", "RottenFishCo", "BoarCo", "MenhirCo","AAPL","AMZN","GOOGL","META","NVDA","NFLX"]:
            return order_pb2.OrderResponse(code = 404, message = "invalid stock name")


        #if type is not buy/sell 
        if tradeType not in ["buy", "sell"]:
            return order_pb2.OrderResponse(code = 404, message = "invalid transaction type")

        #if quantity is negative
        if no_of_items < 0:
            return order_pb2.OrderResponse(code = 404, message = "num stocks traded should be non negative")
        
        #send increment/decrement request to catalog
        with grpc.insecure_channel(f'{CATALOG_HOST}:{CATALOG_PORT}') as channel:
            stub = catalog_pb2_grpc.CatalogServiceStub(channel)
            trade_req = catalog_pb2.TradeRequest(name = tradeName,number_of_items=no_of_items, type=tradeType)
            trade_reply = stub.Trade(trade_req)

        if trade_reply.code == 200:
            with self.write_lock:
                self.transaction_num += 1
                trade_res = order_pb2.OrderResponse(code = 200, transaction_num=self.transaction_num)
                self.order_logs[self.transaction_num] = {
                    "Name": tradeName, 
                    "Type": tradeType, 
                    "VolumeTraded": no_of_items
                }
                # keep a local thread copy of transaction number in this thread so that self.transaction number if changes does not inconsistent trade updates to replicas
                transaction_num = self.transaction_num
            
            #update other replicas about this trade 
            for (rid,host,port) in self.replicas:
                with grpc.insecure_channel(f'{host}:{port}') as channel:
                    stub = order_pb2_grpc.OrderServiceStub(channel)
                    replicate_req = order_pb2.ReplicateOrderRequest(transaction_num = transaction_num, name = tradeName, number_of_items = no_of_items, type = tradeType, leader_id = SERVICE_ID)
                    try:
                        replicate_reply = stub.ReplicateOrder(replicate_req, timeout=2)
                    except grpc.RpcError as e:
                        print(f"[WARN] Failed to replicate to {rid}: {e}")
        else:
            trade_res = order_pb2.OrderResponse(code = 404, message="not enough stocks left to buy")

        # print(trade_res)
        return trade_res
    
    def GetOrderDetails(self, request, context):

        print(f"(Order {SERVICE_ID}): Get Order Details Request receieved")
        transaction_num=request.transaction_num
        with self.read_lock:
            order_details = self.order_logs.get(transaction_num)

        if order_details:
            return order_pb2.GetOrderDetailsResponse(
                code=200,
                transaction_num=transaction_num,
                name=order_details["Name"],
                type=order_details["Type"],
                volume_traded=order_details["VolumeTraded"]
            )
        else:
            return order_pb2.GetOrderDetailsResponse(
                code=404,
                message="Transaction number not found"
            )
        
    def Heartbeat(self, request, context):
        
        print(f"(Order {SERVICE_ID}): Checking heartbeat of order service id {SERVICE_ID}")
        return order_pb2.HeartbeatResponse(code=200)
    
    def NotifyReplica(self, request, context):
        #if this order service got this request then this is not a leader
        with self.write_lock:
            self.leader_id = request.leader_id
        print(f"(Order {SERVICE_ID}): Notified replica with id {SERVICE_ID} of leader with id {self.leader_id}")
        return order_pb2.NotifyReplicaResponse(code=200)

    def ReplicateOrder(self, request, context):
        # if the current order service got this request then it is not a leader
        # write the items to file in disk 
        print(f"(Order {SERVICE_ID}): Received request to replicate order from the leader with id {request.leader_id}")
        with self.write_lock:
            self.order_logs[request.transaction_num] = {
                "Name": request.name,
                "Type": request.type,
                "VolumeTraded": request.number_of_items  # matches proto field name
            }

            self.transaction_num = max(self.transaction_num, request.transaction_num)
            #replica should follow the leader rather than setting its own transaction num
            #self.transaction_num = request.transaction_num is wrong because if older transactions come and later this is the leader it will add numbers 
            # self.transaction_num += 1

        return order_pb2.ReplicateOrderResponse(code=200)
    
    def SyncUp(self, request, context):

        print(f"(Order {SERVICE_ID}): Syncup Request received from {request.service_id}")

        #find all entries after request.transaction_num
        replica_transaction_num = request.transaction_num
        filepath = f"order/order_log_{SERVICE_ID}.csv"

        #BEGIN AI CODE: ChatGPT 4o. Prompt: Return all order log entries with transaction number greater than a given value via gRPC.

        missing_logs = []

        with self.read_lock:
            with open(filepath, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    txn_id = int(row["TransactionNumber"])
                    if txn_id > replica_transaction_num:
                        log_entry = order_pb2.OrderDetails(
                            transaction_num=txn_id,
                            name=row["Name"],
                            type=row["Type"],
                            volume_traded=int(row["VolumeTraded"])
                        )
                        missing_logs.append(log_entry)


        print("received last transaction num", request.transaction_num)
        # print(missing_logs)
        return order_pb2.SyncUpResponse(orders=missing_logs)
    
        #END AI CODE: ChatGPT 4o. Prompt: Return all order log entries with transaction number greater than a given value via gRPC.


        


#BEGIN AI CODE: ChatGPT 4o. Prompt: Read the last transaction number from a CSV file, defaulting to 0 if the file is missing or empty.

def read_from_disk(filepath):


    transaction_num = 0
    with open(filepath, newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if len(rows) == 0:
            return 0
        last_row = rows[-1]
        print(last_row)
        return int(last_row["TransactionNumber"])
    
    return transaction_num

#END AI CODE: ChatGPT 4o. Prompt: Read the last transaction number from a CSV file, defaulting to 0 if the file is missing or empty.


def write_to_disk(lock, filepath, order_logs):

    while True:
        #sleep for 2 mins
        time.sleep(2)
        #only write to disk if order_logs is not empty
        with lock.gen_wlock():
            if order_logs:
                #prevent writing to order_logs when writing to disk
                with open(filepath, mode='a', newline='') as csvfile:
                    fieldnames = ['TransactionNumber', 'Name', 'Type', 'VolumeTraded']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    for num, data in order_logs.items():
                        writer.writerow({
                            'TransactionNumber': num,
                            'Name': data['Name'],
                            'Type': data['Type'],
                            'VolumeTraded': data['VolumeTraded']
                        })

                print(f"[{threading.current_thread().name}] order written to CSV.")
                #clear order_logs so that same entries are not rewritten next time
                order_logs.clear()

def sync_with_replica(lock, replicas, latest_transaction_num):

    sync_done = False

    for (rid, host, port) in replicas:

        with grpc.insecure_channel(f'{host}:{port}') as channel:
            stub = order_pb2_grpc.OrderServiceStub(channel)
            syncup_req = order_pb2.SyncUpRequest(transaction_num = latest_transaction_num, service_id = SERVICE_ID)
            try:
                syncup_reply = stub.SyncUp(syncup_req, timeout=2)
                # print("reply", syncup_reply.orders)
                sync_done = True
            except grpc.RpcError as e:
                print(f"[WARN] Failed to syncup from {rid} due to {e}")

    
    if not sync_done:
        print(f"Sync Up of {SERVICE_ID} failed as no replicas are responding")
    else:
        #suppose the last transaction_num is 38 but before sync up new request come and are logged to the file 
        #but while writing it checks if current transaction > last_transaction due to this entries get rewritten so need to filter entries 
        existing_txns = set()
        filepath = f"order/order_log_{SERVICE_ID}.csv"

        with lock.gen_wlock():
            #not the same as class order logs so no need to acquire lock
            with open(filepath, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    existing_txns.add(int(row["TransactionNumber"]))

            new_orders = []

            for order in syncup_reply.orders:
                if order.transaction_num not in existing_txns:
                    new_orders.append(order)
            
            if new_orders:
                with open(filepath, mode='a', newline='') as csvfile:
                    fieldnames = ['TransactionNumber', 'Name', 'Type', 'VolumeTraded']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    for order in sorted(new_orders, key=lambda x: x.transaction_num):
                        writer.writerow({
                            'TransactionNumber': order.transaction_num,
                            'Name': order.name,
                            'Type': order.type,
                            'VolumeTraded': order.volume_traded
                        })

                print(f"(Order {SERVICE_ID}): Syncup Done and completed writing changes to disk")
            else:
                print(f"(Order {SERVICE_ID}): In Syncup No new entries to write")

if __name__ == "__main__":

    load_dotenv()
    PORT = int(os.getenv("ORDER_PORT", 8093))
    SERVICE_ID = int(os.getenv("ORDER_ID"))

    #order service needs to know about the details of other replicas so that it can call them if this is the leader
    replicas = []
    replicas_env = os.getenv("ORDER_REPLICAS").split(",")
    for replica in replicas_env:
        rid, host, port = replica.split(":")
        rid = int(rid)
        if SERVICE_ID != rid:
            replicas.append((rid, host, port))

    print(f"Replicas of (Order {SERVICE_ID}): are {replicas}")


    #read latest transaction number from file
    transaction_num = read_from_disk(filepath = f"./order/order_log_{SERVICE_ID}.csv")
    print(f"(Order {SERVICE_ID}): This is the starting transaction num: {transaction_num}")
    CATALOG_HOST = os.getenv("CATALOG_HOST", "localhost")
    CATALOG_PORT = int(os.getenv("CATALOG_PORT", 8092))
    # print(transaction_num)
    servicer = OrderServicer(replicas, transaction_num)

    write_to_disk_thread = threading.Thread(target=write_to_disk, args=(servicer.lock,f"order/order_log_{SERVICE_ID}.csv", servicer.order_logs))
    # run a separate thread in background to log the current state of catalog to disk
    write_to_disk_thread.start()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=3))
    order_pb2_grpc.add_OrderServiceServicer_to_server(servicer, server)
    server.add_insecure_port(f'[::]:{PORT}')
    server.start()
    print(f"(Order {SERVICE_ID}): Started")
    time.sleep(3)  # delay before syncing with replicas

    #do sync up after order server has started start a thread to do sync up if needed in case this replica came back from crash 
    print("Starting syncup")
    syncup_thread = threading.Thread(target=sync_with_replica, args = (servicer.lock, replicas, transaction_num))
    syncup_thread.start()
    server.wait_for_termination()



            






