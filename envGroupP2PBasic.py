from envSimple import SimpleEnvironment, np, Simulator, load_trace, video, P2PNetwork
from group import GroupManager
import math
import randStateInit as randstate

SEGMENT_NOT_WORKING = 0
SEGMENT_WORKING = 1
SEGMENT_CACHED = 2
SEGMENT_PEER_WAITING = 3
SEGMENT_IN_QUEUE = 4
SEGMENT_SLEEPING = 5
SEGMENT_PEER_WORKING = 6

SEGMENT_STATUS_STRING = [
"SEGMENT_NOT_WORKING",
"SEGMENT_WORKING",
"SEGMENT_CACHED",
"SEGMENT_PEER_WAITING",
"SEGMENT_IN_QUEUE",
"SEGMENT_SLEEPING",
"SEGMENT_PEER_WORKING",
]

class SegmentDlStat:
    def __init__(self):
        self._status = SEGMENT_NOT_WORKING
        self.requestedTo = None
        self.requestedAt = -1
        self.peerDlAttemp = 0
        self.peerStatus = {}
        self.peerTimeoutHappened = False
        self.peerTimeoutRef = -1
        self.servingTo = []
        self.autoEntryOver = False

    @property
    def statusString(self):
        return SEGMENT_STATUS_STRING[self._status]

    @property
    def status(self):
        return self._status

    @status.setter
    def status(s, st):
        if s._status == SEGMENT_CACHED:
            assert st == SEGMENT_CACHED
        if s._status == SEGMENT_WORKING:
            assert st == SEGMENT_WORKING or st == SEGMENT_CACHED
        s._status = st

class GroupP2PEnvBasic(SimpleEnvironment):
    def __init__(self, vi, traces, simulator, abr = None, grp = None, peerId = None, *kw, **kws):
        super().__init__(vi, traces, simulator, abr, peerId, *kw, **kws)
#         self._vAgent = Agent(vi, self, abr)
        self._vDownloadPending = False
        self._vSegmentDownloading = -1
        self._vGroup = grp
        self._vCatched = {}
        self._vOtherPeerRequest = {}
        self._vTotalDownloaded = 0
        self._vTotalUploaded = 0
        self._vStarted = False
        self._vFinished = False

        self._vSegmentStatus = [SegmentDlStat() for x in range(self._vVideoInfo.segmentCount)]
        self._vPendingRequestedSegments = {}
        self._vGroupNodes = None
        self._vQueue = []

        self._vEarlyDownloaded = 0
        self._vNormalDownloaded = 0
        self._vThroughPutData = {}
        self._vDownloadQueue = []
        self._vServingPeers = {}

    def playerStartedCB(self, *kw, **kwa):
        if self._vGroup:
            self._vGroup.add(self, self._vAgent.nextSegmentIndex+2)
        self._vStarted = True

    def die(self):
        self._vDead = True
        self._vGroup.remove(self, self._vAgent.nextSegmentIndex)

    def schedulesChanged(self, changedFrom, nodes, sched):
        self._vGroupNodes = nodes

    def _rGetRtt(self, node):
        return self._vGroup.getRtt(self, node)

    def _rTransmissionTime(self, *kw):
        return self._vGroup.transmissionTime(self, *kw)

    @property
    def now(self):
        return self.getNow()

#=============================================
    def _rFinish(self):
        print(self._vTraceFile)
        self._vAgent._rFinish()
        self._vFinished = True
        print("Downloaded:", self._vTotalDownloaded, "uploaded:", self._vTotalUploaded, \
                "ration U/D:", self._vTotalUploaded/self._vTotalDownloaded)
        print("Early download:", self._vEarlyDownloaded, "normal:", self._vNormalDownloaded)
        print("video id:", self._vPeerId)
        print("=============================")
        self._vFinished = True

#=============================================
    def _rDownloadNextDataTimeout(self, nextSegId, nextQuality, sleepTime):
        if self._vDead: return

