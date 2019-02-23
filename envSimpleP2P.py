from envSimple import *

class P2PGroup():
    def __init__(self, network):
        self._vPeers = []
        self._vNetwork = network
    
    def addNode(self, node):
        if node in self._vPeers:
            raise Exception("Already exists")
        self._vPeers.append(node)

    def removeNode(self, node):
        self._vPeers.remove(node)
    
    def getNodes(self):
        return list(self._vPeers)

    def getRTT(self, node1, node2):
        return self._vNetwork.getRtt(node1._vPeerId, node2._vPeerId)

    def isClose(self, node1, node2):
        return self._vNetwork.isClose(node1._vPeerId, node2._vPeerId)

class SimpleP2PEnv(SimpleEnviornment):
    def __init__(self, vi, traces, simulator, abr = None, grp = None, nodeId = -1):
        super().__init__(vi, traces, simulator, abr)
        self._vCatched = {}
        self._vGroup = grp
        self._vPeerId = nodeId

#=============================================
    def start(self, startedAt = -1):
        if not self._vAgent:
            raise Exception("Node agent to start")
        self._vAgent.start(startedAt)
        self._vGroup.addNode(self)

    def getData(self, segId, segQuality):
        return self._vCatched.get((segId, segQuality))

#=============================================
    def _rDownloadNextData(self, nextSegId, nextQuality, sleepTime):
        if self._vDead: return

        timeneeded = 0
        data = None
        for node in self._vGroup._vPeers:
            if node == self:
                continue
            if not self._vGroup.isClose(self, node):
                continue
            if node._vAgent.currentBitrateIndex != self._vAgent.currentBitrateIndex:
                continue
            data = node.getData(nextSegId, nextQuality)
            timeneeded += self._vGroup.getRTT(self, node) #np.random.uniform(0.02,0.5)
            if data:
                break
            if timeneeded > sleepTime:
                break

            #TODO need to add a timeout

        if data:
            timeneeded += data.timetaken * np.random.uniform(0.5, 1.1)
            timeneeded = timeneeded if timeneeded > sleepTime else sleepTime
            self._vSimulator.runAfter(timeneeded, self._rAddToBuffer, data)
            return

        self._rFetchSegment(nextSegId, nextQuality, timeneeded)

#=============================================
    def _rAddToBuffer(self, req, simId = None):
        if self._vDead: return

        self._vDownloadPending = False
        self._vCatched[(req.segId, req.qualityIndex)] = req

        self._vAgent._rAddToBufferInternal(req)

def experimentSimpleP2P(traces, vi, network):
    simulator = Simulator()
    grp = P2PGroup(network)
    ags = []
#     s,ccor x in range(5):
    for x, nodeId in enumerate(network.nodes()):
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        env = SimpleP2PEnv(vi, trace, simulator, BOLA, grp, nodeId)
        simulator.runAt(101.0 + x, env.start, 5)
        ags.append(env)
    simulator.run()
    for i,a in enumerate(ags):
        assert a._vFinished
    
    return ags

def main():
#     np.random.seed(2300)
    simulator = Simulator()
    traces = load_trace.load_trace()
    network = P2PNetwork()
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))

    experimentSimpleP2P(traces, vi, network)

if __name__ == "__main__":
    for x in range(1):
        main()
        print("=========================\n")
