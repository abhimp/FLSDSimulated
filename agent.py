from simulator import Simulator
# import random
import load_trace
import numpy as np
import videoInfo as video
import math
import numpy as np
from abrBOLA import BOLA

COOCKED_TRACE_DIR = "./train_sim_traces/"
TIMEOUT_SIMID_KEY = "to"
REQUESTION_SIMID_KEY = "ri"
PLAYBACK_DELAY_THRESHOLD = 4
# np.random.seed(2300)
class Agent():
    def __init__(self, videoInfo, simulator, traces = None, setQuality = None):
        self._vVideoInfo = videoInfo
        self._vSimulator = simulator
        self._vCurrentBitrateIndex = 0
        self._vNextSegmentIndex = 0
        self._vPlaybacktime = 0.0
        self._vBufferUpto = 0
#         self._vPaused = True
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

    def _rWhenToDownload(self, *kw):
        buflen = self._vBufferUpto - self._vPlaybacktime
        if (self._vMaxPlayerBufferLen - self._vVideoInfo.segmentDuration) > buflen:
            return 0, self._vCurrentBitrateIndex
        sleepTime = buflen + self._vVideoInfo.segmentDuration - self._vMaxPlayerBufferLen
        return sleepTime, self._vCurrentBitrateIndex

    def _rAddToBuffer(self, ql, timetaken, segDur, segIndex, clen, simIds = None):
        assert segIndex == self._vNextSegmentIndex
        if simIds and TIMEOUT_SIMID_KEY in simIds:
            self._vSimulator.cancelTask(simIds[TIMEOUT_SIMID_KEY])
        self._rNextQuality(ql, timetaken, segDur, segIndex, clen)

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
                self._rFetchNextSeg()
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

        #maxBufLen, bufferUpto, playbackTime, now, segId
        sleepTime, nextQuality = self._vSetQuality(self._vMaxPlayerBufferLen, \
                self._vBufferUpto, self._vPlaybacktime, now, self._vNextSegmentIndex)
        self._vCurrentBitrateIndex = nextQuality
        if sleepTime == 0.0:
            self._rFetchNextSeg()
        else:
            assert sleepTime >= 0
            nextFetchTime = now + sleepTime
            self._vSimulator.runAt(nextFetchTime, self._rFetchNextSeg, sleepTime)

    def _rTimeoutEvent(self, simIds, lastBandwidthPtr, sleepTime):
        if simIds != None and REQUESTION_SIMID_KEY in simIds:
            self._vSimulator.cancelTask(simIds[REQUESTION_SIMID_KEY])

        self._vLastBandwidthPtr = lastBandwidthPtr
        self._vTimeouts.append((self._vNextSegmentIndex, self._vCurrentBitrateIndex))
        self._vCurrentBitrateIndex = 0
        self._rFetchNextSeg(sleepTime)

    def _rGetTimeOutTime(self):
        timeout = self._vVideoInfo.segmentDuration
        bufLeft = self._vBufferUpto - self._vPlaybacktime
        if bufLeft - timeout > timeout:
            timeout = bufLeft - timeout
        return timeout

    def _rFetchNextSeg(self, sleepTime = 0):
        now = self._vSimulator.getNow()
        simIds = {}
        if self._vCurrentBitrateIndex > 0:
            timeout = self._rGetTimeOutTime() #TODO
            simIds[TIMEOUT_SIMID_KEY] = self._vSimulator.runAt(now + timeout, self._rTimeoutEvent, simIds, self._vLastBandwidthPtr, sleepTime+timeout)
        nextDur = self._vVideoInfo.duration - self._vBufferUpto
        if nextDur >= self._vVideoInfo.segmentDuration:
            nextDur = self._vVideoInfo.segmentDuration
        chsize = self._vVideoInfo.fileSizes[self._vCurrentBitrateIndex][self._vNextSegmentIndex]
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
        simIds[REQUESTION_SIMID_KEY] = self._vSimulator.runAt(now + time, self._rAddToBuffer, self._vCurrentBitrateIndex, time, nextDur, self._vNextSegmentIndex, chsize, simIds)

        #self._vPendingRequests[self._vNextSegmentIndex] = reqId

    def _rFinish(self):
        print(self._vTraceFile)
        print("Simulation finished at:", self._vSimulator.getNow(), "totalStallTime:", self._vTotalStallTime, "startUpDelay:", self._vStartUpDelay)
        print("Stall details:", self._vStallsAt)
        print("qualitiesPlayed:", self._vQualitiesPlayed)
        print("timeouts:", self._vTimeouts)

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

        self._vLastEventTime = self._vSimulator.getNow()
        self._rFetchNextSeg()

def main():
    simulator = Simulator()
    traces = load_trace.load_trace(COOCKED_TRACE_DIR)
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    for x in range(800):
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        bola = BOLA(vi)
        ag = Agent(vi, simulator, trace, bola)
        bola.init(ag)
        simulator.runAt(101.0 + x, ag.start, 5)
#         break
    simulator.run()

if __name__ == "__main__":
    main()
