from envSimple import SimpleEnviornment, np, Simulator, load_trace, COOCKED_TRACE_DIR, video, P2PNetwork
from group import GroupManager
import math
import randStateInit as randstate

SEGMENT_NOT_WORKING = 0
SEGMENT_WORKING = 1
SEGMENT_CACHED = 2
SEGMENT_PEER_WAITING = 3
SEGMENT_IN_QUEUE = 4
SEGMENT_SLEEPING = 5

class SegmentDlStat:
    def __init__(self):
        self.status = SEGMENT_NOT_WORKING
        self.requestedTo = None
        self.requestedAt = -1
        self.peerDlAttemp = 0

class GroupP2PEnv(SimpleEnviornment):
    def __init__(self, vi, traces, simulator, abr = None, grp = None, peerId = None):
        super().__init__(vi, traces, simulator, abr, peerId)
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

    def playerStartedCB(self, *kw, **kwa):
        if self._vGroup:
            self._vGroup.add(self, self._vAgent.nextSegmentIndex+2)
        self._vStarted = True

    def die(self):
        self._vDead = True
        self._vGroup.remove(self, self._vAgent.nextSegmentIndex)

    def schedulesChanged(self, changedFrom, nodes):
        self._vGroupNodes = nodes
        pass

    def _rGetRtt(self, node):
        return self._vGroup.getRtt(self, node)

    def _rTransmissionTime(self, *kw):
        return self._vGroup.transmissionTime(self, *kw)



#=============================================
    def _rFinish(self):
        print(self._vTraceFile)
        self._vAgent._rFinish()
        self._vFinished = True
        print("Downloaded:", self._vTotalDownloaded, "uploaded:", self._vTotalUploaded, \
                "ration U/D:", self._vTotalUploaded/self._vTotalDownloaded)
        print("video id:", self._vPeerId)
        print("=============================")
        self._vFinished = True

#=============================================
    def _rDownloadNextDataTimeout(self, nextSegId, nextQuality, sleepTime):
        if self._vDead: return

#=============================================
# return point after download completed i.e. on simulation event, Only for self dl
    def _rAddToBuffer(self, ql, timetaken, segDur, segIndex, clen, simIds = None, external = False):
        if self._vDead: return
        seg = self._vSegmentStatus[segIndex]
        self._vTotalDownloaded += clen
        if seg.status == SEGMENT_CACHED:
            return
        seg.status = SEGMENT_CACHED
        self._vCatched[segIndex] = (ql, timetaken, segDur, segIndex, clen, simIds, False)
        if segIndex == self._vAgent.nextSegmentIndex:
            self._vAgent._rAddToBufferInternal(ql, timetaken, segDur, segIndex, clen, simIds, False)
        if self._vStarted:
           self._rSendRequestedData(ql, timetaken, segDur, segIndex, clen)

#=============================================
# exit point from this class to envSimple
    def _rFetchSegment(self, nextSegId, nextQuality, sleepTime = 0.0):
        if self._vDead: return
        assert sleepTime >= 0
        self._vSimulator.runAfter(sleepTime, self._rFetchNextSeg, nextSegId, nextQuality)

#=============================================
    def _rDownloadNextDataWake(self, nextSegId, nextQuality):
        if self._vDead: return
        seg = self._vSegmentStatus[nextSegId]
        if seg.status != SEGMENT_SLEEPING:
            return
        assert seg.status == SEGMENT_SLEEPING
        seg.status = SEGMENT_NOT_WORKING
        self._rDownloadNextData(nextSegId, nextQuality, 0)

#=============================================
    def _rAddToPeerBuffer(self, ql, timetaken, segDur, segIndex, clen):
        if self._vDead: return
        seg = self._vSegmentStatus[segIndex]
        if self._vAgent.nextSegmentIndex == segIndex:
            self._vAgent._rAddToBufferInternal(ql, timetaken, segDur, segIndex, clen, None, True)
        if seg.status == SEGMENT_CACHED:
            return
        seg.status = SEGMENT_CACHED
        self._vCatched[segIndex] = (ql, timetaken, segDur, segIndex, clen, None, True)

#=============================================
# entry point from agent
    def _rDownloadNextData(self, nextSegId, nextQuality, sleepTime):
        if self._vDead: return
        now = self.getNow()
        seg = self._vSegmentStatus[nextSegId]
        if sleepTime > 0:
            seg.status = SEGMENT_SLEEPING
            self.runAfter(sleepTime, self._rDownloadNextDataWake, nextSegId, nextQuality)
            return

        if not self._vStarted:
            return self._rFetchSegment(nextSegId, nextQuality, 0)

        if seg.status == SEGMENT_CACHED and self._vAgent.nextSegmentIndex == nextSegId:
            data = self._vCatched[nextSegId]
            return self._vAgent._rAddToBufferInternal(*data)

        if seg.status == SEGMENT_NOT_WORKING:
            seg.status = SEGMENT_IN_QUEUE
            self._vQueue.append((nextSegId, nextQuality, sleepTime, now))

        earlyFetch = True
        while len(self._vQueue):
            nextSegId, nextQuality, sleepTime, at = self._vQueue.pop(0)
            assert sleepTime <= 0
            seg = self._vSegmentStatus[nextSegId]
            downloader = self.getDownloaderFor(nextSegId) #_vGroup.currentSchedule(self, nextSegId)
            if downloader != self and downloader:
                rtt = self._rGetRtt(downloader)
                self.runAfter(rtt, downloader._rRequestSegment, self, nextSegId, nextQuality)
                seg.status = SEGMENT_PEER_WAITING
                continue

            if self._vDownloadPending:
                assert seg.status == SEGMENT_IN_QUEUE
                self._vQueue.append((nextSegId, nextQuality, sleepTime, now))
                return

            earlyFetch = False
            seg.status = SEGMENT_WORKING
            self._rFetchSegment(nextSegId, nextQuality, sleepTime)
            break

        if earlyFetch:
            segId, waitTime = self._rFindNextDownloadableSegment(nextSegId)
            if segId < 0:
                return
            seg = self._vSegmentStatus[segId]
            if seg.status != SEGMENT_NOT_WORKING:
                return
            ql = self._vGroup.getQualityLevel(self)
            self._rDownloadNextData(segId, ql, 0 if waitTime <= 0 else waitTime)

