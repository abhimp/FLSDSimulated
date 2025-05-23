import numpy as np
from util.myprint import myprint

from util.agent import Agent
from simulator.simulator import Simulator
from util import load_trace
import util.videoInfo as video
from abr.BOLA import BOLA
from util.p2pnetwork import P2PNetwork
from util.segmentRequest import SegmentRequest
from util.cdnUsages import CDN

TIMEOUT_SIMID_KEY = "to"
REQUESTION_SIMID_KEY = "ri"

class TraceComputation():
    def __init__(self, startTime, bwtrace, tmtrace):
        self.startedAt = startTime
        self.bw = bwtrace
        self.ttime = tmtrace
        assert self.ttime[0] == 0
        self.bw[0] = self.bw[-1]

    def getDLTime(self, startingTime, clen):
        ackStartTime = startingTime + self.startedAt
        bwStartedAt = ackStartTime % self.ttime[-1]

        i = 1
        while True:
            if self.ttime[i] > bwStartedAt:
                break
            i += 1

        if i == len(self.ttime):
            i = 1

        now = bwStartedAt

        totalDownload = 0
        totalDuration = 0
        dlStat = [(0,0)]
        while True:
            thp = self.bw[i]
            dur = self.ttime[i] - now
#             print(dur, self.ttime[i], now)

            dl = thp * (1024 * 1024 / 8) * dur * 0.95
            dl = round(dl, 3)
            left = round(clen - totalDownload, 3)

            if dl > left:
                dur = dur * (left/dl)
                totalDuration += dur
                totalDownload += left
                dlStat += [(totalDuration, totalDownload)]
                break

            totalDownload += dl
            totalDuration += dur
            dlStat += [(totalDuration, totalDownload)]
            if dl == left:
                break

            i += 1
            if i == len(self.ttime):
                i = 1
            now = self.ttime[i-1]

        totalDuration += 0.08 #delay
        totalDuration *= np.random.uniform(0.9, 1.1)
        ratio = totalDuration/dlStat[-1][0]
        dlStat = [(round(x*ratio, 3), y) for x,y in dlStat]
        return totalDuration, dlStat




class Simple():
    def __init__(self, vi, traces, simulator, abr = None, peerId = -1, logpath=None, resultpath=None, sharedLink=None, *kw, **kws):
        self._vCookedTime, self._vCookedBW, self._vTraceFile = traces
#         self._vLastBandwidthPtr = int(np.random.uniform(1, len(self._vCookedTime)))
#         self._vLastTime = -1
#         self._vLastBandwidthTime =
        self._vAgent = Agent(videoInfo=vi, env=self, abrClass=abr, logpath=logpath, resultpath=resultpath)
        self._vLogPath = logpath
        self._vResultPath = resultpath
        self._vSimulator = simulator
        self._vDead = False
        self._vVideoInfo = vi
        self._vFinished = False
        self._vConnectionSpeed = np.mean(self._vCookedBW)
        self._vLastDownloadedAt = 0
        self._vPeerId = peerId if peerId >= 0 else np.random.randint(1000000)
        self._vIdleTimes = []
        self._vWorkingTimes = []
        self._vTotalIdleTime = 0
        self._vTotalWorkingTime = 0
        self._vNextDownloadId = 0

        self._vWorking = False
        self._vWorkingStatus = None
        self._vTraceProc = None
        self._vCdn = CDN.getInstance()

        #only for sharedLink
        self._vSharedLink = sharedLink
        self._vCurJobId = -1
        self._vCurDlState = None

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
    @property
    def now(self):
        return self._vSimulator.getNow()

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
        myprint(self._vTraceFile)
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

        self._vTraceProc= TraceComputation(self.now, self._vCookedBW, self._vCookedTime)
        self._vLastDownloadedAt = self.getNow()
#         self._vLastTime = (self._vCookedTime[1] + self.now) % int(self._vCookedTime[-1]) # np.random.uniform(self._vCookedTime[1], self._vCookedTime[-1])
        self._vAgent.start(startedAt)

