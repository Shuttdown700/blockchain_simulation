# -*- coding: utf-8 -*-
"""
Created on Sun Nov  8 19:36:08 2020

@author: shuttdown
"""
import matplotlib.pyplot as plt
from matplotlib import style
import numpy as np
import random
import simpy
style.use('ggplot')

###############################################################################
### Object(s) #################################################################

class Network(object):
    def __init__(self, env, client_IDs, device_IDs, num_nodes):
        self.env = env
        self.clients = client_IDs
        self.devices = device_IDs
        self.num_nodes = num_nodes
        self.node = simpy.Resource(env, capacity = self.num_nodes)
        self.transaction_wait_times = []
        self.current_transactions = []
        self.total_transactions = []
        self.active_blocks = []
    
    def make_transaction(self, client, device, start, recycle_probability = 0):
        if random.random() < recycle_probability:
            return 0
        else:
            yield self.env.timeout(random.uniform(0.1, 0.3)) # time (in seconds) to validate transaction
            end = env.now
            transaction = {"Transaction Num": len(self.total_transactions)+1,
                           "Client": client,
                           "Device": device,
                           "Transaction Value": "gridx",
                           "Transaction Start": start,
                           "Transaction End": end,
                           "Time from Transaction Start to Transaction End": end - start,
                           "Transaction Coverage": 1/self.num_nodes,
                           "Relay Start": float('nan'),
                           "Relay End": float('nan'),
                           "Relay Time": float('nan'),
                           "Time from Transaction Start to Relay End":float('nan'),
                           "Assigned Block": 'nan',
                           "Block Start": float('nan'),
                           "Block End": float('nan'),
                           "Time from Transaction Start to Block End": float('nan'),
                           "Maturity Time": 'nan',
                           "Time from Transaction Start to Maturity": float('nan')}
            return transaction
    
    def relay_transaction(self,c,start):
        yield self.env.timeout(random.uniform(0.01, 0.03)) # time (in seconds) to validate transaction per node
        self.total_transactions[c]['Transaction Coverage'] += (1/self.num_nodes)
        end = env.now
        self.total_transactions[c]['Relay Start'] = start
        self.total_transactions[c]['Relay End'] = end
        self.total_transactions[c]['Relay Time'] = end - start
        self.total_transactions[c]['Time from Transaction Start to Relay End'] = end - self.total_transactions[c]['Transaction Start']
        if self.total_transactions[c]['Transaction Coverage'] > 1:
            self.total_transactions[c]['Transaction Coverage'] = 1
    
    def write_transactions(self, block_index, curr_transactions_indexes, start):
        yield self.env.timeout(random.uniform(0.2, 0.5)) # time (in seconds) to validate transaction per node
        self.active_blocks.append(block_index)
        end = env.now
        for i in range(len(curr_transactions_indexes)):
            self.total_transactions[curr_transactions_indexes[i]]['Assigned Block'] = block_index+1
            self.total_transactions[curr_transactions_indexes[i]]['Block Start'] = start
            self.total_transactions[curr_transactions_indexes[i]]['Block End'] = end
            self.total_transactions[curr_transactions_indexes[i]]['Time from Transaction Start to Block End'] = end - self.total_transactions[curr_transactions_indexes[i]]['Transaction Start']

###############################################################################
### Simulation Functions ######################################################

def generate_devices(num_devices = 500): # determines how many transactions to expect
    return [''.join(str(list(np.random.randint(10, size=8))).strip('[]').split(', ')) for i in range(num_devices)]

def generate_clients(num_clients = 500): # helps validate transaction
    return [''.join(str(list(np.random.randint(10, size=10))).strip('[]').split(', ')) for i in range(num_clients)]

def generate_arrivals(arrival_rate, simulation_length):
    arrivals = [0]
    while True:
        if arrivals[-1] > simulation_length:
            return arrivals[1:-1]
        else:
            arrivals.append(arrivals[-1] + np.random.exponential(arrival_rate))

def generate_block_schedule(interblock_time, simulation_length):
    return [interblock_time*i for i in range(1,int(simulation_length / interblock_time)+1)]

