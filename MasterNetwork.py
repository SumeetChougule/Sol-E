import numpy as np
import csv
from datetime import datetime
import random
import os
import pandas as pd




# Generate synthetic sunlight intensity data
hours = np.arange(0, 24, 1)  # 24 hours
avg_sunlight_intensity = 0.5  # This can be between 0 and 1
sunlight_intensity = avg_sunlight_intensity + 0.5 * np.sin((hours - 6) * np.pi / 12)



class SolarPV:
    def __init__(self, capacity):
        self.capacity = capacity  # Capacity in kW
        self.total_energy_generated = 0
        
    def generate_energy(self, hours):
        # Assuming significant energy is generated only between 9 am and 5 pm
        if 9 <= hours % 24 < 17:
            # Energy in kWh generated in one hour
            # Generate a random amount of energy between 50% and 100% of the capacity
            energy = self.capacity * random.uniform(0.7, 0.95)
            self.total_energy_generated += energy
            return energy
        else:
            # No energy generated outside daylight hours
            return 0    
   

    def get_total_energy_generated(self):
        return self.total_energy_generated



    

class Battery:
    def __init__(self, capacity, initial_level_kWh = 0, degradation_rate=0.1):
        self.capacity = capacity
        self.level = initial_level_kWh
        self.degradation_rate = degradation_rate

    def store(self, energy):
        # Calculate the excess energy that cannot be stored
        can_store = self.capacity - self.level
        stored_energy = min(energy, can_store)
        # Update the level of the battery
        self.level += stored_energy
        # Return the excess energy that could not be stored
        return energy - stored_energy
    
    def draw(self, energy):
        # Check if the requested energy is available in the battery
        can_draw = min(energy, self.level)
        # Update the level of the battery
        self.level -= can_draw
        # Return the energy drawn from the battery
        return can_draw


    def get_level(self):
        """
        Get the current level of the battery in kWh
        """
        return self.level

    def get_state_of_charge(self):
        """
        Get the state of charge of the battery in percentage
        """
        return max((self.level / self.capacity) * 100, 0)

    def degrade(self):
        """
        A simple linear degradation model
        """
        self.capacity *= (1 - self.degradation_rate)

        
        
        
class House:
    def __init__(self, id, base_demand, demand_profile):
        # Check that demand_profile is a list with 24 elements
        if len(demand_profile) != 24:
            raise ValueError("demand_profile should have 24 values representing hourly consumption.")
        
        self.id = id
        self.base_demand = base_demand
        self.current_demand = self.base_demand
        self.demand_profile = demand_profile
        self.unmet_demand = 0
        self.grid = None
        self.cost = 0
        self.simulation_time = 0
        self.supplied_energy = 0
        self.log = []  # A log to keep track of various details
        self.energy_source = None # This should be updated when energy is supplied

    def assign_to_grid(self, grid):
        self.grid = grid

    def consume_energy(self, hours):
        self.current_demand = self.base_demand * self.demand_profile[hours % 24]
        self.energy_source = "generation" # setting the source to generation as it is during generation

        if self.grid is not None:
            # energy from ongoing generation
            supplied_energy = self.grid.supply_energy_to_house(self.current_demand) 
            # Ensure that supplied energy is not negative.
            supplied_energy = max(0, supplied_energy)
            # Unmet demand is current demand minus the energy supplied.
            self.unmet_demand = max(self.current_demand - supplied_energy, 0)
            # Update the cost.
            self.cost += supplied_energy * self.grid.selling_price
            
        return self.current_demand

    
    
    def supply_energy(self, amount_supplied, simulation_hour, source = 'mixed'):
        """
        Receive supplied energy.
        
        :param amount_supplied: Amount of energy supplied in kWh.
        """
        # Update unmet demand
        self.unmet_demand = max(self.unmet_demand - amount_supplied, 0)
        
        # Update current demand (reduce it by the supplied amount)
        self.current_demand = max(self.current_demand - amount_supplied, 0)
        
        # Update cost
        self.cost += amount_supplied * self.grid.selling_price
        
        # Keep track of the total energy supplied to the house
        self.supplied_energy += amount_supplied
        
        # Store the source of energy being supplied
        self.energy_source = source
        
        
        # Log the information
        log_entry = {
            'action': 'energy_supplied',
            'amount_supplied': amount_supplied,
            'remaining_unmet_demand': self.unmet_demand,
            'current_demand': self.current_demand,
            'total_cost': self.cost,
            'total_energy_supplied': self.supplied_energy,
            'energy_source': source
        }
        self.log.append(log_entry)

    
    def log_to_csv(self, simulation_hour):
        # Assuming you want to create a unique log file for each grid and house
        if self.grid is not None:
            grid_id = self.grid.id
            house_id = self.id
            file_name = f'house_log_grid_{grid_id}_house_{house_id}.csv'
            file_is_empty = not os.path.isfile(file_name) or os.path.getsize(file_name) == 0

            with open(file_name, 'a', newline='') as f:
                writer = csv.writer(f)

                # Write headers if the file is empty
                if file_is_empty:
                    headers = ['simulation_hour', 'current_demand', 'unmet_demand', 'cost', 'energy_source']
                    writer.writerow(headers)

                # Write the data
                current_demand = round(self.current_demand, 3)
                unmet_demand = round(self.unmet_demand, 3)
                cost = round(self.cost, 3)
                energy_source = self.energy_source
                writer.writerow([simulation_hour, current_demand, unmet_demand, cost, energy_source])


    def step(self, hours):
        self.consume_energy(hours)
        self.log_to_csv(simulation_hour=hours)
        self.simulation_time += 1


        

