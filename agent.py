from simulator import Simulator
import random
import load_trace
import videoInfo as video
import math
import numpy as np
from abrBOLA import BOLA
from group import Group

COOCKED_TRACE_DIR = "./train_sim_traces/"
TIMEOUT_SIMID_KEY = "to"
REQUESTION_SIMID_KEY = "ri"
PLAYBACK_DELAY_THRESHOLD = 4
GLOBAL_DELAY_PLAYBACK = 50 #Total arbit

class Agent():
    __count = 0
    def __init__(self, videoInfo, simulator, traces = None, setQuality = None, grp = None):
        self._id = self.__count
        self.__count += 1
        self._vVideoInfo = videoInfo
        self._vSimulator = simulator
        self._vCurrentBitrateIndex = 0
        self._vNextSegmentIndex = 0
        self._vPlaybacktime = 0.0
        self._vBufferUpto = 0
        self._vLastEventTime = simulator.getNow()
        self._vTotalStallTime = 0
        self._vStallsAt = []
        self._vCookedTime, self._vCookedBW, self._vTraceFile = traces
        self._vLastBandwidthPtr = int(np.random.uniform(1, len(self._vCookedTime)))
        self._vStartUpDelay = 0.0
        self._vQualitiesPlayed = []
        self._vStartedAt = -1
        self._vGlobalStartedAt = -1
        self._vCanSkip = False #in case of live playback can be skipped
        self._vIsStarted = 0
        self._vMaxPlayerBufferLen = 50
        self._vTimeouts = []
        self._vRequests = [] #7-tuple throughput, timetaken, bytes/clen, startingTime, segIndex, segDur, bitrate
        self._vSetQuality = setQuality.getNextDownloadTime if setQuality else self._rWhenToDownload
        self._vStartingPlaybackTime = 0
        self._vStartingSegId = 0
        self._vTotalUploaded = 0
        self._vTotalDownloaded = 0
        self._vGroup = grp
        self._vFinished = False
        self._vCatched = {}
        self._vPendingRequests = set()
        self._vOtherPeerRequest = {}
        self._vDownloadPending = False

#=============================================
    def _rNextQuality(self, ql, timetaken, segDur, segIndex, clen):
        assert segIndex == self._vNextSegmentIndex
        totaldata = clen
        throughput = float(totaldata)/timetaken*8
        startingTime = self._vSimulator.getNow() - timetaken
        self._vRequests.append((throughput, timetaken, clen, \
                startingTime, segIndex, segDur, ql))

        _, times, clens = list(zip(*self._vRequests))[:3]
        avg = sum(clens)*8/sum(times)
        level = 0
        for ql, q in enumerate(self._vVideoInfo.bitrates):
            if q > avg:
                break
            level = ql
        self._vCurrentBitrateIndex = level

#=============================================
    def _rWhenToDownload(self, *kw):
        buflen = self._vBufferUpto - self._vPlaybacktime
        if (self._vMaxPlayerBufferLen - self._vVideoInfo.segmentDuration) > buflen:
            return 0, self._vCurrentBitrateIndex
        sleepTime = buflen + self._vVideoInfo.segmentDuration - self._vMaxPlayerBufferLen
        return sleepTime, self._vCurrentBitrateIndex

#=============================================
    def _rSendRequestedData(self, ql, timetaken, segDur, segIndex, clen, simIds = None, external = False):
        now = self._vSimulator.getNow()
        if segIndex in self._vOtherPeerRequest:
            for node in self._vOtherPeerRequest[segIndex]:
                delay = np.random.uniform(0.1, 0.5)
                self._vSimulator.runAt(now+delay, node._rAddToBuffer, ql, timetaken + delay, segDur, segIndex, clen, external = True)
                self._vTotalUploaded += clen
            del self._vOtherPeerRequest[segIndex]


#=============================================
    def _rAddToBuffer(self, ql, timetaken, segDur, segIndex, clen, simIds = None, external = False):
        self._rSendRequestedData(ql, timetaken, segDur, segIndex, clen, simIds, external)