#=============================================
# return point after download completed i.e. on simulation event, Only for self dl
    def _rAddToBuffer(self, req, simIds = None):
        if self._vDead: return
        segId, clen = req.segId, req.clen
        seg = self._vSegmentStatus[segId]
        self._rDistributeToOther(req) #sending to others
        if seg.status == SEGMENT_CACHED:
            return
        assert seg.status != SEGMENT_CACHED
        self._vTotalDownloaded += clen
        self._vDownloadPending = False
        seg.status = SEGMENT_CACHED
        self._vCatched[segId] = req

        seg = self._vSegmentStatus[segId]
        self._rDownloadFromDownloadQueue()

        if segId == self._vAgent.nextSegmentIndex and seg.autoEntryOver:
            self._vAgent._rAddToBufferInternal(req)

        self._vThroughPutData[self.now] = req.throughput

        if self._vGroup.currentSchedule(self, segId) == self:
           for node in self._vGroupNodes:
               if node == self:
                   continue
               node._rPeerSegmentStatus(self, segId, SEGMENT_CACHED)

#=============================================
    def _rDistributeToOther(self, req):
        if not self._vGroupNodes:
            return
        for node in self._vGroupNodes:
            if node == self:
                continue
            rtt = self._rGetRtt(node)
            seg = node._vSegmentStatus[req.segId]
            if seg.status in [SEGMENT_WORKING, SEGMENT_CACHED]:
                continue
            if seg.status != SEGMENT_PEER_WORKING:
                rtt = self._rTransmissionTime(node, req.clen)
                seg.status = SEGMENT_PEER_WORKING
            elif seg.peerStatus.get(self, SEGMENT_NOT_WORKING) != SEGMENT_WORKING:
                # segment is peer waiting but for some other peer
                continue
            servingTos = self._vServingPeers.setdefault(req.segId, [])
            if node not in servingTos:
                servingTos.append(node)
            self.runAfter(rtt, self._rSendToOtherPeer, node, req)

        if req.segId in self._vPendingRequestedSegments:
            del self._vPendingRequestedSegments[req.segId]

#=============================================
    def _rPredictedThroughput(self):
        maxTime = max(self._vThroughPutData.keys())
        return self._vThroughPutData[maxTime]

#=============================================
# exit point from this class to envSimple
    def _rFetchSegment(self, nextSegId, nextQuality, sleepTime = 0.0):
        if self._vDead: return
        assert sleepTime == 0
        if nextSegId > self._vAgent.nextSegmentIndex:
            self._vEarlyDownloaded += 1
        else:
            self._vNormalDownloaded += 1
        self._vDownloadPending = True
        self._rFetchNextSeg(nextSegId, nextQuality)
        if self._vGroup.currentSchedule(self, nextSegId) == self:
           for node in self._vGroupNodes:
               if node == self:
                   continue
               node._rPeerSegmentStatus(self, nextSegId, SEGMENT_WORKING)


#=============================================
    def _rAddToDownloadQueue(self, nextSegId, nextQuality):
        seg = self._vSegmentStatus[nextSegId]
        assert seg.status == SEGMENT_NOT_WORKING
        self._vDownloadQueue.append((nextSegId, nextQuality))
        self._rDownloadFromDownloadQueue()

#=============================================
    def _rDownloadFromDownloadQueue(self):
        if self._vDownloadPending:
            return
        while len(self._vDownloadQueue):
            segId, ql = self._vDownloadQueue.pop(0)
            seg = self._vSegmentStatus[segId]
            if seg.status in [SEGMENT_CACHED, SEGMENT_WORKING, SEGMENT_PEER_WORKING]:
                continue
            seg.status = SEGMENT_WORKING
            self._rFetchSegment(segId, ql)
            break

#=============================================
    def _rPeerSegmentStatus(self, node, segId, status):
        seg = self._vSegmentStatus[segId]
        assert status in [SEGMENT_CACHED, SEGMENT_WORKING]
        if status == SEGMENT_WORKING:
            if seg.status in [SEGMENT_CACHED, SEGMENT_WORKING, SEGMENT_PEER_WORKING]:
                return
            seg.status = SEGMENT_PEER_WORKING
            node._vSegmentStatus[segId].servingTo += [self]
            node._vServingPeers.setdefault(segId, []).append(self)
        seg.peerStatus[node] = status

#=============================================
    def _rDownloadNextDataBeforeGroupStart(self, nextSegId, nextQuality, sleepTime):
        now = self.getNow()
        seg = self._vSegmentStatus[nextSegId]
        if sleepTime > 0:
            seg.status = SEGMENT_SLEEPING
            self.runAfter(sleepTime, self._rDownloadNextDataBeforeGroupStart, nextSegId, nextQuality, 0)
            return
        if seg.status == SEGMENT_SLEEPING or seg.status == SEGMENT_NOT_WORKING:
            seg.status = SEGMENT_NOT_WORKING
            self._rAddToDownloadQueue(nextSegId, nextQuality)
            return

        if seg.status == SEGMENT_PEER_WORKING: 
            if seg.peerTimeoutRef != -1 and not seg.peerTimeoutHappened:
                timeout, ql = self._rTimeoutForPeer(nextSegId)
                downloader = seg.peerResponsible
                ref = self.runAfter(timeout, self._rPeerDownloadTimeout, downloader, nextSegId, ql)
            return
        assert False