class ConventionalGrid:
    def __init__(self, buying_price, selling_price):
        self.buying_price = buying_price  # Price at which the grid buys excess energy from mini-grids
        self.selling_price = selling_price  # Price at which the grid sells energy to mini-grids
        self.energy_purchased = 0  # Total energy purchased from mini-grids
        self.energy_sold = 0  # Total energy sold to mini-grids
        self.cgrevenue = 0  # Net revenue earned by the grid

    def buy_energy(self, amount):
        """
        The grid buys excess energy from mini-grids.
        :param amount: Amount of energy in kWh to buy from mini-grids.
        """
        cost = amount * self.buying_price
        self.energy_purchased += amount
        self.cgrevenue -= cost
     #   print(f'Conventional Grid buying {amount} energy for {cost} cost')
        return cost  # Returning the cost for the mini-grid to update its revenue

    def sell_energy(self, amount):
        """
        The grid sells energy to mini-grids when they cannot fulfill their demand.
        :param amount: Amount of energy in kWh to sell to mini-grids.
        """
        cost = amount * self.selling_price
        self.energy_sold += amount
        self.cgrevenue += cost
       # print(f"Conventional Grid selling {amount} energy for {cost} cost.") # Debugging print statement
        return cost  # Returning the cost for the mini-grid to update its expenses
    
    def report(self):
        """
        Generate a report of the transactions with the mini-grids.
        """
        print(f"Energy Purchased from Mini-Grids: {self.energy_purchased} kWh")
        print(f"Energy Sold to Mini-Grids: {self.energy_sold} kWh")
        print(f"Net Revenue: ${self.cgrevenue}")

        
        

