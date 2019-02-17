from envSimple import *
from group import GroupManager

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
        self._vPendingSelfSegment = {}
        self._vRequestedSegmentTo = {}

    def playerStartedCB(self, *kw, **kwa):
        if self._vGroup:
            self._vGroup.add(self, self._vAgent.nextSegmentIndex+2)
        self._vStarted = True

    def schedulesChanged(self, changedFrom):
        return
        for segId in range(changedFrom, self._vVideoInfo.segmentCount):
            if segId in self._vCatched:
                continue
            if segId == self._vSegmentDownloading and self._vDownloadPending:
                continue
            nextSegId, sleepTime = None, math.inf
            downloader = self._vGroup.currentSchedule(self, segId)
            if segId in self._vPendingSelfSegment:
                _, nq, sl, at = self._vPendingSelfSegment[segId]
                diff = now - at
                sl = 0 if diff > sl else sl - diff
                nextSegId, sleepTime = segId, sl
                del self._vPendingSelfSegment[segId]
                self._rDownloadNextData(nextSegId, nq, sleepTime)
                continue
            break



#=============================================
    def _rFetchSegment(self, nextSegId, nextQuality, sleepTime = 0.0):
        if self._vDead: return

        if self._vDownloadPending:
            if nextSegId == self._vAgent.nextSegmentIndex:
                self._vPendingSelfSegment[nextSegId] = (nextSegId, nextQuality, sleepTime, self.getNow())
#             print("Download pending for self", nextSegId, self._vAgent.nextSegmentIndex)
            return
#         if nextSegId > self._vAgent.nextSegmentIndex:
#             print("Early downloading", nextSegId, self._vAgent.nextSegmentIndex)
        if sleepTime == 0.0:
            self._rFetchNextSeg(nextSegId, nextQuality)
            self._vDownloadPending = True
            self._vSegmentDownloading = nextSegId
        else:
            assert sleepTime >= 0
#             nextFetchTime = self._vSimulator.getNow() + sleepTime
            self._vSimulator.runAfter(sleepTime, self._rFetchSegment, nextSegId, nextQuality)

#=============================================
    def _rFinish(self):
        print(self._vTraceFile)
        self._vAgent._rFinish()
        self._vFinished = True
        print("Downloaded:", self._vTotalDownloaded, "uploaded:", self._vTotalUploaded, \
                "ration U/D:", self._vTotalUploaded/self._vTotalDownloaded)

#=============================================
    def _rSendRequestedData(self, ql, timetaken, segDur, segIndex, clen, simIds = None, external = False):
        if self._vDead: return

        now = self._vSimulator.getNow()
        if segIndex in self._vOtherPeerRequest:
            for node in self._vOtherPeerRequest[segIndex]:
                if not self._vGroup.isNeighbour(self, node):
                    continue
                delay = self._vGroup.getRtt(self, node) # np.random.uniform(0.1, 0.5)
                self._vSimulator.runAt(now+delay, node._rAddToBuffer, ql, timetaken + delay, segDur, segIndex, clen, external = True)
                self._vTotalUploaded += clen
            del self._vOtherPeerRequest[segIndex]

#=============================================
    def _rAddToBuffer(self, ql, timetaken, segDur, segIndex, clen, simIds = None, external = False):
        if self._vDead: return

        self._rSendRequestedData(ql, timetaken, segDur, segIndex, clen, simIds, external)
        if segIndex not in self._vCatched:
            self._vCatched[segIndex] = (ql, timetaken, segDur, segIndex, clen, simIds, external) 

        if segIndex in self._vPendingSelfSegment:
            del self._vPendingSelfSegment[self._vAgent.nextSegmentIndex]

        if segIndex != self._vAgent.nextSegmentIndex:
#             if self._vAgent.nextSegmentIndex in self._vPendingSelfSegment:
#                 nextSegId, nextQuality, sleepTime, addedAt = self._vPendingSelfSegment[self._vAgent.nextSegmentIndex]
#                 diff = self.getNow() - addedAt
#                 sleepTime = 0 if diff >= sleepTime else sleepTime - diff
#                 self._rFetchSegment(nextSegId, nextQuality, sleepTime)
#                 del self._vPendingSelfSegment[self._vAgent.nextSegmentIndex]
            return
        if simIds and TIMEOUT_SIMID_KEY in simIds:
            self._vSimulator.cancelTask(simIds[TIMEOUT_SIMID_KEY])

        if not external:
            self._vDownloadPending = False
            self._vTotalDownloaded += clen
        self._vAgent._rAddToBufferInternal(ql, timetaken, segDur, segIndex, clen, simIds, external)

#=============================================
    def _rDownloadNextDataTimeout(self, nextSegId, nextQuality, sleepTime):
        if self._vDead: return

        if nextSegId in self._vCatched:
            return
        self._rDownloadNextData(self, nextSegId, nextQuality, sleepTime)

#=============================================
    def _rDownloadNextData(self, nextSegId, nextQuality, sleepTime):
        if self._vDead: return
        now = self.getNow()
        if nextSegId in self._vCatched:
            bitrate, timeTaken, segDur, segId, clen, simIds, external = self._vCatched[nextSegId]
            self._rAddToBuffer(bitrate, timeTaken, segDur, segId, clen, simIds, external)
            return
        if not self._vStarted:
            pass
        elif self._vGroup:
            downloader = self._vGroup.currentSchedule(self, nextSegId)
            if downloader == self:
                nextQuality = self._vGroup.getQualityLevel(self)
            elif downloader and downloader._rRequestSegment(self, nextSegId):
                
                self._vRequestedSegmentTo.setdefault(nextSegId, set()).add(downloader)
                while not self._vDownloadPending:
                    nextSegId += 1
                    if nextSegId >= self._vVideoInfo.segmentCount:
                        break
                    sl = self._vAgent._rIsAvailable(nextSegId)
                    downloader = self._vGroup.currentSchedule(self, nextSegId)
                    if downloader != self:
                        continue
                    if sl <= sleepTime:
                        self._rFetchSegment(nextSegId, nextQuality, 0)
                    break

                return
        else:
            raise Exception("No GroupManager")
        self._rFetchSegment(nextSegId, nextQuality, sleepTime)


#=============================================
    def _rRequestSegment(self, node, segId):
        if self._vDead: return

        now = self.getNow()

        if segId in self._vRequestedSegmentTo: return False
        if node in self._vRequestedSegmentTo.get(segId, set()): return False

        if segId in self._vCatched:
            bitrate, timeTaken, segDur, segId, clen, simIds, external = self._vCatched[segId]
            timeTaken = self._vGroup.transmissionTime(self, node, clen)#TODO arbit
            self._vSimulator.runAt(now + timeTaken, node._rAddToBuffer, bitrate, timeTaken, segDur, segId, clen, external = True)
            self._vTotalUploaded += clen
            return True

        otherPeers = self._vOtherPeerRequest.setdefault(segId, set())
        otherPeers.add(node)
        return True

#=============================================
    def start(self, startedAt = -1):
        super().start(startedAt)
        self._vAgent.addStartupCB(self.playerStartedCB)



def main():
#     np.random.seed(2301)
    simulator = Simulator()
    traces = load_trace.load_trace(COOCKED_TRACE_DIR)
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()
    grp = GroupManager(4, 7, vi, network)#np.random.randint(len(vi.bitrates)))
    ags = []
    for x, nodeId in enumerate(network.nodes()):
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        env = GroupP2PEnv(vi, trace, simulator, None, grp, nodeId)
#         env = SimpleEnviornment(vi, trace, simulator, BOLA)
        simulator.runAt(101.0 + x, env.start, 5)
        ags.append(env)
    simulator.run()
    for i,a in enumerate(ags):
        assert a._vFinished

if __name__ == "__main__":
    for x in range(1000):
        main()
        print("=========================\n")
