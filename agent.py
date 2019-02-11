from simulator import Simulator
# import random
import load_trace
import numpy as np
import videoInfo as video



COOCKED_TRACE_DIR = "./train_sim_traces/"
TIMEOUT_SIMID_KEY = "to"
REQUESTION_SIMID_KEY = "ri"
PLAYBACK_DELAY_THRESHOLD = 4
# np.random.seed(2300)

class Agent():
    def __init__(self, videoInfo, simulator, traces = None):
        self._videoInfo = videoInfo
        self._simulator = simulator
        self._currentBitrateIndex = 0
        self._nextSegmentIndex = 0
        self._playbacktime = 0.0
        self._bufferUpto = 0
        self._paused = True
        self._lastEventTime = simulator.getNow()
        self._totalStallTime = 0
        self._stallsAt = []
        self._cookedTime, self._cookedBW, self._traceFile = traces
        self._lastBandwidthPtr = int(np.random.uniform(1, len(self._cookedTime)))
        self._startUpDelay = 0.0
        self._qualitiesPlayed = []
        self._startedAt = -1
        self._globalStartedAt = -1
        self._canSkip = False #in case of live playback can be skipped
        self._isStarted = 0
        self._playerBufferLen = 50
        self._timeouts = []
        self._requests = [] #7-tuple throughput, timetaken, bytes/clen, startingTime, segIndex, segDur, bitrate

    def nextQuality(self, ql, timetaken, segDur, segIndex, clen):
        assert segIndex == self._nextSegmentIndex
        totaldata = clen
        throughput = float(totaldata)/timetaken*8
        startingTime = self._simulator.getNow() - timetaken
        self._requests.append((throughput, timetaken, clen, \
                startingTime, segIndex, segDur, ql))

        _, times, clens = list(zip(*self._requests))[:3] 
        avg = sum(clens)*8/sum(times)
        level = 0
        for ql, q in enumerate(self._videoInfo.bitrates):
            if q > avg:
                break
            level = ql
        self._currentBitrateIndex = level


    def addToBuffer(self, ql, timetaken, segDur, segIndex, clen, simIds = None):
        if simIds and TIMEOUT_SIMID_KEY in simIds:
            self._simulator.cancelTask(simIds[TIMEOUT_SIMID_KEY])
        self.nextQuality(ql, timetaken, segDur, segIndex, clen)

        now = self._simulator.getNow()
        segPlaybackStartTime = segIndex * self._videoInfo.segmentDuration
        segPlaybackEndTime = segPlaybackStartTime + segDur

        timeSpent = now - self._lastEventTime
        self._lastEventTime = now
        stallTime = 0
        playbackTime = self._playbacktime + timeSpent
        if playbackTime > self._bufferUpto:
            stallTime = playbackTime - self._bufferUpto
            playbackTime = self._bufferUpto

        if not self._isStarted:
            expectedPlaybackTime = 0
            startUpDelay = now - self._startedAt
            stallTime = 0
            playbackTime = segPlaybackStartTime
            bufferUpto = segPlaybackEndTime
            if self._globalStartedAt != self._startedAt:
                expectedPlaybackTime = now - self._globalStartedAt

            if  self._canSkip and expectedPlaybackTime + PLAYBACK_DELAY_THRESHOLD > segPlaybackEndTime:
                #need to skip this segment
                self._nextSegmentIndex += 1
                self.fetchNextSeg()
                return

            self._isStarted = True
            self._startUpDelay = startUpDelay


        if stallTime > 0:
            assert playbackTime > 0
            self._stallsAt.append((playbackTime, stallTime, ql))
            self._totalStallTime += stallTime
        self._bufferUpto = segPlaybackEndTime
        self._playbacktime = playbackTime

        buflen = self._bufferUpto - self._playbacktime
        self._qualitiesPlayed.append(ql)
        self._nextSegmentIndex += 1
        if self._nextSegmentIndex == len(self._videoInfo.fileSizes[0]):
            self._simulator.runAt(self._bufferUpto, self.finish)
            return

        if (self._playerBufferLen - self._videoInfo.segmentDuration) > buflen:
            self.fetchNextSeg()
        else:
            sleepTime = buflen + self._videoInfo.segmentDuration - self._playerBufferLen
            assert sleepTime >= 0
            nextFetchTime = now + sleepTime
            self._simulator.runAt(nextFetchTime, self.fetchNextSeg, sleepTime)

    def timeoutEvent(self, simIds, lastBandwidthPtr, sleepTime):
        if simIds != None and REQUESTION_SIMID_KEY in simIds:
            self._simulator.cancelTask(simIds[REQUESTION_SIMID_KEY])
        
        self._lastBandwidthPtr = lastBandwidthPtr
        self._timeouts.append((self._nextSegmentIndex, self._currentBitrateIndex))
        self._currentBitrateIndex = 0
        self.fetchNextSeg(sleepTime)

    def getTimeOutTime(self):
        timeout = self._videoInfo.segmentDuration
        bufLeft = self._bufferUpto - self._playbacktime
        if bufLeft - timeout > timeout:
            timeout = bufLeft - timeout
        return timeout

    def fetchNextSeg(self, sleepTime = 0):
        now = self._simulator.getNow()
        simIds = {}
        if self._currentBitrateIndex > 0:
            timeout = self.getTimeOutTime() #TODO
            simIds[TIMEOUT_SIMID_KEY] = self._simulator.runAt(now + timeout, self.timeoutEvent, simIds, self._lastBandwidthPtr, sleepTime+timeout)
        nextDur = self._videoInfo.duration - self._bufferUpto
        if nextDur >= self._videoInfo.segmentDuration:
            nextDur = self._videoInfo.segmentDuration
        chsize = self._videoInfo.fileSizes[self._currentBitrateIndex][self._nextSegmentIndex]
        time = 0
        sentSize = 0
        lastTime = self._cookedTime[self._lastBandwidthPtr - 1] + sleepTime
        while lastTime > self._cookedTime[self._lastBandwidthPtr]:
            self._lastBandwidthPtr += 1
            if self._lastBandwidthPtr == len(self._cookedTime):
                self._lastBandwidthPtr = 1
                lastTime = 0

        while True:
            self._lastBandwidthPtr += 1
            if self._lastBandwidthPtr >= len(self._cookedTime):
                self._lastBandwidthPtr = 1
            throughput = self._cookedBW[self._lastBandwidthPtr]
            dur = self._cookedTime[self._lastBandwidthPtr] - self._cookedTime[self._lastBandwidthPtr - 1]
            pktpyld = throughput * (1024 * 1024 / 8) * dur * 0.95
            if sentSize + pktpyld >= chsize:
                fracTime = dur * ( chsize - sentSize ) / pktpyld
                time += fracTime
                break

            time += dur
            sentSize += pktpyld

        time += 0.08 #delay
        time *= np.random.uniform(0.9, 1.1)
        simIds[REQUESTION_SIMID_KEY] = self._simulator.runAt(now + time, self.addToBuffer, self._currentBitrateIndex, time, nextDur, self._nextSegmentIndex, chsize, simIds)
        
        #self._pendingRequests[self._nextSegmentIndex] = reqId

    def finish(self):
        print(self._traceFile)
        print("Simulation finished at:", self._simulator.getNow(), "totalStallTime:", self._totalStallTime, "startUpDelay:", self._startUpDelay)
        print("Stall details:", self._stallsAt)
        print("qualitiesPlayed:", self._qualitiesPlayed)
        print("timeouts:", self._timeouts)

    def start(self, startedAt = -1):
        segId = self._nextSegmentIndex
        now = self._simulator.getNow()
        self._startedAt = self._globalStartedAt = now
        if startedAt >= 0:
            playbackTime = now - startedAt
            self._nextSegmentIndex = int(playbackTime*1./self._videoInfo.segmentDuration)
            while (self._nextSegmentIndex + 1) * self._videoInfo.segmentDuration < playbackTime + PLAYBACK_DELAY_THRESHOLD:
                self._nextSegmentIndex += 1
            self._canSkip = True
            self._globalStartedAt = startedAt

        self._lastEventTime = self._simulator.getNow()
        self.fetchNextSeg()

def main():
    simulator = Simulator()
    traces = load_trace.load_trace(COOCKED_TRACE_DIR)
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    for x in range(8):
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        ag = Agent(vi, simulator, trace)
        simulator.runAt(101.0 + 100*x, ag.start, 5)
#         break
    simulator.run()

if __name__ == "__main__":
    main()