#=============================================
    def _rFetchSegment(self, nextSegId, nextQuality, sleepTime = 0.0, extraData=None):
        if self._vDead: return
        assert sleepTime >= 0
        assert nextSegId < self._vVideoInfo.segmentCount
        if sleepTime > 0:
            self._vSimulator.runAfter(sleepTime, self._rFetchNextSeg, nextSegId, nextQuality)
        else:
            self._rFetchNextSeg(nextSegId, nextQuality, extraData)

#=============================================
    def _rAddToBuffer(self, req, simIds = None):
        if self._vDead: return
        self._vAgent._rAddToBufferInternal(req, simIds)

#=============================================
    def getTimeRequredToDownload(self, start, clen):
        dur, dlStat = self._vTraceProc.getDLTime(start, clen)
        return dur

#=============================================
    def _rFetchNextSegNonShared(self, nextSegId, nextQuality, extraData=None):
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

        nextDur = self._vVideoInfo.getSegDuration(nextSegId)

        clen = self._vVideoInfo.fileSizes[nextQuality][nextSegId]

        time, downloadData = self._vTraceProc.getDLTime(now, clen)

        simIds[REQUESTION_SIMID_KEY] = self._vSimulator.runAfter(time, self._rFetchNextSegReturn, nextQuality, now, nextDur, nextSegId, clen, simIds, extraData, self._vNextDownloadId)
        self._vWorkingStatus = (now, time, nextSegId, clen, downloadData, simIds, self._vNextDownloadId)
        self._vNextDownloadId += 1
                #useful to calculate downloaded data

#=============================================
    def _rFetchNextSeg(self, nextSegId, nextQuality, extraData=None):
        if self._vSharedLink is None:
            return self._rFetchNextSegNonShared(nextSegId, nextQuality, extraData)

        if self._vDead: return

        assert not self._vWorking
        self._vWorking = True
        now = self.now

        sleepTime = now - self._vLastDownloadedAt
        idleTime = round(sleepTime, 3)
        self._vIdleTimes += [(now, 0)]
        if idleTime > 0:
            self._vTotalIdleTime += idleTime
            self._vWorkingTimes += [(now, 0, nextSegId)]

        dur = self._vVideoInfo.getSegDuration(nextSegId)
        clen = self._vVideoInfo.fileSizes[nextQuality][nextSegId]
        curDlId = self._vNextDownloadId
        self._vNextDownloadId += 1

        dlState = []
        state = [nextSegId, nextQuality, extraData, clen, curDlId, dlState, now, dur]

        self._vCurDlState = state
        self._vCurJobId = self._vSharedLink.addJob(self._rOnUpdate, self._rOnFinish, state, clen, 128*1024)
        self._vWorkingStatus = (now, None, nextSegId, clen, dlState, None, curDlId)

#=============================================
    def _rOnUpdate(self, state, downloaded, now, *_):
        nextSegId, nextQuality, extraData, clen, curDlId, dlState, startedAt, dur = state

        timeSpent = round(now - startedAt, 3)
        dlState += [(timeSpent, downloaded)]

#=============================================
    def _rOnFinish(self, state, downloaded, now, *_):
        if not self._vWorking:# or self._vWorkingStatus[6] != dlId:
            return
        assert self._vWorking
        segId, ql, extraData, clen, curDlId, dlState, startedAt, dur = state
        self._vWorking = False
        self._vWorkingStatus = None

        self._vIdleTimes += [(now, 25)]
        time = now - startedAt
        self._vLastDownloadedAt = now
        self._vTotalWorkingTime += time
        req = SegmentRequest(ql, startedAt, now, dur, segId, clen, self, extraData)
        self._vWorkingTimes += [(now, req.throughput, segId)]
        self._vCdn.add(startedAt, now, req.throughput)
        req.markDownloaded()
        self._rAddToBuffer(req, None)

#=============================================
    def _rGetWorkingSegid(self):
        assert self._vWorking
        now, time, nextSegId, clen, downloadData, simIds, dlId = self._vWorkingStatus
        return nextSegId

