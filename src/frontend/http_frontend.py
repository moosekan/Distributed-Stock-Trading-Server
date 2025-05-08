from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
from socketserver import ThreadingMixIn
import grpc
import catalog.catalog_pb2 as catalog_pb2
import catalog.catalog_pb2_grpc as catalog_pb2_grpc
import order.order_pb2 as order_pb2
import order.order_pb2_grpc as order_pb2_grpc
from google.protobuf.empty_pb2 import Empty
import os
from collections import OrderedDict
from readerwriterlock import rwlock
import sys
import time 



cache = OrderedDict()
cache_size = 5
lock = rwlock.RWLockFair()
read_lock = lock.gen_rlock()
write_lock = lock.gen_wlock()
    

#Handler class run by each thread
class FrontendServer(BaseHTTPRequestHandler):

    #Need to specify HTTP/1.1 to support session functionality otherwise defaults to HTTP/1.0
    protocol_version = 'HTTP/1.1'

    #run this method in GET request
    def do_GET(self):

        def handle_get_stock(stockName):

            print("Handling get stock lookup requests")
        

            cache_miss = 0
            is_cache=True
            #to verify persistent socket connections, same port is being reused
            print("Client address:", self.client_address)
            print("Connection:", self.connection)
            print(f"GET [{threading.current_thread().name}] is running to serve {self.client_address}")

            #check if the stock exists in cache 
            with write_lock:
                if is_cache and stockName in cache:
                    print(f"Fetched {stockName} from cache")
                    code = 200
                    response = {"data": {"name": stockName, "price": cache[stockName]["price"], "quantity": cache[stockName]["quantity"]}}
                    #move this stockname to the end as recently used in cache 
                    cache.move_to_end(stockName)
                else:
                    #call catalog microservice
                    cache_miss = 1
            
            if cache_miss:
                print(f"Could not find {stockName} in cache calling catalog microservice\n")

                with grpc.insecure_channel(f'{CATALOG_HOST}:{CATALOG_PORT}') as channel:
                    stub = catalog_pb2_grpc.CatalogServiceStub(channel)
                    lookup_req = catalog_pb2.LookupRequest(stock_name = stockName)
                    lookup_reply = stub.Lookup(lookup_req)

                print(lookup_reply)
                #if incorrect stock name sent
                if lookup_reply.code == 404:
                    code=404
                    response = {
                        "error": {
                            "code": lookup_reply.code,
                            "message": lookup_reply.message
                        }
                    }
                else:
                    #request succeeded
                    code = 200
                    response = {"data": {"name": lookup_reply.name, "price": lookup_reply.price, "quantity": lookup_reply.quantity}}
            
                    #check cache size before adding to cache 
                    with write_lock:
                        if len(cache) == cache_size:
                            #remove the oldest added item
                            cache.popitem(last=False)
                        
                        #add this item to cache for future
                        cache[lookup_reply.name] = {"price": lookup_reply.price, "quantity": lookup_reply.quantity}

            return code, response

        def handle_get_order(transaction_num):

            global leader_id, ORDER_HOST, ORDER_PORT
            print("Handling get order requests")

            try: 
                with read_lock:
                    lid = leader_id
                    host = ORDER_HOST
                    port = ORDER_PORT
                
                with grpc.insecure_channel(f'{host}:{port}') as channel:
                    stub = order_pb2_grpc.OrderServiceStub(channel)
                    details_req = order_pb2.GetOrderDetailsRequest(transaction_num = transaction_num)
                    details_reply = stub.GetOrderDetails(details_req)
            except Exception as e: 
                print(f"(Frontend): Order Leader {lid} not responding, re-electing leader")
                #redo leader election, (also handles notification of replicas about new leader)
                leader_add = find_leader()
                if leader_add is None:
                    print("No Order Replicas are responding, shutting down the system")
                    sys.exit(1)
                
                with write_lock: 
                    leader_id, (ORDER_HOST, ORDER_PORT) = leader_add
                    lid = leader_id
                    host = ORDER_HOST
                    port = ORDER_PORT
                
                try:
                    with grpc.insecure_channel(f'{host}:{port}') as channel:
                        stub = order_pb2_grpc.OrderServiceStub(channel)
                        details_req = order_pb2.GetOrderDetailsRequest(transaction_num = transaction_num)
                        details_reply = stub.GetOrderDetails(details_req)
                except Exception as e2:
                    print(f"(Frontend): New leader {lid} also failed due to {e2}")
                    code = 404
                    response = {
                        "error": {
                            "code": code,
                            "message": "Order service temporarily unavailable"
                        }
                    }
                    return code, response

            if details_reply.code == 404:
                code=404
                response = {
                    "error": {
                        "code": details_reply.code,
                        "message": details_reply.message
                    }
                }
            else:
                #request succeeded
                code = 200
                response = {"data": {"order_num": details_reply.transaction_num, "name": details_reply.name, "type": details_reply.type, "quantity": details_reply.volume_traded}}
        
            return code, response
        

        try:
            if self.path.startswith("/stocks/"):
                stockName=self.path.split("/")[-1]
                code, response = handle_get_stock(stockName)
            elif self.path.startswith("/orders/"):
                transaction_num = int(self.path.split("/")[-1])
                code, response = handle_get_order(transaction_num)
            else:
                raise ValueError("Invalid URL path")
            
        except ValueError as e:
            #will be raised when url sent is invalid
            code=404
            response = {
                "error": {
                    "code": code,
                    "message": "Invalid path sent"
                }
            }
            

        #Content length helps clients to know when the server has stopped sending its message
        response = json.dumps(response).encode('utf-8')
        #prepare HTTP headers
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        #send response
        self.wfile.write(response)

    #this method is run in POST request
    def do_POST(self):
        global leader_id, ORDER_HOST, ORDER_PORT
        try:
            if not self.path.startswith("/orders/") :
                raise ValueError("Invalid URL path")
            print(f"POST [{threading.current_thread().name}] is running to serve {self.client_address}")

            #read incoming POST message
            length = int(self.headers.get('content-length'))
            message = self.rfile.read(length).decode('utf-8')
            message = json.loads(message)
            
            stock_name = message["name"]
            order_type = message["type"]
            quantity = message["quantity"]

            #call order microservice

            try:
                with read_lock:
                    lid = leader_id
                    host = ORDER_HOST
                    port = ORDER_PORT

                with grpc.insecure_channel(f'{host}:{port}') as channel:
                    stub = order_pb2_grpc.OrderServiceStub(channel)
                    order_req = order_pb2.OrderRequest(name = stock_name,number_of_items=quantity, type=order_type)
                    order_reply = stub.Order(order_req)
            except Exception as e:
                print(f"(Frontend): Order Leader {lid} not responding, re-electing leader")

                leader_add = find_leader()
                if leader_add is None:
                    print("No Order Replicas are responding, shutting down the system")
                    sys.exit(1)
                
                with write_lock: 
                    leader_id, (ORDER_HOST, ORDER_PORT) = leader_add
                    lid = leader_id
                    host = ORDER_HOST
                    port = ORDER_PORT
                
                try:
                    with grpc.insecure_channel(f'{host}:{port}') as channel:
                        stub = order_pb2_grpc.OrderServiceStub(channel)
                        order_req = order_pb2.OrderRequest(name = stock_name,number_of_items=quantity, type=order_type)
                        order_reply = stub.Order(order_req)
                except Exception as e2:
                    print(f"(Frontend): New leader {lid} also failed due to {e2}")
                    code = 404
                    response = {
                        "error": {
                            "code": code,
                            "message": "Order service temporarily unavailable"
                        }
                    }
            
                    return code, response
            
            if order_reply.code == 404:
                code=404
                response = {
                    "error": {
                        "code": order_reply.code,
                        "message": order_reply.message
                    }
                }
            else:
                code = 200
                response = {"data": {"transaction_number": order_reply.transaction_num}}
        except ValueError as e:
                    code=404
                    response = {
                        "error": {
                            "code": code,
                            "message": "Invalid path sent"
                        }
                    }
        response = json.dumps(response).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_DELETE(self):
        if self.path.startswith("/delete/"):
            stock_name = self.path.split("/")[-1]
            print(f"Deleting {stock_name} from cache \n")

            with write_lock:
                cache.pop(stock_name, None)

            response = json.dumps({"code": 200, "message": "Cache invalidated"}).encode('utf-8')
            code=200

        else:
            response = json.dumps({"code": 404, "message": "Invalid path"}).encode('utf-8')
            code=404
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response)