#         assert segIndex not in self._vCatched
        if segIndex not in self._vCatched:
            self._vCatched[segIndex] = (ql, timetaken, segDur, segIndex, clen, simIds, external) 
#         assert segIndex == self._vNextSegmentIndex
        if segIndex != self._vNextSegmentIndex:
            return
        if simIds and TIMEOUT_SIMID_KEY in simIds:
            self._vSimulator.cancelTask(simIds[TIMEOUT_SIMID_KEY])

        if not external:
            self._rNextQuality(ql, timetaken, segDur, segIndex, clen)
            self._vDownloadPending = False
            self._vTotalDownloaded += clen

        now = self._vSimulator.getNow()
        segPlaybackStartTime = segIndex * self._vVideoInfo.segmentDuration
        segPlaybackEndTime = segPlaybackStartTime + segDur

        timeSpent = now - self._vLastEventTime
        self._vLastEventTime = now
        stallTime = 0
        playbackTime = self._vPlaybacktime + timeSpent
        if playbackTime > self._vBufferUpto:
            stallTime = playbackTime - self._vBufferUpto
            playbackTime = self._vBufferUpto

        if not self._vIsStarted:
            expectedPlaybackTime = 0
            startUpDelay = now - self._vStartedAt
            stallTime = 0
            playbackTime = segPlaybackStartTime
            bufferUpto = segPlaybackEndTime
            if self._vGlobalStartedAt != self._vStartedAt:
                expectedPlaybackTime = now - self._vGlobalStartedAt

            if  self._vCanSkip and expectedPlaybackTime + PLAYBACK_DELAY_THRESHOLD > segPlaybackEndTime:
                #need to skip this segment
                self._vNextSegmentIndex += 1
                self._rFetchSegment(self._vNextSegmentIndex, self._vCurrentBitrateIndex)
                return

            self._vIsStarted = True
            self._vStartingPlaybackTime = playbackTime
            self._vStartingSegId = segIndex
            self._vStartUpDelay = startUpDelay


        if stallTime > 0:
            assert playbackTime > 0
            self._vStallsAt.append((playbackTime, stallTime, ql))
            self._vTotalStallTime += stallTime
        self._vBufferUpto = segPlaybackEndTime
        self._vPlaybacktime = playbackTime

        buflen = self._vBufferUpto - self._vPlaybacktime
        self._vQualitiesPlayed.append(ql)
        self._vNextSegmentIndex += 1
        if self._vNextSegmentIndex == len(self._vVideoInfo.fileSizes[0]):
            self._vSimulator.runAt(self._vBufferUpto, self._rFinish)
            return
        self._rDownloadNextData(buflen)

#=============================================
    def _rDownloadNextData(self, buflen):
        now = self._vSimulator.getNow()
        nextSegId = self._vNextSegmentIndex
        nextQuality = self._vCurrentBitrateIndex
        if nextSegId in self._vCatched:
            bitrate, timeTaken, segDur, segId, clen, simIds, external = self._vCatched[nextSegId]
            self._rAddToBuffer(bitrate, timeTaken, segDur, segId, clen, simIds, external)
            return
        sleepTime = 0 if buflen < (self._vMaxPlayerBufferLen - self._vVideoInfo.segmentDuration) else(buflen + self._vVideoInfo.segmentDuration - self._vMaxPlayerBufferLen)
        if self._vGroup:
            downloader = self._vGroup.currentSchedule(self, nextSegId)
            if downloader == self:
                nextQuality = self._vGroup.qualityLevel
            elif downloader:
                downloader._rRequestSegment(self, nextSegId)
                while not self._vDownloadPending:
                    nextSegId += 1
                    if nextSegId >= self._vVideoInfo.segmentCount:
                        break
                    sl = self._rIsAvailable(nextSegId)
                    downloader = self._vGroup.currentSchedule(self, nextSegId)
                    if downloader != self:
                        continue
                    if sl >= 0:
                        self._rFetchSegment(nextSegId, nextQuality, sl)
                    break

                return
        else:
            sleepTime, nextQuality = self._vSetQuality(self._vMaxPlayerBufferLen, \
                self._vBufferUpto, self._vPlaybacktime, now, self._vNextSegmentIndex)
        self._vCurrentBitrateIndex = nextQuality
        self._rFetchSegment(nextSegId, nextQuality, sleepTime)

