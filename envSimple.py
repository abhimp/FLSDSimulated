from agent import Agent
from simulator import Simulator
import load_trace
import videoInfo as video
import numpy as np
from abrBOLA import BOLA

COOCKED_TRACE_DIR = "./train_sim_traces/"
TIMEOUT_SIMID_KEY = "to"
REQUESTION_SIMID_KEY = "ri"

class SimpleEnviornment():
    def __init__(self, vi, traces, simulator, abr = None):
        self._vCookedTime, self._vCookedBW, self._vTraceFile = traces
        self._vLastBandwidthPtr = int(np.random.uniform(1, len(self._vCookedTime)))
        self._vAgent = Agent(vi, self, abr)
        self._vSimulator = simulator
        self._vDead = False
        self._vDownloadPending = False
        self._vVideoInfo = vi
        self._vFinished = False

    def addAgent(self, ag):
        self._vAgent = ag

    def getNow(self):
        return self._vSimulator.getNow()

    def finishedAfter(self, after):
        self._vSimulator.runAfter(after, self._rFinish)

    def runAfter(self, after, *kw, **kws):
        self._vSimulator.runAfter(after, *kw, **kws)

#=============================================
    def _rFinish(self):
        print(self._vTraceFile)
        self._vAgent._rFinish()
        self._vFinished = True
    

#=============================================
    def _rDownloadNextData(self, nextSegId, nextQuality, sleepTime, buflen):
        if self._vDead: return

        self._rFetchSegment(nextSegId, nextQuality, sleepTime)

#=============================================
    def start(self, startedAt = -1):
        if not self._vAgent:
            raise Exception("Node agent to start")
        self._vAgent.start(startedAt)

#=============================================
    def _rFetchSegment(self, nextSegId, nextQuality, sleepTime = 0.0):
        if self._vDead: return

        if self._vDownloadPending:
            print("Download pending for self", nextSegId, self._vAgent.nextSegmentIndex)
            return
        if nextSegId > self._vAgent.nextSegmentIndex:
            print("Early downloading", nextSegId, self._vAgent.nextSegmentIndex)
        if sleepTime == 0.0:
            self._rFetchNextSeg(nextSegId, nextQuality)
        else:
            assert sleepTime >= 0
#             nextFetchTime = self._vSimulator.getNow() + sleepTime
            self._vSimulator.runAfter(sleepTime, self._rFetchNextSeg, nextSegId, nextQuality, sleepTime)
        self._vDownloadPending = True

#=============================================
    def _rAddToBuffer(self, ql, timetaken, segDur, segIndex, clen, simIds = None, external = False):
        if self._vDead: return

        self._vDownloadPending = False

        self._vAgent._rAddToBufferInternal(ql, timetaken, segDur, segIndex, clen, simIds, external)

#=============================================
    def _rFetchNextSeg(self, nextSegId, nextQuality, sleepTime = 0, ignoreGroup = False):
        if self._vDead: return

        now = self._vSimulator.getNow()
        simIds = {}

        nextDur = self._vVideoInfo.duration - self._vAgent.bufferUpto
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
        simIds[REQUESTION_SIMID_KEY] = self._vSimulator.runAt(now + time, self._rAddToBuffer, nextQuality, time, nextDur, nextSegId, chsize, simIds)


#=============================================
def main():
#     np.random.seed(2300)
    simulator = Simulator()
    traces = load_trace.load_trace(COOCKED_TRACE_DIR)
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    ags = []
    for x in range(5):
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        env = SimpleEnviornment(vi, trace, simulator, BOLA)
        simulator.runAt(101.0 + x, env.start, 5)
        ags.append(env)
    simulator.run()
    for i,a in enumerate(ags):
        assert a._vFinished

if __name__ == "__main__":
    for x in range(1):
        main()
        print("=========================\n")
