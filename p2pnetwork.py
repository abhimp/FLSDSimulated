import networkx as nx
import numpy as np

class P2PNetwork():
    def  __init__(self, fpath = "./graph/as19990829.txt"):
        self.grp = nx.Graph()
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

    def getDistance(self, n1, n2):
        return nx.shortest_path_length(self.grp, n1, n2)

    def isClose(self, n1, n2):
#         return True
        dist = self.getDistance(n1, n2)
        return dist < 3 #threshold

    def getRtt(self, n1, n2):
        distance = self.getDistance(n1, n2)
        distance = 9 if distance > 9 else distance
        rtt = 2**distance
        return rtt/1000.0

    def transmissionTime(self, n1, n2, size, buf=64*1024): #default 5mb data
        rtt = self.getRtt(n1, n2)
        speed = buf * 8 / rtt
        time = size*8/speed
        time *= np.random.uniform(0.95, 1.05)
        return time



def main():
    grp = Network()
    for node in grp.nodes():
        print(node)

if __name__ == "__main__":
    main()