#=============================================
    def _rFetchNextSegReturn(self, ql, startedAt, dur, segId, clen, simIds, extraData, dlId):
        if not self._vWorking or self._vWorkingStatus[6] != dlId:
            return
        assert self._vWorking
        _, _, _, _, downloadData, _, dlId = self._vWorkingStatus
        self._vWorking = False
        self._vWorkingStatus = None

        now = self._vSimulator.getNow()
        self._vIdleTimes += [(now, 25)]
        time = now - startedAt
        self._vLastDownloadedAt = now
        self._vTotalWorkingTime += time
        req = SegmentRequest(ql, startedAt, now, dur, segId, clen, self, extraData)
        self._vWorkingTimes += [(now, req.throughput, segId)]
        self._vCdn.add(startedAt, now, req.throughput)
        req.markDownloaded()
        self._rAddToBuffer(req, simIds)

#=============================================
    def _rStopDownloadNonShared(self):
        assert self._vWorking
        now = self.getNow()
        startedAt, dur, segId, clen, downloadData, simIds, dlId = self._vWorkingStatus
        time, downloaded, _ = self._rDownloadStatus()
        self._vLastDownloadedAt = now
        self._vTotalWorkingTime += time
        req = SegmentRequest(0, startedAt, now, dur, segId, downloaded, self)
        self._vWorkingTimes += [(now, req.throughput, segId)]
        self._vCdn.add(startedAt, now, req.throughput)

#=============================================
    def _rDownloadStatusNonShared(self):
        if not self._vWorking:
            return (0,0,0)
        assert self._vWorking
        now = self.getNow()
        startedAt, dur, segId, clen, downloadData, simIds, dlId = self._vWorkingStatus
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

                downLoadedTillNow = s
                downLoadedTillNow += 0 if slt == 0 else round(amt*sltSpent/slt, 3)
                break
        return round(timeElapsed, 3), round(downLoadedTillNow), clen

#=============================================
    def _rStopDownload(self):
        if self._vSharedLink is None:
            return self._rStopDownloadNonShared()
        assert self._vWorking
        self._vSharedLink.cancelJob(self._vCurJobId)

        now = self.now
#         startedAt, dur, segId, clen, downloadData, simIds, dlId = self._vWorkingStatus
        segId, nextQuality, extraData, clen, curDlId, dlState, startedAt, dur = self._vCurDlState
        time, downloaded, _ = self._rDownloadStatus()
        self._vLastDownloadedAt = now
        self._vTotalWorkingTime += time
        req = SegmentRequest(0, startedAt, now, dur, segId, downloaded, self)
        self._vWorkingTimes += [(now, req.throughput, segId)]
        self._vCdn.add(startedAt, now, req.throughput)

#=============================================
    def _rDownloadStatus(self):
        if self._vSharedLink is None:
            return self._rDownloadStatusNonShared()

        if not self._vWorking:
            return (0,0,0)
        assert self._vWorking
        nextSegId, nextQuality, extraData, clen, curDlId, dlState, startedAt, dur = self._vCurDlState
        if len(dlState) == 0:
            return 0, 0, clen
        ts, dl = dlState[-1]
        return ts, dl, clen

#=============================================
def experimentSimple(traces, vi, network, abr = BOLA):
    simulator = Simulator()
    ags = []
    for x, nodeId in enumerate(network.nodes()):
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        env = Simple(vi=vi, traces=trace, simulator=simulator, abr=abr)
        simulator.runAt(101.0 + x, env.start, 5)
        ags.append(env)
    simulator.run()
    for i,a in enumerate(ags):
        assert a._vFinished
#         print(a._vAgent._vSegIdPlaybackTime, "="*35, sep="\n", end="\n\n")
    return ags


#=============================================
def main():
#     np.random.seed(2300)
    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()
    experimentSimple(traces=traces, vi=vi, network=network)

if __name__ == "__main__":
    for x in range(1):
        main()
        print("=========================\n")
