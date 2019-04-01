from envSimple import SimpleEnvironment
from myprint import myprint
import math
import numpy as np
from envSimple import SimpleEnvironment, np, Simulator, load_trace, video, P2PNetwork
from group import GroupManager
import randStateInit as randstate
from easyPlotViewer import EasyPlot
import os

LOG_LOCATION="/tmp/"


class GlobalSingleToneTracker():
    __INSTANT = None

    @staticmethod
    def getInstance(simulator):
        if not GlobalSingleToneTracker.__INSTANT:
            GlobalSingleToneTracker(simulator)
        assert GlobalSingleToneTracker.__INSTANT
        return GlobalSingleToneTracker.__INSTANT

    @staticmethod
    def clean():
        GlobalSingleToneTracker.__INSTANT = None
    
    def __init__(self, simulator):
        assert not GlobalSingleToneTracker.__INSTANT
        GlobalSingleToneTracker.__INSTANT = self
        self.fingerTable = {} 
        self.nodes = {}
        self.nodeIdSet = set()
        self.nodeIds = []
        self.dhtcache = {}
        self.M  = 1

    def newNode(self, node):
        self.nodes[node.networkId] = node
        self.nodeIds.append(node.networkId)
        self.nodeIdSet.add(node.networkId)
        self.nodeIds.sort()
        self.fingerTable = {}
        m = int(math.ceil(math.log(self.nodeIds[-1], 2)))
        M = 2**m        
        for nd in self.nodeIds:
            curNodeId = nd
            finger = []
            for x in range(m):
                i = (curNodeId + 2 ** x)%M
                y = np.searchsorted(self.nodeIds, i) % len(self.nodeIds)
                nid = self.nodeIds[y]
                finger.append(self.nodes[nid])
            self.fingerTable[curNodeId] = finger
        self.M = M
    
    def getNode(self, networkId):
        return self.nodes[networkId]

    def getFingerTable(self, networkId):
        return self.fingerTable[networkId]

    def getSuccessor(self, networkId):
        return self.fingerTable[networkId][0]

    def getNextNodeByKey(self, networkId, key):
        finger = self.fingerTable[networkId]
        uk = (key - networkId) % self.M
        i = int(math.log(uk, 2))
        nextNode = finger[i]
        return nextNode

    def getIsMine(self, networkId, key):
        uk = key % self.M
        uk = (np.searchsorted(self.nodeIds, uk)) % len(self.nodeIds)
        return self.nodeIds[uk] == networkId

    def isAvailable(self, key):
        return key in self.dhtcache

    def getOwner(self, key):
        return self.dhtcache[key]
    def addKey(self, key, ownersId):
        if key not in self.dhtcache:
            self.dhtcache[key] = ownersId
        

