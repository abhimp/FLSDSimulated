'''envRLS - Rapid Live Streaming Environment

'''
from p2pnetwork import P2PRandomNetwork
from envSimpleP2P import P2PGroup
from simulator import Simulator

import numpy as np
import load_trace
import videoInfo as video


'''
Rapid Livestreaming environment.
This environment takes care of agents connected according to our topology
and manages the data download
'''


def setupEnv(traces, vi, network, abr=None):
   simulator = Simulator()
   agents = []
   trace_map = {}

   # allocate different traces for each link in the network
   for x, nodeId in enumerate(network.nodes()):
        link_traces = {}
        for neighbor in network.grp.neighbors(nodeId):
           edge = (min(neighbor, nodeId), max(neighbor, nodeId))
           if edge not in trace_map:
               idx = np.random.randint(len(traces))
               link_traces[neighbor] = traces[idx]
               trace_map[edge] = traces[idx]
           else:
               link_traces[neighbor] = trace_map[edge]
       # TODO: make an environment
   

def main():
    network = P2PRandomNetwork(6)
    # By default, we assume super peer to be node id 0

    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    setupEnv(traces, vi, network)

if __name__ == '__main__':
    main()
