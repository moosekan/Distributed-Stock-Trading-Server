import csv 
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from concurrent import futures
import json
import threading
import catalog.catalog_pb2 as catalog_pb2
import catalog.catalog_pb2_grpc as catalog_pb2_grpc
import grpc
from readerwriterlock import rwlock
import time
import os
import requests

class CatalogServicer(catalog_pb2_grpc.CatalogServiceServicer):
    def __init__(self):
        #use fair lock so don't starve readers and writers, don't priortize anyone 
        self.lock  = rwlock.RWLockFair()
        self.read_lock = self.lock.gen_rlock()
        self.write_lock = self.lock.gen_wlock()
    
    # Returns the stock price and trading volume for a given stock
    def Lookup(self, request, context):
        print(f"[{threading.current_thread().name}] is running")
        print("Lookup Request Received")
        print(request)

        #prevent writes but reads can happen
        with self.read_lock:
            if request.stock_name not in catalog:
                lookup_res = catalog_pb2.LookupResponse(code = 404, message = "stock not found")
            else:
                lookup_res = catalog_pb2.LookupResponse(code = 200, name = request.stock_name, price = catalog[request.stock_name]["price"], quantity = catalog[request.stock_name]["quantity"])

        print(lookup_res)
        return lookup_res
    
    # Updates the inmemory catalog dictionary fields : quantity and volume
    def Trade(self, request, context):
    
        print(f"[{threading.current_thread().name}] is running")
        
        print("Trade Request Received")
        print(request)

        tradeType=request.type
        tradeName=request.name
        no_of_items= request.number_of_items


        with self.write_lock:
            if tradeType == "buy":
                #buy request suceeds only when the requested quantity of stock is less than the quantity of stock in catalog
                if no_of_items <= catalog[tradeName]["quantity"]:
                    catalog[tradeName]["quantity"]-=no_of_items
                    catalog[tradeName]["volume"]+=no_of_items
                else:
                    #not enough stock left to buy
                    return catalog_pb2.TradeResponse(code = 404) 
            else:
                #in case of sell increment both quantity and volume
                catalog[tradeName]["quantity"]+=no_of_items
                catalog[tradeName]["volume"]+=no_of_items
        
        try:
            response = requests.delete(url_delete + tradeName).json()
            print(response)
        except requests.RequestException as e:
            print(f"Cache invalidation failed due to {e}")
        
        return catalog_pb2.TradeResponse(code = 200) 


# BEGIN AI CODE: ChatGPT 4o. Prompt: Write a Python daemon thread that periodically writes a shared catalog dictionary to a CSV file every few seconds.
def write_to_disk(lock):
    while True:
        #write to disk every 1 second using the background thread 
        time.sleep(1)
        with lock.gen_rlock():
            with open('catalog/catalog.csv', mode='w', newline='') as csvfile:
                fieldnames = ['Name', 'Price', 'Quantity', 'Volume']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for name, data in catalog.items():
                    writer.writerow({
                        'Name': name,
                        'Price': data['price'],
                        'Quantity': data['quantity'],
                        'Volume': data['volume']
                    })

            print(f"[{threading.current_thread().name}] catalog written to CSV.")

# END AI CODE: ChatGPT 4o. Prompt: Write a Python daemon thread that periodically writes a shared catalog dictionary to a CSV file every few seconds


# BEGIN AI CODE: ChatGPT 4o. Prompt: Write Python code to read a CSV file with columns Name, Price, Quantity, Volume and convert it into a dictionary catalog with structure: {Name: {"price": float, "quantity": int, "volume": int}}.
def read_from_disk():

    catalog = {}

    with open('catalog/catalog.csv', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            name = row["Name"]
            catalog[name] = {
                "price": float(row["Price"]),
                "quantity": int(row["Quantity"]),
                "volume": int(row["Volume"])
        }
    
    return catalog

 # END AI CODE: ChatGPT 4o. Prompt: Write Python code to read a CSV file with columns Name, Price, Quantity, Volume and convert it into a dictionary catalog with structure: {Name: {"price": float, "quantity": int, "volume": int}}.



if __name__ == "__main__":

    #get the port specificed from the environment specified in docker-compose file
    PORT = int(os.getenv("CATALOG_PORT", 8092))
    FRONTEND_HOST = os.getenv("FRONTEND_HOST", "localhost")
    FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", 8091))
    url_delete = f"http://{FRONTEND_HOST}:{FRONTEND_PORT}/delete/"

    #inmemory dictionary of stocks
    catalog = read_from_disk()

    servicer = CatalogServicer()
    write_to_disk_thread = threading.Thread(target=write_to_disk, args=(servicer.lock,), daemon=True)
    
    # run a separate thread in background to log the current state of catalog to disk
    write_to_disk_thread.start()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=3))
    catalog_pb2_grpc.add_CatalogServiceServicer_to_server(servicer, server)
    server.add_insecure_port(f'[::]:{PORT}')
    server.start()
    print(f"Catalog service running on port {PORT}")
    server.wait_for_termination()
            

        