#=============================================
    def getDownloaderFor(self, segId):
        downloader = self._vGroup.currentSchedule(self, segId)
        if downloader not in self._vGroupNodes:
            return None
    
#=============================================
# findout next segId to be downloaded
    def _rFindNextDownloadableSegment(self, nextSegId):
        now = self.getNow()
        while nextSegId < self._vVideoInfo.segmentCount:
            waitTime = self._vAgent._rIsAvailable(nextSegId)
            downloader = self.getDownloaderFor(nextSegId) #self._vGroup.currentSchedule(self, nextSegId)
            if not downloader or downloader == self:
                return (nextSegId, waitTime)
            nextSegId += 1
        return (-1, 0)

#=============================================
    def _rSendToOtherPeer(self, node, ql, timetaken, segDur, segIndex, clen):
        if self._vDead: return
        self._vTotalUploaded += clen
        node._rAddToPeerBuffer(ql, timetaken, segDur, segIndex, clen)

#=============================================
    def _rPeerRequestFailed(self, segId, ql):
        if self._vDead: return
        now = self.getNow()
        seg = self._vSegmentStatus[segId]
        if seg.status != SEGMENT_PEER_WAITING:
            return
        seg.status = SEGMENT_NOT_WORKING
        self._rDownloadNextData(segId, ql, 0)

#=============================================
# receive segment request from other peer
    def _rRequestSegment(self, node, segId, ql):
        if self._vDead: return
        seg = self._vSegmentStatus[segId]
        if seg.status == SEGMENT_WORKING:
            self._vPendingRequestedSegments.setdefault(segId, {})[node] = ql
            return #don't need to bother
        if seg.status == SEGMENT_CACHED:
            ql, timetaken, segDur, segIndex, clen, _, __ = self._vCatched[segId]
            time = self._rTransmissionTime(node, clen)
            self.runAfter(time, self._rSendToOtherPeer, node, ql, timetaken, segDur, segIndex, clen)
            return
        rtt = self._rGetRtt(node)
        self.runAfter(rtt, node._rPeerRequestFailed, segId, ql)
        pass

#=============================================
# server pending request to other peers
    def _rSendRequestedData(self, *kw):
        ql, timetaken, segDur, segIndex, clen = kw
        rnodes = self._vPendingRequestedSegments.get(segIndex, {})
        for node in self._vGroup.getAllNode(self, self):
            self._rSendToOtherPeer(node, *kw)
            if node in rnodes:
                del rnodes[node]
        for node in rnodes:
            rtt = self._rGetRtt(node)
            self.runAfter(rtt, node._rPeerRequestFailed, segIndex, rnodes[node])
        if len(rnodes):
            del self._vPendingRequestedSegments[segIndex]
        pass

#=============================================
    def start(self, startedAt = -1):
        super().start(startedAt)
        self._vAgent.addStartupCB(self.playerStartedCB)

def randomDead(simulator, agents):
    nextDead = np.random.randint(len(agents))
    agents[nextDead].die()
    del agents[nextDead]
    ranwait = np.random.uniform(0, 100)
    for x in agents:
        if not x._vDead and not x._vFinished:
            simulator.runAfter(ranwait, randomDead, simulator, agents)
            break

def main():
    randstate.storeCurrentState() #comment this line to use same state as before
    randstate.loadCurrentState()
    simulator = Simulator()
    traces = load_trace.load_trace(COOCKED_TRACE_DIR)
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()
    grp = GroupManager(4, 7, vi, network)#np.random.randint(len(vi.bitrates)))
    ags = []
    maxTime = 0
    for x, nodeId in enumerate(network.nodes()):
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        env = GroupP2PEnv(vi, trace, simulator, None, grp, nodeId)
#         env = SimpleEnviornment(vi, trace, simulator, BOLA)
        simulator.runAt(101.0 + x, env.start, 5)
        maxTime = 101.0 + x
        ags.append(env)
    simulator.runAt(maxTime + 50, randomDead, simulator, ags)
    simulator.run()
    for i,a in enumerate(ags):
        assert a._vFinished # or a._vDead

if __name__ == "__main__":
    for x in range(1000):
        main()
        print("=========================\n")
