import networkx as nx
import numpy as np

NUM_NEIGHBOURS = 3

class P2PNetwork():
    def  __init__(self, fpath = "./graph/as19990829.txt"):
        self.grp = nx.Graph()
        if fpath is not None:
            self.__readPfile(fpath)
    
    def __readPfile(self, fpath):
        with open(fpath) as fp:
            for line in fp:
                if line[0] == "#":
                    continue
                n1, n2 = [int(x) for x in line.strip().split()]
                self.grp.add_edge(n1, n2)

    def nodes(self):
        nodes = sorted(self.grp.nodes())
        for node in nodes:
            yield node

    def numNodes(self):
        return len(self.grp.nodes())

    def getDistance(self, n1, n2):
        return nx.shortest_path_length(self.grp, n1, n2)

    def isClose(self, n1, n2):
#         return True
        dist = self.getDistance(n1, n2)
        return dist < 3 #threshold

    def getRtt(self, n1, n2):
        distance = self.getDistance(n1, n2)
        distance = min(9, distance)
#         distance = max(2, distance)

        rtt = 2**distance
        rtt *= np.random.uniform(0.95, 1.05)
        return rtt/1000.0

    def transmissionTime(self, n1, n2, size, buf=64*1024, maxSpeed=-1): #default 5mb data
        maxSpeed = max(maxSpeed, 40*1000*1000) if maxSpeed == -1 else maxSpeed
        rtt = self.getRtt(n1, n2)
        speed = buf * 8 / rtt
        speed = min(maxSpeed, speed)
        time = size*8/speed
        time *= np.random.uniform(0.95, 1.05)
        return time


'''Creates a topology where each node gets 1<=n<=3 neighbours
The topology is randomly created
'''
class P2PRandomNetwork(P2PNetwork):
    def __init__(self, num_nodes, connectivity=3):
        super().__init__(None)
        # for now, create a  random 3-regular graph wherein all nodes have exactly 3 neighbours
        print(connectivity, num_nodes)
        self.grp = nx.random_regular_graph(connectivity, num_nodes)


'''Fully connected graph to know global state
'''
class P2PFullyConnectedNetwork(P2PNetwork):
    def __init__(self, num_nodes):
        super().__init__(None)
        self.grp = nx.complete_graph(num_nodes)


'''Star graph - each peer downloads only from Super Peer
'''
class P2PStarNetwork(P2PNetwork):
    def __init__(self, num_nodes):
        super().__init__(None)
        self.grp = nx.star_graph(num_nodes)


def main():
    grp = P2PRandomNetwork(6)
    for node in grp.nodes():
        print(node)
        for neighbor in grp.grp.neighbors(node):
            print(neighbor," "),
        print("\n")

if __name__ == "__main__":
    main()
