import requests
import random
import multiprocessing
import time
import matplotlib.pyplot as plt
from statistics import mean


def measure_latencies(url_get, url_post, url_getOrder, client_latencies_lookup, client_latencies_trade, client_latencies_order, index, num_req, p):
    with requests.Session() as session:
        lookup_latency,trade_latency,order_latency = [],[],[]

        for i in range(num_req):
            process = multiprocessing.current_process()
            stock_name = random.choice(["GameStart", "RottenFishCo", "BoarCo", "MenhirCo", "AAPL", "AMZN", "GOOGL", "META", "NVDA", "NFLX"])

            # Measure latency for stock lookup request
            start_time = time.time()
            response = session.get(url_get + stock_name)
            end_time = time.time()
            latency = (end_time - start_time) * 1000 
            lookup_latency.append(latency)

            get_data = response.json()
            if "error" in get_data:
                continue

            if get_data["data"]["quantity"] > 0 and random.random() < p:
                order = {
                    "name": stock_name,
                    "quantity": random.randint(1, 10),
                    "type": random.choice(["buy", "sell"])
                }
                # trade request latency
                start_time = time.time()
                post_response = session.post(url_post, json=order)
                end_time = time.time()
                post_latency = (end_time - start_time) * 1000
                trade_latency.append(post_latency)

                post_data = post_response.json()
                if "data" in post_data:
                    order_number = post_data["data"]["transaction_number"]

                    # orders details latency
                    start_time = time.time()
                    order_response = session.get(url_getOrder + str(order_number))
                    end_time = time.time()
                    latency3 = (end_time - start_time) * 1000
                    order_latency.append(latency3)

        client_latencies_lookup[index] = mean(lookup_latency) if lookup_latency else 0
        client_latencies_trade[index] = mean(trade_latency) if trade_latency else 0
        client_latencies_order[index] = mean(order_latency) if order_latency else 0

    session.close()


if __name__ == "__main__":
    PORT = 8091
    HOST = "107.22.138.66"
    NUM_REQUESTS = 100
    NUM_CLIENTS = 5
    PROBABILITIES = [0.0, 0.2, 0.4, 0.6, 0.8]

    url_get = f"http://{HOST}:{PORT}/stocks/"
    url_post = f"http://{HOST}:{PORT}/orders/"
    url_getOrder = f"http://{HOST}:{PORT}/orders/"

    avgLookup_latencies = []
    avgTrade_latencies = []
    avgOrder_latencies = []

    for p in PROBABILITIES:
        print(f"\nProbability = {p}")
        manager = multiprocessing.Manager()
        latencies_lookup = manager.list([0] * NUM_CLIENTS)
        latencies_trade = manager.list([0] * NUM_CLIENTS)
        latencies_order = manager.list([0] * NUM_CLIENTS)

        processes = []
        for i in range(NUM_CLIENTS):
            p_worker = multiprocessing.Process(
                target=measure_latencies,
                args=(url_get, url_post, url_getOrder,
                      latencies_lookup, latencies_trade,latencies_order,i, NUM_REQUESTS, p),  daemon=True 
            )
            processes.append(p_worker)

        for p_worker in processes:
            p_worker.start()
        for p_worker in processes:
            p_worker.join()

        avgLookup_latencies.append(mean(latencies_lookup))
        avgTrade_latencies.append(mean(latencies_trade))
        avgOrder_latencies.append(mean(latencies_order))

    # Plotting the trends
    probabilities_percent = [int(p * 100) for p in PROBABILITIES]
    plt.figure(figsize=(10, 6))
    plt.plot(probabilities_percent, avgLookup_latencies, marker='o', label='Lookup Latency (ms)')
    plt.plot(probabilities_percent, avgTrade_latencies, marker='s', label='Trade Latency (ms)')
    plt.plot(probabilities_percent, avgOrder_latencies, marker='^', label='Get Order Latency (ms)')
    plt.xlabel("Probability")
    plt.ylabel("Average Latency (ms)")
    plt.title("AWS Latency vs Probability, With Cache")
    plt.legend()
    plt.grid(True)
    plt.savefig("AWS latency_vs_probability_with_cache.png")
    plt.show()