#when the server exits deamon_threads set true will ensure the thread also exits 
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def find_leader():

    order_services = {}

    def check_health(s_id, order_services):
        host, port = order_services[s_id]

        try:
            with grpc.insecure_channel(f'{host}:{port}') as channel:
                stub = order_pb2_grpc.OrderServiceStub(channel)
                order_reply = stub.Heartbeat(Empty())
                return order_reply.code == 200
        except grpc.RpcError as e:
            print(f"(Frontend): Replica {s_id} unreachable: {e}")
            return False
    
    def notify_replicas(leader_id, order_services):


        for s_id, add in order_services.items():
            host, port = add
            if s_id == leader_id:
                continue
            try:
                with grpc.insecure_channel(f'{host}:{port}') as channel:
                    stub = order_pb2_grpc.OrderServiceStub(channel)
                    notify_req = order_pb2.NotifyReplicaRequest(leader_id=leader_id)
                    stub.NotifyReplica(notify_req)
                    print(f"(Frontend): Notified replica {s_id} about leader {leader_id}")
            except grpc.RpcError as e:
                print(f"(Frontend): Failed to notify replica {s_id}: {e}")


    #order_services = {1: (host_add, port), 2:(host_add, port)}
    for i in range(3):
        service_id = int(os.getenv(f"ORDER_ID_{i+1}", i+1))
        order_services[service_id] = (os.getenv(f"ORDER_HOST_{i+1}", "localhost"), int(os.getenv(f"ORDER_PORT_{i+1}",8093+i)))


    #ping the order service with the highest id number 
    service_ids = sorted(list(order_services.keys()), reverse=True)
    for s_id in service_ids:
        if check_health(s_id, order_services):
            notify_replicas(s_id, order_services)
            return s_id, order_services[s_id]

    #no order replicas are available   
    return None


    

if __name__ == "__main__":

    #get environment variables from os environment created by docker-compose 
    FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", 8091))
    CATALOG_HOST =  os.getenv("CATALOG_HOST", "localhost")
    CATALOG_PORT = int(os.getenv("CATALOG_PORT", 8092))
    leader_add = find_leader()
    
    if leader_add is None:
        print("No Order Replicas are responding, shutting down the system")
        sys.exit(1)
    
    #leader host and port 
    leader_id, (ORDER_HOST, ORDER_PORT) = leader_add
    # print("aaaa", leader_id, ORDER_HOST, ORDER_PORT)
    # ORDER_HOST = os.getenv("ORDER_HOST", "localhost")
    # ORDER_PORT = int(os.getenv("ORDER_PORT", 8093))

    #listen on all interfaces 
    httpd = ThreadedHTTPServer(('0.0.0.0', FRONTEND_PORT),FrontendServer)
    print("Server running ... \n")

    #start the main server which will forward new client connection to a new thread running FrontendServer Handler 
    #FrontendServer handler will handle all request from that client (thread-per-session)
    httpd.serve_forever()

