from agent import Agent
from simulator import Simulator
import load_trace
import videoInfo as video
import numpy as np
from abrBOLA import BOLA

from p2pnetwork import P2PNetwork
from segmentRequest import SegmentRequest

TIMEOUT_SIMID_KEY = "to"
REQUESTION_SIMID_KEY = "ri"

class SimpleEnvironment():
    def __init__(self, vi, traces, simulator, abr = None, peerId = None):
        self._vCookedTime, self._vCookedBW, self._vTraceFile = traces
        self._vLastBandwidthPtr = int(np.random.uniform(1, len(self._vCookedTime)))
#         self._vLastBandwidthTime = 
        self._vAgent = Agent(vi, self, abr)
        self._vSimulator = simulator
        self._vDead = False
        self._vVideoInfo = vi
        self._vFinished = False
        self._vConnectionSpeed = np.mean(self._vCookedBW)
        self._vLastDownloadedAt = 0
        self._vPeerId = peerId if peerId else np.random.randint(1000000)
        self._vIdleTimes = []
        self._vWorkingTimes = []
        self._vTotalIdleTime = 0
        self._vTotalWorkingTime = 0
        self._lastThrougput = 0
        
        self._vWorking = False
        self._vWorkingStatus = None

    @property
    def networkId(self):
        return self._vPeerId

    @property
    def connectionSpeed(self):
        return self._vConnectionSpeed

    @property
    def connectionSpeedBPS(self):
        return self._vConnectionSpeed * 1000000

    @property
    def idleTime(self):
        return self._vTotalIdleTime

    @property
    def totalWorkingTime(self):
        return self._vTotalWorkingTime

    def addAgent(self, ag):
        self._vAgent = ag

    def getNow(self):
        return self._vSimulator.getNow()

    def finishedAfter(self, after):
        self._vSimulator.runAfter(after, self._rFinish)

    def runAfter(self, after, *kw, **kws):
        return self._vSimulator.runAfter(after, *kw, **kws)

#=============================================
    def _rFinish(self):
        print(self._vTraceFile)
        self._vAgent._rFinish()
        self._vFinished = True

#=============================================
    def _rDownloadNextData(self, nextSegId, nextQuality, sleepTime):
        if self._vDead: return

        self._rFetchSegment(nextSegId, nextQuality, sleepTime)

#=============================================
    def start(self, startedAt = -1):
        if not self._vAgent:
            raise Exception("Node agent to start")
        self._vLastDownloadedAt = self.getNow()
        self._vAgent.start(startedAt)

#=============================================
    def _rFetchSegment(self, nextSegId, nextQuality, sleepTime = 0.0):
        if self._vDead: return
        assert sleepTime >= 0
        assert nextSegId < self._vVideoInfo.segmentCount
        self._vSimulator.runAfter(sleepTime, self._rFetchNextSeg, nextSegId, nextQuality)

#=============================================
    def _rAddToBuffer(self, req, simIds = None):
        if self._vDead: return
        self._vAgent._rAddToBufferInternal(req, simIds)

#=============================================
    def _rFetchNextSeg(self, nextSegId, nextQuality):
        if self._vDead: return

        assert not self._vWorking
        self._vWorking = True

        now = self._vSimulator.getNow()
        sleepTime = now - self._vLastDownloadedAt
        simIds = {}

        idleTime = round(sleepTime, 3)
        self._vIdleTimes += [(now, 0)]
        if idleTime > 0:
            self._vTotalIdleTime += idleTime
            self._vWorkingTimes += [(now, 0, nextSegId)]

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

        downloadData = [[0, 0]]
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
                if fracTime > 0:
                    downloadData += [[time, chsize]]
                break
            time += dur
            sentSize += pktpyld
            downloadData += [[time, sentSize]] #I may not use it now

        time += 0.08 #delay
        time *= np.random.uniform(0.9, 1.1)
        timeChangeRatio = time/downloadData[-1][0]

        downloadData = [[round(x[0]*timeChangeRatio, 3), x[1]] for x in downloadData]

        simIds[REQUESTION_SIMID_KEY] = self._vSimulator.runAfter(time, self._rFetchNextSegReturn, nextQuality, now, nextDur, nextSegId, chsize, simIds)
        self._vWorkingStatus = (now, time, nextSegId, chsize, downloadData, simIds)
                #useful to calculate downloaded data 

#=============================================
    def _rFetchNextSegReturn(self, ql, startedAt, dur, segId, chsize, simIds):
        assert self._vWorking
        self._vWorking = False
        self._vWorkingStatus = None

        now = self._vSimulator.getNow()
        self._vIdleTimes += [(now, 25)]
        time = now - startedAt
        self._vLastDownloadedAt = now
        self._vTotalWorkingTime += time
        req = SegmentRequest(ql, startedAt, now, dur, segId, chsize, self)
        self._vWorkingTimes += [(now, req.throughput, segId)]
        self._rAddToBuffer(req, simIds)

#=============================================
    def _rDownloadStatus(self):
        assert self._vWorking
        now = self.getNow()
        startedAt, dur, segId, chsize, downloadData, simIds = self._vWorkingStatus 
        timeElapsed = now - startedAt
        downLoadedTillNow = 0
        for i,x in enumerate(downloadData):
            t,s = x
            if t == timeElapsed:
                downLoadedTillNow = s
                break
            if t < timeElapsed:
                assert i < len(downloadData) - 1
                slt = downloadData[i + 1][0] - t #slot duration
                amt = downloadData[i + 1][1] - s #downloaded in the slot
                sltSpent = timeElapsed - t

                downLoadedTillNow = round(s + amt*sltSpent/slt, 3)
                break
        return round(timeElapsed, 3), round(downLoadedTillNow), chsize

#=============================================
def experimentSimpleEnv(traces, vi, network, abr = None):
    simulator = Simulator()
    ags = []
    for x, nodeId in enumerate(network.nodes()):
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        env = SimpleEnvironment(vi, trace, simulator, abr)
        simulator.runAt(101.0 + x, env.start, 5)
        ags.append(env)
    simulator.run()
    for i,a in enumerate(ags):
        assert a._vFinished
    return ags


#=============================================
def main():
#     np.random.seed(2300)
    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()
    experimentSimpleEnv(traces, vi, network)

if __name__ == "__main__":
    for x in range(1):
        main()
        print("=========================\n")
