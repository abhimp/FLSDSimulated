from envSimple import SimpleEnvironment, np, Simulator, load_trace, video, P2PNetwork
from myprint import myprint
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
        self._status = SEGMENT_NOT_WORKING
        self.requestedTo = None
        self.requestedAt = -1
        self.peerDlAttemp = 0

    @property
    def status(self):
        return self._status

    @status.setter
    def status(s, st):
        if s._status == SEGMENT_CACHED:
            assert st == SEGMENT_CACHED
        s._status = st

class GroupP2PEnv(SimpleEnvironment):
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

    def playerStartedCB(self, *kw, **kwa):
        if self._vGroup:
            self._vGroup.add(self, self._vAgent.nextSegmentIndex+2)
        self._vStarted = True

    def die(self):
        self._vDead = True
        self._vGroup.remove(self, self._vAgent.nextSegmentIndex)

    def schedulesChanged(self, changedFrom, nodes, sched):
        self._vGroupNodes = nodes
        pendingSegIds = list(self._vPendingRequestedSegments.keys())
        for segId in pendingSegIds:
            downloader = sched.get(segId, None)
            if downloader and downloader != self:
                self.denyPendingRequests(segId)

    def denyPendingRequests(self, segId):
#         return
        if segId not in self._vPendingRequestedSegments:
            return
        waiter = self._vPendingRequestedSegments[segId]
        for node in waiter:
            rtt = self._rGetRtt(node)
            ql = waiter[node]
            self.runAfter(rtt, node._rPeerRequestFailed, segId, ql)
        del self._vPendingRequestedSegments[segId]

    def _rGetRtt(self, node):
        return self._vGroup.getRtt(self, node)

    def _rTransmissionTime(self, *kw):
        return self._vGroup.transmissionTime(self, *kw)



#=============================================
    def _rFinish(self):
        myprint(self._vTraceFile)
        self._vAgent._rFinish()
        self._vFinished = True
        myprint("Downloaded:", self._vTotalDownloaded, "uploaded:", self._vTotalUploaded, \
                "ration U/D:", self._vTotalUploaded/self._vTotalDownloaded)
        myprint("Early download:", self._vEarlyDownloaded, "normal:", self._vNormalDownloaded)
        myprint("video id:", self._vPeerId)
        myprint("=============================")
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
        self._vTotalDownloaded += clen
        self._vDownloadPending = False
        if seg.status == SEGMENT_CACHED:
            return
        seg.status = SEGMENT_CACHED
        self._vCatched[segId] = req
        if segId == self._vAgent.nextSegmentIndex:
            self._vAgent._rAddToBufferInternal(req)
        if self._vStarted:
           self._rSendRequestedData(req)
        elif segId in self._vPendingRequestedSegments:
            self.denyPendingRequests(segId)

#=============================================
# exit point from this class to envSimple
    def _rFetchSegment(self, nextSegId, nextQuality, sleepTime = 0.0, extraData=None):
        if self._vDead: return
        assert sleepTime == 0
        if nextSegId > self._vAgent.nextSegmentIndex:
            self._vEarlyDownloaded += 1
        else:
            self._vNormalDownloaded += 1
        self._vDownloadPending = True
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
    def _rAddToPeerBuffer(self, sender, req):
        if self._vDead: return
        assert sender != self
        segId, clen = req.segId, req.clen
        seg = self._vSegmentStatus[segId]
        if self._vAgent.nextSegmentIndex == segId:
            self._vAgent._rAddToBufferInternal(req)
        if seg.status == SEGMENT_CACHED:
            return
        sender._vTotalUploaded += clen
        seg.status = SEGMENT_CACHED
        self._vCatched[segId] = req

#=============================================
    def _rDownloadNextDataBeforeGroupStart(self, nextSegId, nextQuality, sleepTime):
        now = self.getNow()
        seg = self._vSegmentStatus[nextSegId]
        if sleepTime > 0:
            seg.status = SEGMENT_SLEEPING
            self.runAfter(sleepTime, self._rDownloadNextDataBeforeGroupStart, nextSegId, nextQuality, 0)
            return
        if seg.status == SEGMENT_SLEEPING or seg.status == SEGMENT_NOT_WORKING:
            seg.status == SEGMENT_WORKING
            self._rFetchSegment(nextSegId, nextQuality, 0)

            return

        assert False

#=============================================
    def _rDownloadNextDataForMe(self):
        now = self.getNow()
        nextSegId = self._vAgent.nextSegmentIndex
        ql = self._vGroup.getQualityLevel(self)
        while nextSegId < self._vVideoInfo.segmentCount:
            seg = self._vSegmentStatus[nextSegId]
            downloader = self._vGroup.currentSchedule(self, nextSegId)
            if downloader and downloader != self:
                if seg.status != SEGMENT_PEER_WAITING \
                    and seg.status != SEGMENT_CACHED \
                    and seg.status != SEGMENT_WORKING:
#                     assert seg.peerDlAttemp < 3
                    if seg.peerDlAttemp >= 3:
                        wait = self._vAgent._rIsAvailable(nextSegId)
                        if wait <= 0:
                            if not self._vDownloadPending:
                                seg.status = SEGMENT_WORKING
                                self._rFetchSegment(nextSegId, ql, 0)
                                break
                        else:
                            self.runAfter(wait, self._rDownloadNextDataForMe)
                    else:
                        self.denyPendingRequests(nextSegId)
                        seg.status = SEGMENT_PEER_WAITING
                        seg.requestedTo = downloader
                        self.runAfter(self._rGetRtt(downloader), downloader._rRequestSegment, self, nextSegId, ql)
            elif seg.status == SEGMENT_NOT_WORKING \
                    and not self._vDownloadPending:
                seg.status = SEGMENT_WORKING
                self._rFetchSegment(nextSegId, ql, 0)
                break
            else:
                break
            nextSegId += 1



#=============================================
# entry point from agent
    def _rDownloadNextData(self, nextSegId, nextQuality, sleepTime):
        if self._vDead: return
        if not self._vStarted: 
            return self._rDownloadNextDataBeforeGroupStart(nextSegId, nextQuality, sleepTime)
        now = self.getNow()
        seg = self._vSegmentStatus[nextSegId]

        if seg.status == SEGMENT_CACHED:
            req= self._vCatched[nextSegId]
            self._vAgent._rAddToBufferInternal(req)
            return
            

        if sleepTime > 0:
            seg.status = SEGMENT_SLEEPING
            self.runAfter(sleepTime, self._rDownloadNextDataWake, nextSegId, nextQuality)
        else:
            self._rDownloadNextDataForMe()

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
    def _rSendToOtherPeer(self, node, req):
        if self._vDead: return
#         self._vTotalUploaded += clen
        node._rAddToPeerBuffer(self, req)

#=============================================
    def _rPeerRequestFailed(self, segId, ql):
        if self._vDead: return
        now = self.getNow()
        seg = self._vSegmentStatus[segId]
        if seg.status != SEGMENT_PEER_WAITING:
            return
        seg.status = SEGMENT_NOT_WORKING
        seg.peerDlAttemp += 1
        self._rDownloadNextData(segId, ql, 0)

#=============================================
# receive segment request from other peer
    def _rRequestSegment(self, node, segId, ql):
        if self._vDead: return
        seg = self._vSegmentStatus[segId]
#         if seg.status != SEGMENT_CACHED:
        if seg.status == SEGMENT_WORKING:
            self._vPendingRequestedSegments.setdefault(segId, {})[node] = ql
            return #don't need to bother
        if seg.status == SEGMENT_CACHED:
            req = self._vCatched[segId]
            time = self._rTransmissionTime(node, req.clen)
            self.runAfter(time, self._rSendToOtherPeer, node, req)
            return
        rtt = self._rGetRtt(node)
        self.runAfter(rtt, node._rPeerRequestFailed, segId, ql)

#=============================================
# server pending request to other peers
    def _rSendRequestedData(self, req):
        segId, clen = req.segId, req.clen
        rnodes = self._vPendingRequestedSegments.get(segId, {})

        for node in self._vGroup.getAllNode(self, self):
            assert node != self
            remSeg = node._vSegmentStatus[segId]
            if remSeg.status != SEGMENT_WORKING and remSeg.status != SEGMENT_CACHED:
                remSeg.status = SEGMENT_PEER_WAITING
#                 self._rSendToOtherPeer(node, *kw)
                time = self._rTransmissionTime(node, clen)
                self.runAfter(time, self._rSendToOtherPeer, node, req)
            if node in rnodes:
                del rnodes[node]
        for node in rnodes:
            rtt = self._rGetRtt(node)
            self.runAfter(rtt, node._rPeerRequestFailed, segId, rnodes[node])
        if len(rnodes):
            del self._vPendingRequestedSegments[segId]

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

def experimentGroupP2P(traces, vi, network):
    simulator = Simulator()
    grp = GroupManager(4, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []
    maxTime = 0
    for x, nodeId in enumerate(network.nodes()):
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        env = GroupP2PEnv(vi, trace, simulator, None, grp, nodeId)
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
    randstate.storeCurrentState() #comment this line to use same state as before
    randstate.loadCurrentState()
    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()

    experimentGroupP2P(traces, vi, network)

if __name__ == "__main__":
    for x in range(1):
        main()
        print("=========================\n")
