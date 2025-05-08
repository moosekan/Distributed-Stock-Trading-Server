import requests
import random
import time

FRONTENDPORT=8091
#host address is identified be frontend as the client container is attached to the network of microservices set up by docker-compose

FRONTENDHOST = "localhost"
# FRONTENDHOST = "34.235.125.182"



#change host address to "localhost" if client is running on native machine 
# FRONTENDHOST = "localhost"


url_get = f"http://{FRONTENDHOST}:{FRONTENDPORT}/stocks/"
url_post = f"http://{FRONTENDHOST}:{FRONTENDPORT}/orders/"
url_getOrderNo = f"http://{FRONTENDHOST}:{FRONTENDPORT}/orders/" # new REST API added...
NUM_REQUESTS = 1000

#this is the threshold for sending trade request from client 
p=random.random()

#create a session and send consecutive request in same session 
with requests.Session() as session:
    for _ in range(NUM_REQUESTS):
        #select a random stock
        stock_name = random.choice(["GameStart", "RottenFishCo", "BoarCo", "MenhirCo","AAPL","AMZN","GOOGL","META","NVDA","NFLX"])
        print(f"\nGive details of stock: {stock_name}")
        response = session.get(url_get + stock_name)
        get_data = response.json()
        
        #error handling at client side if lookup request fails due to incorrect GET url
        if "error" in get_data:
            print(get_data)
            break

        print(get_data)
        if get_data["data"]["quantity"] > 0:
            threshold=random.random()
            #with probability p send a trade request
            if threshold <= p:
                # from lab2 stock_name should be same...
                # stock_name = random.choice(["GameStart", "RottenFishCo", "BoarCo", "MenhirCo"])
                stock_quantity = random.randint(0, 10)
                stock_type = random.choice(["buy", "sell"])
                order = {"name":stock_name,"quantity":stock_quantity,"type":stock_type}
                response = session.post(url_post, json=order)
                post_data = response.json()
                print("\n Trade request sent...")
                #instead of printing transaction no. here, printing it in new Get API...
                # print(post_data)

                # new GET API...
                if "data" in post_data:
                    order_number=post_data["data"]["transaction_number"]
                    print(f"Give details of order number: {order_number}")

                    response = session.get(url_getOrderNo + str(order_number))
                    get_data = response.json()
                    print(get_data)
                # in case trade request recieves an error, directly printing it in else part...
                else:
                    print(post_data)


 

session.close()