#=============================================
    def _rTimeoutEvent(self, simIds, lastBandwidthPtr, sleepTime):
        if simIds != None and REQUESTION_SIMID_KEY in simIds:
            self._vSimulator.cancelTask(simIds[REQUESTION_SIMID_KEY])

        self._vLastBandwidthPtr = lastBandwidthPtr
        self._vTimeouts.append((self._vNextSegmentIndex, self._vCurrentBitrateIndex))
        self._vCurrentBitrateIndex = 0
        self._rFetchSegment(self._vNextSegmentIndex, self._vCurrentBitrateIndex, sleepTime)

    def _rFetchSegment(self, nextSegId, nextQuality, sleepTime = 0.0):
        if self._vDownloadPending:
            print("Download pending for self")
            return
        if sleepTime == 0.0:
            self._rFetchNextSeg(nextSegId, nextQuality)
        else:
            assert sleepTime >= 0
            nextFetchTime = self._vSimulator.getNow() + sleepTime
            self._vSimulator.runAt(nextFetchTime, self._rFetchNextSeg, nextSegId, nextQuality, sleepTime)
        

#=============================================
    def _rGetTimeOutTime(self):
        timeout = self._vVideoInfo.segmentDuration
        bufLeft = self._vBufferUpto - self._vPlaybacktime
        if bufLeft - timeout > timeout:
            timeout = bufLeft - timeout
        return timeout

#=============================================
    def _rIsAvailable(self, segId):
        assert segId < self._vVideoInfo.segmentCount
        now = self._vSimulator.getNow()
        ePlaybackTime = now - self._vGlobalStartedAt
        segStartTime = (segId+1)*self._vVideoInfo.segmentDuration
        return ePlaybackTime + GLOBAL_DELAY_PLAYBACK - segStartTime

#=============================================
    def _rRequestSegment(self, node, segId):
        now = self._vSimulator.getNow()

        if segId in self._vCatched:
            bitrate, timeTaken, segDur, segId, clen, simIds, external = self._vCatched[segId]
            timeTaken = 5 #TODO arbit
            self._vSimulator.runAt(now + timeTaken, node._rAddToBuffer, bitrate, timeTaken, segDur, segId, clen, external = True)
            self._vTotalUploaded += clen
            return True

        otherPeers = self._vOtherPeerRequest.setdefault(segId, [])
        otherPeers.append(node)
        return True

#=============================================
    def _rFetchNextSeg(self, nextSegId, nextQuality, sleepTime = 0, ignoreGroup = False):
        now = self._vSimulator.getNow()
        simIds = {}

        nextDur = self._vVideoInfo.duration - self._vBufferUpto
        if nextDur >= self._vVideoInfo.segmentDuration:
            nextDur = self._vVideoInfo.segmentDuration
        chsize = self._vVideoInfo.fileSizes[nextQuality][nextSegId]
        time = 0
        sentSize = 0
        lastTime = self._vCookedTime[self._vLastBandwidthPtr - 1] + sleepTime
        while lastTime > self._vCookedTime[self._vLastBandwidthPtr]:
            self._vLastBandwidthPtr += 1
            if self._vLastBandwidthPtr == len(self._vCookedTime):
                self._vLastBandwidthPtr = 1
                lastTime = 0

        while True:
            self._vLastBandwidthPtr += 1
            if self._vLastBandwidthPtr >= len(self._vCookedTime):
                self._vLastBandwidthPtr = 1
            throughput = self._vCookedBW[self._vLastBandwidthPtr]
            dur = self._vCookedTime[self._vLastBandwidthPtr] - self._vCookedTime[self._vLastBandwidthPtr - 1]
            pktpyld = throughput * (1024 * 1024 / 8) * dur * 0.95
            if sentSize + pktpyld >= chsize:
                fracTime = dur * ( chsize - sentSize ) / pktpyld
                time += fracTime
                break
            time += dur
            sentSize += pktpyld

        time += 0.08 #delay
        time *= np.random.uniform(0.9, 1.1)
        simIds[REQUESTION_SIMID_KEY] = self._vSimulator.runAt(now + time, self._rAddToBuffer, self._vCurrentBitrateIndex, time, nextDur, nextSegId, chsize, simIds)
        self._vPendingRequests.add(nextSegId)