class MiniGrid:
    def __init__(self, id, houses, avg_sunlight_hours , selling_price, num_days_backup, neighboring_grids, conventional_grid, safety_factor):
        
         # Check that avg_sunlight_hours is in a reasonable range
        if not (0 <= avg_sunlight_hours <= 24):
            raise ValueError("avg_sunlight_hours should be between 0 and 24.")
        
        # Check that selling_price is positive
        if selling_price <= 0:
            raise ValueError("selling_price should be a positive number.")
        
        # Check that num_days_backup is positive
        if num_days_backup <= 0:
            raise ValueError("num_days_backup should be a positive number.")
        
        # Check that safety_factor is positive
        if safety_factor <= 0:
            raise ValueError("safety_factor should be a positive number.")
        
        
        
        self.id = id
        self.houses = houses
        self.selling_price = selling_price
        self.neighboring_grids = neighboring_grids
        self.conventional_grid = conventional_grid
        self.safety_factor = safety_factor
        self.revenue = 0.0      
        self.total_demand = 0
        self.unmet_demand = 0
        self.grid_transactions = 0
        self.simulation_time = 0
        self.avg_sunlight_hours = avg_sunlight_hours 
        self.internal_transactions_log = []
        self.external_transactions_log = []
        self.log = []
        
        
          # Calculate average daily energy requirement
        self.total_daily_energy_requirement = 0
        for house in houses:
            for hour in range(24):
                self.total_daily_energy_requirement += house.base_demand * house.demand_profile[hour]
        
        # Calculate solar panel capacity (capacity in kW)
        # Using a safety factor to account for days with less sunlight
        self.solar_pv = SolarPV(self.total_daily_energy_requirement * safety_factor / avg_sunlight_hours)        
        
        # Calculate battery capacity
        # It should store enough energy to provide for daily usage, plus some extra for backup
        self.battery = Battery(capacity = self.total_daily_energy_requirement * num_days_backup, initial_level_kWh = 0.5 * self.total_daily_energy_requirement)

        self.total_generation = 0
        self.generation = 0
        
        
        

        # Associate the MiniGrid with the houses
        for house in self.houses:
            house.grid = self

            

    def demand_energy(self, house, demand):
        # In this example, the MiniGrid supplies all the demand to the house if possible.
        # Otherwise, it supplies whatever it can (up to total_generation - total_demand).
        # Note that this is a very simple example and your implementation might be different.

        energy_supplied = min(demand, self.total_generation - self.total_demand)
        self.total_demand += energy_supplied
        return energy_supplied

            
            
    
    def initialize_csv(self, grid_number):
        with open(f'mini_grid_log_{grid_id}.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            headers = ['simulation_hour', 'generation_kWh', 'total_demand_kWh', 'unmet_demand_kWh', 'internal_grid_transactions_kWh', 'external_grid_transactions_kWh', 'revenue_USD', 'battery_level_kWh', 'battery_%']
            writer.writerow(headers)


    
        
            
    def dynamic_selling_price(self, hours):
        # Here you can implement the logic for calculating the dynamic selling price.
        # As a simple example, let's assume the price increases by 10% during peak hours (6 pm - 10 pm)
        if 18 <= hours % 24 <= 22:
            return self.selling_price * 1.1
        else:
            return self.selling_price            
      
    
    


    def supply_energy_to_house(self, amount_needed):
        # Energy supplied from the ongoing generation
        energy_from_generation = min(amount_needed, self.total_generation)
        self.total_generation -= energy_from_generation

        return energy_from_generation

    
    
    
    def step(self, grid_id, hours):
        grid_id = self.id

        # Step 1: Generate Energy
        self.generation = self.solar_pv.generate_energy(hours)
        self.total_generation += self.generation 

        # Distribute the energy amongst houses and calculate total demand
        total_demand = 0
        energy_supplied_to_houses = 0
        for house in self.houses:
            energy_consumed = house.consume_energy(hours)
            total_demand += energy_consumed
            energy_supplied_to_houses += energy_consumed
            

            # Add revenue for energy supplied from ongoing generation
            energy_from_generation = min(self.generation, energy_consumed)
            self.revenue += energy_from_generation * self.selling_price

        # Update total_demand
        self.total_demand = total_demand

        # Calculate surplus or deficit
        energy_balance = self.generation - energy_supplied_to_houses

        # Initialize excess and shortage
        excess = 0
        shortage = 0

        # Step 3: Handle Surplus
        if energy_balance > 0:
            # Store energy in battery up to its capacity
            excess_energy = self.battery.store(energy_balance)
            excess = excess_energy

            # Offer excess energy to neighboring grids
            for ng in self.neighboring_grids:
                if excess <= 0:
                    break
                initial_excess = excess
                excess = ng.accept_energy(excess, from_grid_id=self.id)
                energy_transferred = initial_excess - excess
                if energy_transferred > 0:
                    self.internal_transactions_log.append((ng.id, energy_transferred, 'supply'))
#                    self.internal_transactions_log.append((hours, ng.id, energy_transferred, 'supply'))
                    

            # Sell any remaining excess energy to the conventional grid
            if excess > 0:
                revenue_from_sale = self.conventional_grid.buy_energy(excess)
                self.external_transactions_log.append(('sell', excess, revenue_from_sale))
#                self.external_transactions_log.append((hours, 'sell', excess, revenue_from_sale))
                self.revenue += revenue_from_sale

        # Step 4: Handle Deficit
        elif energy_balance < 0:
            # Calculate the maximum energy that can be drawn from the battery while maintaining 2 days reserve
            min_reserve = 0.0 * self.total_daily_energy_requirement
            max_draw_from_battery = max(0, self.battery.get_level() - min_reserve)

            # Total energy acquired during the deficit
            total_energy_acquired = 0
    
            # Draw from the battery until it hits the 2-day reserve
            if max_draw_from_battery > 0:
                energy_to_draw = min(abs(energy_balance), max_draw_from_battery)
                energy_from_battery = self.battery.draw(energy_to_draw)
                total_energy_acquired += energy_from_battery
                energy_balance += energy_from_battery


            # Request energy from neighboring grids if in deficit
            if energy_balance < 0:
                for ng in self.neighboring_grids:
                    if energy_balance >= 0:
                        break
                    energy_provided = ng.provide_energy(abs(energy_balance), to_grid_id=self.id)
                    total_energy_acquired += energy_provided
                    energy_balance += energy_provided
                    if energy_provided > 0:
                        self.internal_transactions_log.append((ng.id, energy_provided, 'demand'))
#                        self.internal_transactions_log.append((hours, ng.id, energy_provided, 'demand'))


            # Buy energy from the conventional grid if still in deficit
            if energy_balance < 0:
                amount_needed = abs(energy_balance)
                cost_of_energy = self.conventional_grid.sell_energy(amount_needed)
                total_energy_acquired += amount_needed
                # Storing external transaction ('buy', amount, cost)
                self.external_transactions_log.append(('buy', amount_needed, cost_of_energy))
#                self.external_transactions_log.append((hours, 'buy', amount_needed, cost_of_energy))
                self.revenue -= cost_of_energy  # Subtracting the cost from revenue

                
            # Distribute the total_energy_acquired among houses according to their unmet demand
            if total_energy_acquired > 0:
                for house in self.houses:
                    if house.unmet_demand > 0:
                        energy_for_this_house = min(total_energy_acquired, house.unmet_demand)
                        house.supply_energy(energy_for_this_house, simulation_hour = hours)
                        total_energy_acquired -= energy_for_this_house
                        
                        # Add revenue for supplying electricity to the house
                        self.revenue += energy_for_this_house * self.selling_price



        # Update unmet_demand
        self.unmet_demand = shortage

        self.log_to_csv(grid_id, hours)

        # Return excess and shortage as a tuple
        return excess, shortage

        
    
    

    def accept_energy(self, amount, from_grid_id):
        # A method that neighboring grids can use to give excess energy to this grid
        can_accept = max(0, self.battery.capacity - self.battery.level)
        accepted = min(can_accept, amount)
        self.battery.store(accepted)
       
        # Log the transaction
        if accepted > 0:
            self.internal_transactions_log.append((from_grid_id, accepted, 'receive'))

        return amount - accepted
    

        
        
    def provide_energy(self, amount_needed, to_grid_id):
        """
        Provide energy to a neighboring mini-grid.
        :param amount_needed: Amount of energy in kWh needed by the neighboring mini-grid.
        :return: Amount of energy provided in kWh.
        """
        # Calculate the current energy surplus
        current_surplus = self.total_generation - self.total_demand

        # Calculate the maximum energy that can be drawn from the battery while maintaining 2 days reserve
        two_day_reserve = 2 * self.total_daily_energy_requirement
        max_draw_from_battery = max(0, self.battery.get_level() - two_day_reserve)

        # Energy provided from the ongoing generation surplus
        energy_from_generation = 0
        if current_surplus > 0:
            energy_from_generation = min(amount_needed, current_surplus)
            self.total_generation -= energy_from_generation  # Decrease generation as energy is provided
            amount_needed -= energy_from_generation

        # Energy provided from the battery if needed
        energy_from_battery = 0
        if amount_needed > 0 and max_draw_from_battery > 0:
            energy_from_battery = min(amount_needed, max_draw_from_battery)
            self.battery.draw(energy_from_battery)

        # Total energy provided
        total_energy_provided = energy_from_generation + energy_from_battery
        

        # Log the transaction
        if total_energy_provided > 0:
            self.internal_transactions_log.append((to_grid_id, total_energy_provided, 'supply'))


        return total_energy_provided
    
    

    
                
    def log_to_csv(self, grid_id, simulation_hour):
        # Add a log entry to the log list  
        self.log.append({
            'simulation_hour': simulation_hour,
            'generation_kWh': round(self.generation, 3),
            'total_demand_kWh': round(self.total_demand, 3),
            'unmet_demand_kWh': round(self.unmet_demand, 3),
            'internal_grid_transactions_kWh': str([(x[0], round(x[1], 3), x[2]) for x in self.internal_transactions_log]),
            'external_grid_transactions_kWh': str([(x[0], round(x[1], 3), round(x[2], 3)) for x in self.external_transactions_log]),
            'revenue_USD': round(self.revenue, 3),
            'battery_level_kWh': round(self.battery.get_level(), 3),
            'battery_%': round(self.battery.get_state_of_charge(), 2),
        })
        
        # Clear the transaction logs after logging
        self.internal_transactions_log.clear()
        self.external_transactions_log.clear()


    def save_logs(self):
        file_name = f'mini_grid_log_{self.id}.csv'
        
        with open(file_name, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.log[0].keys())
            writer.writeheader()
            writer.writerows(self.log)

            
    
            
        


            
            
class Simulation:
    def __init__(self, conventional_grid, grids):
        self.conventional_grid = conventional_grid
        self.grids = grids
        self.total_generation = 0
        self.total_demand = 0
        self.unmet_demand = 0
        self.total_grid_transactions = 0
        self.revenue = 0
        self.total_client_revenue = 0
        self.log = []
        
        
        # Check that grids is a non-empty list
        if not grids:
            raise ValueError("grids should be a non-empty list.")
        
        

    def step(self, hours):
        total_excess = 0
        total_shortage = 0
        
        # Each grid steps
        for grid_id, grid in enumerate(self.grids):
            # assuming grid.step returns a tuple (excess, shortage)
            excess, shortage = grid.step(grid_id, hours)
            
            total_excess += excess
            total_shortage += shortage
                
        # Load balancing among mini-grids
        if total_excess > 0 and total_shortage > 0:
            energy_transfer = min(total_excess, total_shortage)
            total_excess -= energy_transfer
            total_shortage -= energy_transfer
            
        # Transactions with Conventional Grid
        if total_excess > 0:
            self.conventional_grid.buy_energy(total_excess)
            self.total_grid_transactions += total_excess
        elif total_shortage > 0:
            self.conventional_grid.sell_energy(total_shortage)
            self.total_grid_transactions -= total_shortage
        
        # Log the state of each house
        for grid_id, grid in enumerate(self.grids):
            for house_id, house in enumerate(grid.houses):
                # assuming log_to_csv accepts necessary information for logging
                house.log_to_csv(hours)
        
        
        # Compute total metrics
        self.total_generation = sum(grid.total_generation for grid in self.grids)
        self.total_demand = sum(grid.total_demand for grid in self.grids)
        self.unmet_demand += total_shortage
        self.total_client_revenue = sum(house.cost for grid in self.grids for house in grid.houses)
        self.revenue = sum(grid.revenue for grid in self.grids)

        
        

        # Log the total metrics
        self.log_to_csv(hours)

    
    def log_to_csv(self, simulation_hour):
        # Add a log entry to the log list
        self.log.append({
            'simulation_hour': simulation_hour,
            'total_generation': round(self.total_generation, 3),
            'total_demand': round(self.total_demand, 3),
            'unmet_demand': round(self.unmet_demand, 3),
            'total_grid_transactions': round(self.total_grid_transactions, 3),
            'total_client_expenditure': round(self.total_client_revenue, 3),
            'revenue': round(self.revenue, 3),
        })

    
    def save_logs(self):
        file_name = 'simulation_log.csv'
        
        with open(file_name, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.log[0].keys())
            writer.writeheader()
            writer.writerows(self.log)    
        
        
    

    def simulate_days(self, num_days):
        for day in range(num_days):
            # Loop through 24 hours
            for hour in range(24):
                # Get the sunlight intensity for the current hour
#                weather_factor = sunlight_intensity[hour]
                # Call the step method
                self.step(24 * day + hour)
    
    
    def get_initial_state(self):
        print("Getting initial state...")
        state = []

        for i, grid in enumerate(self.grids):
            # Calculate average consumption for each house in the minigrid
            total_consumption = sum(house.current_demand for house in grid.houses)
            average_consumption = total_consumption / len(grid.houses) if grid.houses else 0

            # Create a dictionary with the data for this grid
            grid_data = {
                "id": i + 1,
                "num_houses": len(grid.houses),
                "average_consumption": round(average_consumption, 3),
                "solar_capacity": round(grid.solar_pv.capacity, 3),
                "battery_capacity": round(grid.battery.capacity, 3),
            }

            # Append the dictionary to the state list
            state.append(grid_data)
        print(state)

        return state
        
        

                
def create_mini_grid(id, conventional_grid, demand_profile):
    # Ask the user for specifics about the mini-grid
    num_houses = int(input(f"How many houses do you want in MiniGrid {id}? "))
    avg_sunlight_hours = float(input(f"Average sunlight hours for MiniGrid {id}? "))
    
    # Create houses for this grid
    avg_demand = float(input(f"Enter average daily consumption for houses in MiniGrid {id} (in kWh): ")) 
    #         House(id, base_demand, demand_profile)   
    houses = [House(i, avg_demand/ 24, demand_profile) for i in range(num_houses)]
    
    minigrid = MiniGrid(
        id=id, houses=houses, avg_sunlight_hours=avg_sunlight_hours,
        selling_price=0.05, num_days_backup=1, neighboring_grids=[],
        conventional_grid=conventional_grid, safety_factor=1.2
    )

    for house in houses:
        house.assign_to_grid(minigrid)

    return minigrid




if __name__ == "__main__":
    
    # Example demand profile (24 values representing hourly consumption)
    demand_profile = [1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2,
                  1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.8, 1.7, 1.6, 1.5, 1.3, 1.2]

    # Create a ConventionalGrid with certain prices
    # (buying_price, selling_price)
    conventional_grid = ConventionalGrid(0.03, 0.06)
    
    # User determines the number of mini-grids
    num_mini_grids = int(input("How many mini grids do you want to simulate? "))
    
    # Create and setup the mini-grids
    minigrids = [create_mini_grid(i+1, conventional_grid, demand_profile) for i in range(num_mini_grids)]
    
    # Setting up neighbors for each mini-grid
    for i, minigrid in enumerate(minigrids):
        minigrid.neighboring_grids = [mg for j, mg in enumerate(minigrids) if j != i]

    # Create a Simulation instance
    simulation = Simulation(conventional_grid, minigrids)

    # Simulate for a certain number of days
    simulation.simulate_days(7)
    
    # Save the logs
    simulation.save_logs()
    for grid in simulation.grids:
        grid.save_logs()

    # Output results
    print(f"Total revenue from selling to houses: ${round(simulation.total_client_revenue, 3)}")
    print(f"Total unmet demand: {round(simulation.unmet_demand, 3)} kWh")
    
    # Output system information
    for i, grid in enumerate(simulation.grids):
        total_consumption = sum(house.current_demand for house in grid.houses)
        average_consumption = total_consumption / len(grid.houses) if grid.houses else 0
        print(f"\nMiniGrid {i + 1}:")
        print(f"\tNumber of houses: {len(grid.houses)}")
        print(f"\tAverage consumption/hour: {round(average_consumption, 3)} kWh")
        print(f"\tSolar capacity: {round(grid.solar_pv.capacity, 3)} kWp")
        print(f"\tBattery capacity: {round(grid.battery.capacity, 3)} kWh")
            
            

        
        
        
        