#=============================================
    def _rTimeoutForPeer(self, segId, ql = -1):
        if ql == -1:
            ql = self._vGroup.getQualityLevel(self)

        if ql > 0:
            ql = ql - 1

        downloadTIme = self._vVideoInfo.bitrates[ql] * self._vVideoInfo.segmentDuration / self._rPredictedThroughput()

        bufferLeft = self._vAgent.bufferLeft

        timeout = bufferLeft - downloadTIme

        return round(timeout, 3), ql


#=============================================
    def _rPeerDownloadTimeout(self, downloader, segId, ql):
        seg = self._vSegmentStatus[segId]
        if seg.status in [SEGMENT_CACHED, SEGMENT_WORKING, SEGMENT_PEER_WORKING]:
            return
        if not downloader._vDead:
            self._rCancelPeerDownloading(downloader, segId)
        if seg.status == SEGMENT_PEER_WAITING:
            seg.status = SEGMENT_NOT_WORKING
        seg.peerTimeoutHappened = True
        seg.peerTimeoutRef = -1
        self._rAddToDownloadQueue(segId, ql)

#=============================================
# entry point from agent
    def _rDownloadNextData(self, nextSegId, nextQuality, sleepTime):
        if self._vDead: return
        now = self.getNow()
        seg = self._vSegmentStatus[nextSegId]
        if not self._vStarted or len(self._vGroupNodes) <= 1:
            seg.autoEntryOver = True
            return self._rDownloadNextDataBeforeGroupStart(nextSegId, nextQuality, sleepTime)

        if sleepTime > 0:
            self.runAfter(sleepTime, self._rDownloadNextData, nextSegId, nextQuality, 0)
            return

        if seg.status == SEGMENT_CACHED:
            assert self._vAgent.nextSegmentIndex >= nextSegId
            if self._vAgent.nextSegmentIndex == nextSegId:
                req= self._vCatched[nextSegId]
                self._vAgent._rAddToBufferInternal(req)
            return

        seg.autoEntryOver = True

        if seg.status == SEGMENT_WORKING \
                or seg.status == SEGMENT_SLEEPING \
                or seg.status == SEGMENT_PEER_WAITING \
                or seg.status == SEGMENT_IN_QUEUE:
            return

        if seg.status == SEGMENT_PEER_WORKING:
            return

        if sleepTime > 0:
            seg.status = SEGMENT_SLEEPING
            self.runAfter(sleepTime, self._rDownloadNextDataWake, nextSegId, nextQuality, 0)
            return

        seg.status = SEGMENT_NOT_WORKING

        self._rDownloadNextDataGroup(nextSegId, nextQuality, 0)

#=============================================
    def _rDownloadNextDataWake(self, nextSegId, nextQuality, sleepTime):
        seg = self._vSegmentStatus[nextSegId]
        if seg.status != SEGMENT_SLEEPING:
            return
        seg.status = SEGMENT_NOT_WORKING
        self._rDownloadNextDataGroup(nextSegId, nextQuality, 0)

#=============================================
    def _rDownloadNextDataGroup(self, nextSegId, nextQuality, sleepTime):
        now = self.getNow()
        seg = self._vSegmentStatus[nextSegId]
        downloader = self._vGroup.currentSchedule(self, nextSegId)

        if downloader and downloader != self:
            timeout, ql = self._rTimeoutForPeer(nextSegId)
            seg.status = SEGMENT_PEER_WAITING
            if timeout <= 0:
                self._rPeerDownloadTimeout(downloader, nextSegId, ql)
            else:
                ref = self.runAfter(timeout, self._rPeerDownloadTimeout, downloader, nextSegId, ql)
                seg.peerTimeoutRef = ref

        nextSegId, waitTime = self._rFindNextDownloadableSegment(nextSegId)
        if nextSegId < 0 or waitTime > 0:
            return

        seg = self._vSegmentStatus[nextSegId]
        if seg.status in [SEGMENT_CACHED, SEGMENT_WORKING, SEGMENT_PEER_WORKING]:
            return

        self._rAddToDownloadQueue(nextSegId, self._vGroup.getQualityLevel(self))