def operate_on_network(env, net, arrivals, block_schedule, maturity_threshold = 6):
    """
    Step 1: see if it is time to write a new block
    Step 2: see if there is a pending transaction to validate
    Step 3: see if there are any validated transaction that need to be relayed to base standard (50%?)
    Step 4: see if there are any validated transactions currently at the initial covergance standard needing to go to 100%
    """   
    if len(net.total_transactions) == 0:
        arrival_index = 0
    else:
        arrival_index = len(net.total_transactions)
    if len(net.active_blocks) == 0:
        block_index = 0
    else:
        block_index = net.active_blocks[-1] + 1
        for i in range(len(net.total_transactions)): # checks if transactions can be be deemed "mature"
            if float(net.total_transactions[i]['Assigned Block']) != 'nan':
                if block_index - float(net.total_transactions[i]['Assigned Block']) >= maturity_threshold and net.total_transactions[i]['Maturity Time'] == 'nan':
                    net.total_transactions[i]['Maturity Time'] = env.now
                    net.total_transactions[i]['Time from Transaction Start to Maturity'] = env.now - net.total_transactions[i]['Transaction Start']
    # Priority 1: Accept arrivals
    if arrival_index < len(arrivals):
        if float(env.now) > float(arrivals[arrival_index]):
            start = arrivals[arrival_index]
            with net.node.request() as request: # step 2 of full node is to accept any new transactions
                yield request
                transaction = yield env.process(net.make_transaction(net.clients[random.randint(0,len(net.clients)-1)],net.devices[random.randint(0,len(net.devices)-1)],start))
                net.total_transactions.append(transaction)
    # Priority 2: Write blocks
    if float(env.now) > float(block_schedule[block_index]): # step 1 of full node is to write blocks
        curr_transactions_indexes = []
        for i in range(len(net.total_transactions)):
            if net.total_transactions[i]['Assigned Block'] == 'nan' and np.random.rand() <= net.total_transactions[i]['Transaction Coverage']:
                curr_transactions_indexes.append(i)
        start = env.now
        with net.node.request() as request:
            yield request
            yield env.process(net.write_transactions(block_index, curr_transactions_indexes, start))
        block_index += 1
    # Priority 3: Relay Transactions
    if len(net.total_transactions) > 0: # step 3 of full node is to relay known validated transactions
        coverages = [t['Transaction Coverage'] for t in net.total_transactions]
        find = False
        for c in range(len(coverages)):
            if coverages[c] < 1:
                start = env.now
                while coverages[c] < 1:
                    coverages = [t['Transaction Coverage'] for t in net.total_transactions]
                    with net.node.request() as request:
                        yield request
                        yield env.process(net.relay_transaction(c,start))
                    find = True
            if find:
                break
    progressive_data.append(net.total_transactions)

def run_network(env, client_IDs, device_ID, num_nodes, arrivals, block_schedule):
    net = Network(env, client_IDs, device_IDs, num_nodes)
    while True:
        yield env.timeout(0.05)  # Wait a bit
        env.process(operate_on_network(env, net, arrivals, block_schedule))

def plot_hist(l,title):
    plt.figure()
    plt.hist(l, color="Black", bins = int(2*len(l)**(1/3)))
    if min(l) > 10:
        plt.xlim(min(l),max(l))
    else:
        plt.xlim(0,max(l))
    plt.xlabel("Time (seconds)")
    plt.ylabel("Frequency")
    plt.title(title)
    plt.show()

##############################################################################
### Execution ################################################################

# progressive_data = []
# simulation_length = 2000 # in seconds
# device_IDs = generate_devices(num_devices = 500)
# client_IDs = generate_clients(num_clients = 500)
# interarrival_times = 1 # seconds per device
# arrival_times = generate_arrivals(interarrival_times,simulation_length*3/4)
# interblock_time = 10 # seconds
# block_schedule = generate_block_schedule(interblock_time, simulation_length) # exponential arrivals
# num_nodes = 50
# env = simpy.Environment()
# env.process(run_network(env, client_IDs, device_IDs, num_nodes, arrival_times, block_schedule))
# env.run(until=simulation_length)
# data = progressive_data[-1]


num_nodes_candidates = [10,25,50,100,200,400,1000]
results = []
for i in range(len(num_nodes_candidates)):
    progressive_data = []
    simulation_length = 2000 # in seconds
    device_IDs = generate_devices(num_devices = 500)
    client_IDs = generate_clients(num_clients = 500)
    interarrival_times = 1 # seconds per device
    arrival_times = generate_arrivals(interarrival_times,simulation_length*3/4)
    interblock_time = 10 # seconds
    block_schedule = generate_block_schedule(interblock_time, simulation_length) # exponential arrivals
    env = simpy.Environment()
    env.process(run_network(env, client_IDs, device_IDs, num_nodes_candidates[i], arrival_times, block_schedule))
    env.run(until=simulation_length)
    data = progressive_data[-1]
    T_to_R = [d['Time from Transaction Start to Relay End'] for d in data]
    T_to_R = [incom for incom in T_to_R if str(incom) != 'nan']
    plot_hist(T_to_R,"Time Between Transaction Start & 100% Relay")
    T_to_B = [d['Time from Transaction Start to Block End'] for d in data]
    T_to_B = [incom for incom in T_to_B if str(incom) != 'nan']
    plot_hist(T_to_B,"Time Between Transaction Start & Block Write")
    T_to_M = [d['Time from Transaction Start to Maturity'] for d in data]
    T_to_M = [incom for incom in T_to_M if str(incom) != 'nan']
    plot_hist(T_to_M,"Time Between Transaction Start & Maturity")
    print(np.mean(T_to_M), np.std(T_to_M))
    results.append((np.mean(T_to_M), np.std(T_to_M)))


##############################################################################
### Analysis #################################################################

# T_to_R = [d['Time from Transaction Start to Relay End'] for d in data]
# T_to_R = [incom for incom in T_to_R if str(incom) != 'nan']
# plot_hist(T_to_R,"Time Between Transaction Start & 100% Relay")
# T_to_B = [d['Time from Transaction Start to Block End'] for d in data]
# T_to_B = [incom for incom in T_to_B if str(incom) != 'nan']
# plot_hist(T_to_B,"Time Between Transaction Start & Block Write")
# T_to_M = [d['Time from Transaction Start to Maturity'] for d in data]
# T_to_M = [incom for incom in T_to_M if str(incom) != 'nan']
# plot_hist(T_to_M,"Time Between Transaction Start & Maturity")








