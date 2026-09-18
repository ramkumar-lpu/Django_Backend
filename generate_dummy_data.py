import csv
import random

# Generate a sample of 100 fuel stations across the USA to act as a placeholder
# since the original file was not provided in the environment.

stations = []
states = ["NY", "PA", "OH", "IN", "IL", "IA", "NE", "CO", "UT", "NV", "CA", "TX", "FL", "GA", "VA", "MD", "NJ"]

for i in range(1, 101):
    state = random.choice(states)
    price = round(random.uniform(2.50, 5.50), 3)
    stations.append({
        "OPIS Truckstop ID": str(10000 + i),
        "Truckstop Name": f"Station {i}",
        "Address": f"{i} Main St",
        "City": "Anytown",
        "State": state,
        "Rack ID": str(20000 + i),
        "Retail Price": str(price)
    })

# Add some specific ones for the NY to CA route (I-80ish)
route_states = ["NY", "PA", "OH", "IN", "IL", "IA", "NE", "WY", "UT", "NV", "CA"]
for i, state in enumerate(route_states):
    price = round(random.uniform(2.80, 4.50), 3)
    stations.append({
        "OPIS Truckstop ID": str(50000 + i),
        "Truckstop Name": f"Route 80 Stop {state}",
        "Address": f"100 Highway 80",
        "City": "RouteCity",
        "State": state,
        "Rack ID": str(60000 + i),
        "Retail Price": str(price)
    })

with open('data/fuel-prices-for-be-assessment.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=["OPIS Truckstop ID", "Truckstop Name", "Address", "City", "State", "Rack ID", "Retail Price"])
    writer.writeheader()
    writer.writerows(stations)

print("Generated dummy data/fuel-prices-for-be-assessment.csv")