#=============================================
# findout next segId to be downloaded
    def _rFindNextDownloadableSegment(self, nextSegId):
        now = self.getNow()
        while nextSegId < self._vVideoInfo.segmentCount:
            waitTime = self._vAgent._rIsAvailable(nextSegId)
            downloader = self._vGroup.currentSchedule(self, nextSegId) #self._vGroup.currentSchedule(self, nextSegId)
            if not downloader or downloader == self:
                return (nextSegId, round(waitTime, 3))
            nextSegId += 1
        return (-1, 0)

#=============================================
    def _rReceiveReq(self, node, req):
        if self._vDead: return

        segId = req.segId
        seg = self._vSegmentStatus[segId]
        assert seg.status != SEGMENT_WORKING
        if seg.status != SEGMENT_CACHED:
            seg.status = SEGMENT_CACHED
            self._vCatched[segId] = req
            if segId == self._vAgent.nextSegmentIndex and seg.autoEntryOver:
                self._vAgent._rAddToBufferInternal(req)
            node._vTotalUploaded += req.clen #this is not exactly the way it will happen in the real world scenerio.
                                             #However, in real world,

#=============================================
    def _rCancelPeerDownloading(self, node, segId):
        rtt = self._rGetRtt(node)
        self.runAfter(rtt, node._rCancelRequestReceived, self, segId)

#=============================================
    def _rCancelRequestReceived(self, node, segId):
        nodes = self._vPendingRequestedSegments.get(segId, set())
        if node in nodes:
            nodes.remove(node)

#=============================================
#Calling other peer function
    def _rSendToOtherPeer(self, node, req):
        if self._vDead: return
#         self._vTotalUploaded += clen
        seg = node._vSegmentStatus[req.segId]
        if seg.status in [SEGMENT_CACHED, SEGMENT_WORKING]:
            return
        seg.status = SEGMENT_PEER_WORKING
        node._rReceiveReq(self, req)
        if req.segId in self._vServingPeers:
            servingTos = self._vServingPeers[req.segId]
            if node in servingTos:
                servingTos.remove(node)
            if len(servingTos) == 0:
                del self._vServingPeers[req.segId]

#=============================================
    def _rRequestSegment(self, downloader, nextSegId):
        rtt = self._rGetRtt(downloader)
        self.runAfter(rtt, downloader._rSegmentRequestRecved, self, nextSegId)

#=============================================
    def _rSegmentRequestRecved(self, node, segId):
        assert False
        seg = self._vSegmentStatus[segId]
        if seg.status == SEGMENT_CACHED:
            rtt = self._rGetRtt
            self.runAfter(rtt, self._rSendToOtherPeer, node, self._vCatched[segId])
        elif seg.status == SEGMENT_WORKING:
            self._vPendingRequestedSegments.setdefault(segId, set()).add(node)
        else:
            assert False

#=============================================
    def start(self, startedAt = -1):
        super().start(startedAt)
        self._vAgent.addStartupCB(self.playerStartedCB)

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
        env = GroupP2PEnv(vi, trace, simulator, None, grp, nodeId)
        simulator.runAfter(10, env.start, 5)
    ranwait = np.random.uniform(0, 1000)
    for x in agents:
        if not x._vDead and not x._vFinished:
            simulator.runAfter(ranwait, randomDead, vi, traces, grp, simulator, agents, deadAgents)
            break

#=============================================
def experimentGroupP2PBasic(traces, vi, network):
    simulator = Simulator()
    grp = GroupManager(4, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []
    maxTime = 0
    for x, nodeId in enumerate(network.nodes()):
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        env = GroupP2PEnvBasic(vi, trace, simulator, None, grp, nodeId)
#         env = SimpleEnvironment(vi, trace, simulator, BOLA)
        simulator.runAt(101.0 + x, env.start, 5)
        maxTime = 101.0 + x
        ags.append(env)
#     simulator.runAt(maxTime + 50, randomDead, vi, traces, grp, simulator, ags, deadAgents)
    simulator.run()
    grp.printGroupBucket()
    for i,a in enumerate(ags):
        assert a._vFinished # or a._vDead
    return ags

def main():
#     randstate.storeCurrentState() #comment this line to use same state as before
    randstate.loadCurrentState()
    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()

    experimentGroupP2P(traces, vi, network)

if __name__ == "__main__":
    for x in range(2000):
        main()
        print("=========================\n")