class DHTEnvironment(SimpleEnvironment):
    def __init__(self, vi, traces, simulator, abr = None, grp = None, peerId = None, *kw, **kws):
        super().__init__(vi, traces, simulator, abr, peerId, *kw, **kws)
        self.grp = grp
        self.tracker = GlobalSingleToneTracker.getInstance(self._vSimulator)
        self.tracker.newNode(self)
        self.cache = {}
        self.querySeen = set()
        self.keyAdded = set()
        self._vThroughPutData = []

    def searchDHT(self, qlId, segId, sleepTime, startTime):
        key = qlId * self._vVideoInfo.segmentCount + segId
        if self.tracker.getIsMine(self.networkId, key):
            if self.tracker.isAvailable(key):
                ownersId = self.tracker.getOwner(key)
                self.ihaveDHT(ownersId, key, qlId, segId, sleepTime, startTime)
            else:
                self.runFailSafe(qlId, segId, sleepTime, startTime)
            return

        nextNode = self.tracker.getNextNodeByKey(self.networkId, key)
        delay = self.grp.getRtt(nextNode, self)
        self.runAfter(delay, nextNode.queryDHT, key, self.networkId, qlId, segId, sleepTime, startTime)

    def queryDHT(self, key, networkId, qlId, segId, sleepTime, startTime):
        assert (key, networkId, qlId, segId, sleepTime, startTime) not in self.querySeen
        self.querySeen.add((key, networkId, qlId, segId, sleepTime, startTime))
        if networkId == self.networkId: #already failed
            self.runFailSafe(qlId, segId, sleepTime, startTime)
            return
        remNode = self.tracker.getNode(networkId)
        delay = self.grp.getRtt(self, remNode)
        if (qlId, segId) in self.cache:
            self.runAfter(delay, remNode.ihaveDHT, self.networkId, key, qlId, segId, sleepTime, startTime)
            return

        if self.tracker.getIsMine(self.networkId, key):
            if self.tracker.isAvailable(key):
                ownersId = self.tracker.getOwner(key)
                self.runAfter(delay, remNode.ihaveDHT, ownersId, key, qlId, segId, sleepTime, startTime)
                return
            else:
                self.runAfter(delay, remNode.runFailSafe, qlId, segId, sleepTime, startTime)
                return

        nextNode = self.tracker.getNextNodeByKey(self.networkId, key)
        delay = self.grp.getRtt(nextNode, self)
        self.runAfter(delay, nextNode.queryDHT, key, networkId, qlId, segId, sleepTime, startTime)

    def _rFetchSegment(self, nextSegId, nextQuality, sleepTime = 0.0):
        self.searchDHT(nextQuality, nextSegId, sleepTime, self.now)

    def runFailSafe(self, ql, segId, sleepTime, start):
        sleepTimeLeft = max(0, start + sleepTime - self.now)
        if sleepTimeLeft > 0:
            self.runAfter(sleepTimeLeft, self.runFailSafe, ql, segId, sleepTime, start)
            return
        self._rFetchNextSeg(segId, ql)

    def ihaveDHT(self, ownersId, key, ql, segId, sleepTime, start):
        sleepTimeLeft = max(0, start + sleepTime - self.now)
        if sleepTimeLeft > 0:
            self.runAfter(sleepTimeLeft, self.ihaveDHT, ownersId, key, ql, segId, sleepTime, start)
            return

        assert self.networkId != ownersId
            
        node = self.tracker.getNode(ownersId)
        delay = self.grp.getRtt(self, node)
        self.runAfter(delay, node.reqDHT, self, key, ql, segId)

    def reqDHT(self, node, key, ql, segId):
        assert self.networkId != node.networkId
        clen = self._vVideoInfo.fileSizes[ql][segId]
        transmissionTime = self.grp.transmissionTime(self, node, clen)
        self.runAfter(transmissionTime, node._rAddToBuffer, self.cache[(ql, segId)]) 

    def _rAddToBuffer(self, req, simIds = None):
        segId = req.segId
        ql = req.qualityIndex
        key = ql * self._vVideoInfo.segmentCount + segId
        self.cache[(ql, segId)] = req
        self.addToDHT(key, segId, ql, self.networkId)
        self._vAgent._rAddToBufferInternal(req, simIds)

    def addToDHT(self, key, segId, ql, ownersId):
        assert (key, segId, ql, ownersId) not in self.keyAdded
        self.keyAdded.add((key, segId, ql, ownersId))
        if self.tracker.getIsMine(self.networkId, key):
            self.tracker.addKey(key, ownersId)
            return
        node = self.tracker.getNextNodeByKey(self.networkId, key)
        delay = self.grp.getRtt(self, node)
        self.runAfter(delay, node.addToDHT, key, segId, ql, ownersId)


#=============================================
def randomDead(vi, traces, grp, simulator, agents, deadAgents):
    now = simulator.getNow()
    if now - 5 < vi.duration:
        return
    if np.random.randint(2) == 1 or len(deadAgents) == 0:
        nextDead = np.random.randint(len(agents))
        agents[nextDead].die()
        del agents[nextDead]
        trace = (agents[nextDead]._vCookedTime, agents[nextDead]._vCookedBW, agents[nextDead]._vTraceFile)
        deadAgents.append((agents[nextDead]._vPeerId, trace))
    else:
        startAgain = np.random.randint(len(deadAgents))
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        np.random.shuffle(deadAgents)
        nodeId, trace = deadAgents.pop()
        env = DHTEnvironment(vi, trace, simulator, None, grp, nodeId)
        simulator.runAfter(10, env.start, 5)
    ranwait = np.random.uniform(0, 1000)
    for x in agents:
        if not x._vDead and not x._vFinished:
            simulator.runAfter(ranwait, randomDead, vi, traces, grp, simulator, agents, deadAgents)
            break

#=============================================
def encloser(st, label):
        p = "<br><br>"
        p += "<div><b>" + label + "</b></div>"
        return p + st

def plotIdleStallTIme(dpath, group):
    if not os.path.isdir(dpath):
        os.makedirs(dpath)

    colors = ["blue", "green", "red", "cyan", "magenta", "yellow", "black"]

    pltHtmlPath = os.path.join(dpath,"groupP2PTimeout.html")
    open(pltHtmlPath, "w").close()
    eplt = EasyPlot()
    for ql,grpSet in group.groups.items():
        for grp in grpSet:
            grpLabel = str([x._vPeerId for x in grp.getAllNode()])
            label = "<hr><h2>BufferLen</h2>"
            label += " NumNode:" + str(len(grp.getAllNode()))
            label += " Quality Index: " + str(grp.qualityLevel)
