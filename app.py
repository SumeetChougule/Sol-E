from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
from MasterNetwork import *


app = Flask(__name__)
socketio = SocketIO(app)

simulation = None

@app.route('/')
def home():
    return "Hello, this is Sol-E!"




@app.before_first_request
def initialize_simulation():
    global simulation


 # Example demand profile (24 values representing hourly consumption)
demand_profile = [1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2,
                  1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.8, 1.7, 1.6, 1.5, 1.3, 1.2]


# Create a few houses with random average daily consumption
# (id, base_demand, demand_profile)   random.uniform(5, 6)
houses1 = [House(i, 12/24, demand_profile) for i in range(5)]
houses2 = [House(i,  10/24, demand_profile) for i in range(9)]
houses3 = [House(i, 11/24, demand_profile) for i in range(2)]



# Create a ConventionalGrid with certain prices
# (buying_price, selling_price)
conventional_grid = ConventionalGrid(0.03, 0.06)

# Create MiniGrid instances without setting neighboring_grids yet
minigrid1 = MiniGrid(id=1, houses = houses1, avg_sunlight_hours = 8, selling_price = 0.05, num_days_backup = 5, neighboring_grids = [], conventional_grid=conventional_grid, safety_factor = 1.5)

minigrid2 = MiniGrid(id=2, houses = houses2, avg_sunlight_hours = 5, selling_price = 0.05, num_days_backup = 5, neighboring_grids = [], conventional_grid=conventional_grid, safety_factor = 1.5)

minigrid3 = MiniGrid(id=3, houses = houses3, avg_sunlight_hours = 6, selling_price = 0.05, num_days_backup = 5, neighboring_grids = [], conventional_grid=conventional_grid, safety_factor = 1.5)


# Now that all MiniGrid instances are created, set the neighboring grids
minigrid1.neighboring_grids = [minigrid2, minigrid3]
minigrid2.neighboring_grids = [minigrid3, minigrid1]
minigrid3.neighboring_grids = [minigrid1, minigrid2]

# Assign houses to the respective grids and initialize CSVs
for house in houses1:
    house.assign_to_grid(minigrid1)
   # house.initialize_csv()

for house in houses2:
    house.assign_to_grid(minigrid2)
    #house.initialize_csv()

for house in houses3:
    house.assign_to_grid(minigrid3)
    #house.initialize_csv()

# Add the MiniGrids to a list
minigrids = [minigrid1, minigrid2, minigrid3]

# Create a Simulation instance
# (conventional_grid, grids)
simulation = Simulation(conventional_grid, minigrids)
print("Simulation initialized!")


@app.route('/api/initial-state')
def initial_state():
    if simulation is None:
        return "Simulation not initialized", 500
    state = simulation.get_initial_state()
    return jsonify(state)
        


@app.route('/')
def index():
    return render_template('index.html')


@app.errorhandler(500)
def internal_error(error):
    # log error here 
    print("Server Error: ", error)
    return "Internal server error", 500

if __name__ == '__main__':
    socketio.run(app, debug=True)
    