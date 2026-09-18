"""
Fuel Stop Optimization Service
===============================
Implements a cost-aware greedy algorithm to minimize total fuel expenditure
while ensuring the vehicle can reach the destination.

Algorithm: "Cheapest-Forward" Strategy
--------------------------------------
At each decision point (start or fuel station), the algorithm:

1. If the destination is reachable with current fuel → drive directly (no purchase).
2. Look ahead at all reachable stations within current fuel range.
3. If a station with price <= current station's price exists ahead → buy just
   enough fuel to reach it (why buy expensive fuel when cheap fuel is ahead?).
4. If NO cheaper station exists ahead within range → fill the tank completely
   at the current (cheapest available) station, then drive to the cheapest
   reachable station to continue the journey.

This is a well-known variant of the "optimal refueling" greedy strategy.
It is provably optimal for the single-vehicle, fixed-route fueling problem
when the route is a simple path with known station positions and prices.

Vehicle assumptions:
- max_range_miles: Maximum distance on a full tank (default 500)
- mpg: Miles per gallon (default 10)
- Initial condition: tank is full (max_range_miles / mpg gallons)
- The initial full tank is NOT counted as purchased fuel
"""


class OptimizationService:

    @staticmethod
    def calculate_optimal_stops(
        route_distance_miles: float,
        stations: list,
        max_range_miles: float = 500.0,
        mpg: float = 10.0,
    ) -> dict:
        """
        Calculate optimal fuel stops to minimize total fuel cost.

        Args:
            route_distance_miles: Total route distance in miles.
            stations: List of dicts, each with at least:
                - 'station_id': str
                - 'distance_from_start': float (miles along route)
                - 'price': float (price per gallon)
                Any additional keys are preserved in the output.
            max_range_miles: Vehicle max range on full tank.
            mpg: Vehicle fuel efficiency (miles per gallon).

        Returns:
            dict with keys:
                - 'fuel_stops': list of stop dicts with purchase info
                - 'total_cost': float
                - 'total_purchased_gallons': float

        Raises:
            Exception: If the destination cannot be reached.
        """
        tank_capacity = max_range_miles / mpg  # gallons

        # Edge case: zero or negative distance
        if route_distance_miles <= 0:
            return {
                'fuel_stops': [],
                'total_cost': 0.0,
                'total_purchased_gallons': 0.0,
            }

        # Sort and filter stations strictly between start and destination
        valid = sorted(
            [s for s in stations if 0 < s['distance_from_start'] < route_distance_miles],
            key=lambda s: s['distance_from_start'],
        )

        # Build node list: START → stations → FINISH
        # START has infinite cheapness (price=0, type='start') so we never "buy" there
        # FINISH has price=0 so it's always treated as "cheaper ahead" target
        nodes = []
        nodes.append({
            '_type': 'start',
            '_idx': 0,
            'station_id': '__START__',
            'distance_from_start': 0.0,
            'price': float('inf'),  # START: we can't buy here, treat as infinitely expensive
        })

        for i, s in enumerate(valid):
            node = dict(s)  # preserve all original keys
            node['_type'] = 'station'
            node['_idx'] = i + 1
            nodes.append(node)

        nodes.append({
            '_type': 'finish',
            '_idx': len(nodes),
            'station_id': '__FINISH__',
            'distance_from_start': float(route_distance_miles),
            'price': 0.0,  # FINISH: always cheapest, so we never overshoot buying
        })

        # Simulation state
        current_fuel = tank_capacity  # start with a full tank
        current_idx = 0
        fuel_stops = []
        total_cost = 0.0
        total_purchased = 0.0

        while current_idx < len(nodes) - 1:
            current = nodes[current_idx]
            current_dist = current['distance_from_start']
            current_price = current['price']
            fuel_range = current_fuel * mpg  # how far we can drive right now

            # Can we reach the finish directly?
            dist_to_finish = nodes[-1]['distance_from_start'] - current_dist
            if fuel_range >= dist_to_finish:
                # Drive to finish, no purchase needed
                current_fuel -= dist_to_finish / mpg
                break

            # Find all nodes reachable with FULL tank (not just current fuel)
            # We need to know what's within max_range to decide how much to buy
            reachable = []
            for j in range(current_idx + 1, len(nodes)):
                gap = nodes[j]['distance_from_start'] - current_dist
                if gap <= max_range_miles:
                    reachable.append(j)
                else:
                    break

            if not reachable:
                raise Exception(
                    "Destination cannot be reached with the available fuel stations."
                )

            # Strategy: look for the FIRST node ahead that is cheaper or equal
            # (in order of distance). If found, buy just enough to reach it.
            cheaper_ahead_idx = None
            for j in reachable:
                if nodes[j]['price'] <= current_price:
                    cheaper_ahead_idx = j
                    break

            if cheaper_ahead_idx is not None:
                # Buy just enough fuel to reach the cheaper station
                target = nodes[cheaper_ahead_idx]
                gap = target['distance_from_start'] - current_dist
                fuel_needed = gap / mpg
                shortfall = fuel_needed - current_fuel

                if shortfall > 0 and current['_type'] == 'station':
                    cost = round(shortfall * current_price, 2)
                    total_cost += cost
                    total_purchased += shortfall
                    stop = _make_stop(current, shortfall, cost)
                    fuel_stops.append(stop)
                    current_fuel += shortfall

                # Drive to that station
                current_fuel -= gap / mpg
                current_idx = cheaper_ahead_idx

            else:
                # No cheaper station ahead within max range.
                # Fill up completely here (if we're at a station), then go to the
                # cheapest reachable node.
                if current['_type'] == 'station':
                    buy_amount = tank_capacity - current_fuel
                    if buy_amount > 0:
                        cost = round(buy_amount * current_price, 2)
                        total_cost += cost
                        total_purchased += buy_amount
                        stop = _make_stop(current, buy_amount, cost)
                        fuel_stops.append(stop)
                        current_fuel = tank_capacity

                # Drive to the cheapest reachable node
                # (among nodes we can actually reach with current fuel)
                actually_reachable = [
                    j for j in reachable
                    if (nodes[j]['distance_from_start'] - current_dist) <= current_fuel * mpg
                ]

                if not actually_reachable:
                    raise Exception(
                        "Destination cannot be reached with the available fuel stations."
                    )

                # Pick the cheapest among actually reachable
                best_j = min(actually_reachable, key=lambda j: nodes[j]['price'])
                target = nodes[best_j]
                gap = target['distance_from_start'] - current_dist
                current_fuel -= gap / mpg
                current_idx = best_j

        return {
            'fuel_stops': fuel_stops,
            'total_cost': round(total_cost, 2),
            'total_purchased_gallons': round(total_purchased, 2),
        }


def _make_stop(node: dict, gallons: float, cost: float) -> dict:
    """Build a fuel stop record from a node, preserving original station data."""
    # Copy all keys except internal ones
    stop = {k: v for k, v in node.items() if not k.startswith('_')}
    stop['gallons_purchased'] = round(gallons, 2)
    stop['cost'] = round(cost, 2)
    return stop