#             plt.clf()
#             fig, ax1 = plt.subplots(figsize=(15, 7), dpi=90)
            eplt.addFig()
            for i, ag in enumerate(grp.getAllNode()):
                pltData = ag._vAgent._vBufferLenOverTime
                Xs, Ys = list(zip(*pltData))
                eplt.plot(Xs, Ys, marker="x", label=str(ag._vPeerId), color=colors[i%len(colors)])

                label += "\n<br><span style=\"color: " + colors[i%len(colors)] + "\" >PeerId: " + str(ag._vPeerId)
                label += " avgQualityIndex: " + str(ag._vAgent.avgQualityIndex)
                label += " avgStallTime: " + str(ag._vAgent.totalStallTime)
                label += " startedAt: " + str(ag._vAgent._vStartedAt)
                label += " traceIdx: " + str(AGENT_TRACE_MAP.get(ag._vPeerId, 0))
                label += "</span>"
            eplt.setFigHeader(label)
            label = "<h2>workingTime</h2>"
#             plt.clf()
#             fig, ax1 = plt.subplots(figsize=(15, 7), dpi=90)
            eplt.addFig()
            for i, ag in enumerate(grp.getAllNode()):
                pltData = ag._vWorkingTimes
                Xs, Ys, Zs = list(zip(*pltData))
                eplt.step(Xs, Ys, toolTipData=Zs, marker="o", label="idleTime", where="pre", color=colors[i%len(colors)])
            eplt.setFigHeader(label)
            label = "<h2>StallTime</h2>"
#             plt.clf()
#             fig, ax1 = plt.subplots(figsize=(15, 7), dpi=90)
            eplt.addFig()
            for i, ag in enumerate(grp.getAllNode()):
                pltData = ag._vAgent._vTimeSlipage
                Xs, Ys, Zs = list(zip(*pltData))
                eplt.plot(Xs, Ys, toolTipData=Zs, marker="o", label="idleTime", where="pre", color=colors[i%len(colors)])
            eplt.setFigHeader(label)

            label = "<h2>qualityLevel</h2>"
#             plt.clf()
#             fig, ax1 = plt.subplots(figsize=(15, 7), dpi=90)
            eplt.addFig()
            for i, ag in enumerate(grp.getAllNode()):
                pltData = ag._vAgent._vQualitiesPlayedOverTime
                Xs, Ys, Zs = list(zip(*pltData))
                eplt.step(Xs, Ys, toolTipData=Zs, marker="o", label="idleTime", where="post", color=colors[i%len(colors)])
            eplt.setFigHeader(label)

    with open(pltHtmlPath, "w") as fp:
        eplt.printFigs(fp, width=1000, height=400)

#=============================================
def logThroughput(ag):
    logPath = os.path.join(LOG_LOCATION, "logThroughput")
    if not os.path.isdir(logPath):
        os.makedirs(logPath)
    path = os.path.join(logPath, "%s.csv"%(ag._vPeerId))
    with open(path, "w") as fp:
        print("#time\tBandwidth", file=fp)
        for t, x in ag._vThroughPutData:
            print("{t}\t{x}".format(t=t, x=x), file=fp)

AGENT_TRACE_MAP = {}

#=============================================
def experimentGroupP2PTimeout(traces, vi, network):
    simulator = Simulator()
    grp = GroupManager(4, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []
    maxTime = 0
    for x, nodeId in enumerate(network.nodes()):
        idx = np.random.randint(len(traces))
        startsAt = np.random.randint(vi.duration/2)
        trace = traces[idx]
        env = DHTEnvironment(vi, trace, simulator, None, grp, nodeId)
        simulator.runAt(startsAt, env.start, 5)
        maxTime = 101.0 + x
        AGENT_TRACE_MAP[nodeId] = idx
        ags.append(env)
    simulator.run()
    grp.printGroupBucket()
    for i,a in enumerate(ags):
        assert a._vFinished # or a._vDead
        logThroughput(a)
    if __name__ == "__main__":
        plotIdleStallTIme("results/stall-idle/", grp)
    return ags

#=============================================
def experimentGroupP2PSmall(traces, vi, network):
    network = P2PNetwork()
    simulator = Simulator()
    grp = GroupManager(4, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []

    for trx, nodeId, startedAt in [( 5, 267, 107), (36, 701, 111), (35, 1800, 124), (5, 2033, 127)]:
        trace = traces[trx]
        env = DHTEnvironment(vi, trace, simulator, None, grp, nodeId)
        simulator.runAt(startedAt, env.start, 5)
        AGENT_TRACE_MAP[nodeId] = trx
        ags.append(env)

    simulator.run()
    grp.printGroupBucket()
    for i,a in enumerate(ags):
        assert a._vFinished # or a._vDead
        logThroughput(a)
    if __name__ == "__main__":
        plotIdleStallTIme("results/stall-idle/", grp)
    return ags

def main():
#     randstate.storeCurrentState() #comment this line to use same state as before
    randstate.loadCurrentState()
    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_qBVThFwdYTc.py")
    vi = video.loadVideoTime("./videofilesizes/sizes_penseive.py")
    vi = video.loadVideoTime("./videofilesizes/sizes_qBVThFwdYTc.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()

    experimentGroupP2PTimeout(traces, vi, network)
#     experimentGroupP2PSmall(traces, vi, network)

if __name__ == "__main__":
    for x in range(1):
        main()
        print("=========================\n")
