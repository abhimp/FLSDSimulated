from envSimple import *

class P2PGroup():
    def __init__(self):
        self._vPeers = []
    
    def addNode(self, node):
        if node in self._vPeers:
            raise Exception("Already exists")
        self._vPeers.append(node)

    def removeNode(self, node):
        self._vPeers.remove(node)
    
    def getNodes(self):
        return list(self._vPeers)

class SimpleP2PEnv(SimpleEnviornment):
    def __init__(self, vi, traces, simulator, abr = None, grp = None):
        super().__init__(vi, traces, simulator, abr)
        self._vCatched = {}
        self._vGroup = grp

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
            data = node.getData(nextSegId, nextQuality)
            if data:
                break

            timeneeded += np.random.uniform(0.02,0.5)
            #TODO need to add a timeout

        if data:
            ql, timetaken, segDur, segIndex, clen, simIds, external = data
            timeneeded += timetaken * np.random.uniform(0.5, 1.1)
            timeneeded = timeneeded if timeneeded > sleepTime else sleepTime
            self._vSimulator.runAfter(timeneeded, self._rAddToBuffer, ql, timetaken, segDur, segIndex, clen, simIds, external)
            return


        self._rFetchSegment(nextSegId, nextQuality, sleepTime)

#=============================================
    def _rAddToBuffer(self, ql, timetaken, segDur, segIndex, clen, simIds = None, external = False):
        if self._vDead: return

        self._vDownloadPending = False
        self._vCatched[(segIndex, ql)] = (ql, timetaken, segDur, segIndex, clen, simIds, external)

        self._vAgent._rAddToBufferInternal(ql, timetaken, segDur, segIndex, clen, simIds, external)



def main():
#     np.random.seed(2300)
    simulator = Simulator()
    traces = load_trace.load_trace(COOCKED_TRACE_DIR)
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    grp = P2PGroup()
    ags = []
    for x in range(5):
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        env = SimpleP2PEnv(vi, trace, simulator, BOLA, grp)
        simulator.runAt(101.0 + x, env.start, 5)
        ags.append(env)
    simulator.run()
    for i,a in enumerate(ags):
        assert a._vFinished

if __name__ == "__main__":
    for x in range(1):
        main()
        print("=========================\n")