#=============================================
    def _rCalculateQoE(self):
        lmbda = 1
        mu = 4.3
        mu_s = 1 
        rmin = self._vVideoInfo.bitrates[0]
        bitratePlayed = [self._vVideoInfo.bitrates[x] for x in self._vQualitiesPlayed]
        bitratePlayed = [math.log(self._vVideoInfo.bitrates[x]/rmin) for x in self._vQualitiesPlayed]
        bitratePlayed = self._vQualitiesPlayed
        avgQuality = float(sum(bitratePlayed))/len(bitratePlayed)
        avgQualityVariation = [abs(bt - bitratePlayed[x - 1]) for x,bt in enumerate(bitratePlayed) if x > 0]
        avgQualityVariation = 0 if len(avgQualityVariation) == 0 else sum(avgQualityVariation)/float(len(avgQualityVariation))

        QoE = avgQuality - lmbda * avgQualityVariation - mu * self._vTotalStallTime - mu_s * self._vStartUpDelay
        return QoE

#=============================================
    def _rFinish(self):
        self._vFinished = True
        print(self._vTraceFile)
        print("Simulation finished at:", self._vSimulator.getNow(), "totalStallTime:", self._vTotalStallTime, "startUpDelay:", self._vStartUpDelay)
        print("QoE:", self._rCalculateQoE())
#         print("Quality played:", self._vQualitiesPlayed)
        print("Downloaded:", self._vTotalDownloaded, "uploaded:", self._vTotalUploaded, \
                "ration D/U:", self._vTotalDownloaded/self._vTotalUploaded)

    def start(self, startedAt = -1):
        segId = self._vNextSegmentIndex
        now = self._vSimulator.getNow()
        self._vStartedAt = self._vGlobalStartedAt = now
        if startedAt >= 0:
            playbackTime = now - startedAt
            self._vNextSegmentIndex = int(playbackTime*1./self._vVideoInfo.segmentDuration)
            while (self._vNextSegmentIndex + 1) * self._vVideoInfo.segmentDuration < playbackTime + PLAYBACK_DELAY_THRESHOLD:
                self._vNextSegmentIndex += 1
            self._vCanSkip = True
            self._vGlobalStartedAt = startedAt

        if self._vGroup:
            self._vGroup.add(self, self._vNextSegmentIndex+2)
        self._vLastEventTime = self._vSimulator.getNow()
        self._rFetchSegment(self._vNextSegmentIndex, self._vCurrentBitrateIndex)

#=============================================
def main():
#     np.random.seed(2300)
    simulator = Simulator()
    traces = load_trace.load_trace(COOCKED_TRACE_DIR)
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    grp = Group(5)#np.random.randint(len(vi.bitrates)))
    ags = []
    for x in range(5):
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        bola = BOLA(vi)
        ag = Agent(vi, simulator, trace, bola, grp)
        bola.init(ag)
        simulator.runAt(101.0 + x, ag.start, 5)
        ags.append(ag)
#         break
    simulator.run()
    for i,a in enumerate(ags):
        assert a._vFinished

if __name__ == "__main__":
    for x in range(1):
        main()
        print("=========================\n")
