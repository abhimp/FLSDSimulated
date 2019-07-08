import os
from util.myprint import myprint
import math
import json
import matplotlib.pyplot as plt
import numpy as np
import glob
import smtplib
from email.mime.text import MIMEText
import sys
import traceback as tb

from simenv.Simple import Simple, np, Simulator, load_trace, video, P2PNetwork
from simenv.GroupP2PDeter import GroupP2PDeter
from util.email import sendErrorMail
from util.group import GroupManager
import util.randStateInit as randstate
from util.easyPlotViewer import EasyPlot
from util.calculateMetric import measureQoE
from abr.BOLA import BOLA

# from rnnTimeout import getPensiveLearner, saveLearner
import rnn.Agent as rnnAgent
import rnn.Quality as rnnQuality


GROUP_JOIN_THRESHOLD = 10
BYTES_IN_MB = 1000000.0

LOG_LOCATION = "./results/"
NN_MODEL_QUA = None
NN_MODEL_AGE = None
def default(o):
    if isinstance(o, np.int64): return int(o)
    raise TypeError

class GroupP2PDeterQaRNN(GroupP2PDeter):
    def __init__(self, vi, traces, simulator, abr = None, grp = None, peerId = None, modelPath=None, *kw, **kws):
        super().__init__(vi=vi, traces=traces, simulator=simulator, abr=abr, grp=grp, peerId=peerId, modelPath=modelPath, *kw, **kws)
        actions = list(range(len(self._vVideoInfo.bitrates) -1, -1, -1))
#         self._vPensieveAgentLearner = None if not self._vModelPath  else rnnAgent.getPensiveLearner(list(range(5)), summary_dir = self._vModelPath, nn_model = NN_MODEL_AGE)
        self._vPensieveQualityLearner = None if not self._vModelPath  else rnnQuality.getPensiveLearner(actions, summary_dir = self._vModelPath, nn_model = NN_MODEL_QUA)
#=============================================
    def _rGetMyQualityFailSafe(self, nextQl, segId, rnnkey):
        super()._rGetMyQuality(nextQl, segId, rnnkey)

#=============================================
    def _rGetDealine(self, segId):
        deadLine = segId*self._vVideoInfo.segmentDuration - self._vAgent.playbackTime
        if self._vGroupNodes and len(self._vGroupNodes) >= 1:
            deadLine = segId*self._vVideoInfo.segmentDuration - max([n._vAgent.playbackTime for n in self._vGroupNodes])
        return deadLine

#=============================================
    def _rGetMyQuality(self, nextQl, segId, rnnkey):
        if not rnnkey:
            return nextQl #handle this
        segIds = [x[0] for x in self._vGroupSegDetails[-5:]]
        lastPlayerId = [x[1] for x in self._vGroupSegDetails[-5:]]
        lastQl = [x[1] for x in self._vGroupSegDetails[-5:]]

        lastClens = [0]*5 + [self._vVideoInfo.fileSizes[ql][s] for ql, s in zip(lastQl, segIds)]
        _, lastPlayerId, lastQl = list(zip(*([(0,0,0), (0,0,0)] + self._vGroupSegDetails[-5:])))
        lastClens = np.array(lastClens)/BYTES_IN_MB

        lastPlayerId = [0]*5 + list(lastPlayerId)
        lastQl = [0]*5 + [x[1] for x in self._vDownloadQl[-5:]]

        deadLine = self._rGetDealine(segId) / self._vAgent.maxPlayerBufferLen #segId*self._vVideoInfo.segmentDuration - max([n._vAgent.playbackTime for n in self._vGroupNodes])
        curProg = self._rDownloadStatus()
        prog = len(self._vDownloadQueue) * 100 + (curProg[1] / curProg[2] if curProg[2] else 0)

        targetQl = lastQl[-1] if len(lastQl) > 1 else self._vAgent._vQualitiesPlayed[-1]

        clens = [ql[segId]/BYTES_IN_MB for ql in self._vVideoInfo.fileSizes]

        thrpt = self._vThroughPutData[-5:]
        if curProg[1] > 0 and curProg[0] > 0:
            thrpt += [(self.now, curProg[1] * 8 / curProg[0])]
        thrpt = [x for t, x in thrpt]
        thrpt = np.array([0]*5 + thrpt)/BYTES_IN_MB/8

        lastQl = [self._vVideoInfo.bitrates[x]/BYTES_IN_MB for x in lastQl]

        state = (thrpt[-5:], lastQl[-5:], lastClens[-5:], clens, self._vWeightedThroughput/BYTES_IN_MB/8, self._vAgent.bufferLeft/self._vVideoInfo.segmentDuration, deadLine)

        self._vSegIdRNNKeyMap[segId] = rnnkey

        rnnkey, _ = rnnkey

        ql = self._vPensieveQualityLearner.getNextAction(rnnkey, state)

        return ql

#=============================================
    def _rDownloadAsTeamPlayer(self, segId, rnnkey = None, ql = -1, syncSeg = False):
        nextDownloader, rnnkeynew = self._rGetNextDownloader(segId)
        if not rnnkeynew:
            rnnkeynew = ((self.networkId, segId), 0)
        self._rAddToDownloadQueue(segId, ql, rnnkey=rnnkey, syncSeg=syncSeg)
        self.gossipSend(self._rSetNextDownloader, nextDownloader, segId+1, rnnkeynew, segId, self._vPlayerIdInGrp, ql)
        self._rSetNextDownloader(nextDownloader, segId + 1, rnnkeynew, segId, self._vPlayerIdInGrp, ql)

#=============================================
    def _rDownloadFromDownloadQueue(self):
        if self._vDownloadPending:
            return
        while len(self._vDownloadQueue):
            segId, ql, rnnkey, syncSeg = self._vDownloadQueue.pop(0)
            if segId < self._vAgent.nextSegmentIndex: #we are not going to playit anyway.
                continue
            if segId >= self._vGroupStartedFromSegId and self._vGroupStarted:
                ql = self._rGetMyQuality(ql, segId, rnnkey) # handle rnnkey == None
                assert ql < len(self._vVideoInfo.fileSizes)
                self.gossipSend(self._rDownloadingUsing, segId, ql)
                self._rDownloadingUsing(segId, ql)

            deadLine = self._rGetDealine(segId)
            self._rFetchSegment(segId, ql, extraData={"syncSeg":syncSeg, "deadLine":deadLine, "started": self.now})
            self._vDownloadPending = True
            self._vDownloadPendingRnnkey = rnnkey
            break

#=============================================
    def _rQoE(self, curBitrate, lastBitrate, stall):
        alpha = 10
        beta = 1
        gamma = .43

        stall = stall/10 if stall < 8 else stall

        return alpha*curBitrate - beta*abs(curBitrate - lastBitrate) - gamma*stall

#=============================================
    def _rQoEAll(self):
        alpha = 10
        beta = 1
        gamma = .43
        qa, st = self._vAgent._vQualitiesPlayed, self._vAgent._vTotalStallTime
        qa = [self._vVideoInfo.bitrates[x]/BYTES_IN_MB for x in qa]
        if len(qa) == 0:
            return 1
        if len(qa) == 1:
            return alpha*qa[0]
        avQaVa = [abs(qa[x-1]-qa[x]) for x, _ in enumerate(qa) if x > 0]
        avQaVa = sum(avQaVa)
        avQa = sum(qa)

        stall = st/10 if st < 30 else st

        qoe = alpha*avQa - beta*avQaVa - gamma*stall
#         myprint("qoe =", qoe)
        return qoe

#=============================================
    def _rFindOptimalQualityLevel(self, req):
        if req.syncSeg:
            return None
        if req.downloader != self:
            return None

        startedAt = req.downloadStarted

        clens = [ql[req.segId] for ql in self._vVideoInfo.fileSizes]

        durations = [self.getTimeRequredToDownload(startedAt, clen) for clen in clens]


        lastPlaybackInfo = self._vAgent._vSegIdPlaybackTime.get(req.segId - 1, None) #it have to be None as 0 != None
        if lastPlaybackInfo == None:
            return None
        lastSegPlaybackStartedAt, lastReq = lastPlaybackInfo
        lastSegPlaybackEndedAt = lastSegPlaybackStartedAt + self._vVideoInfo.segmentDuration

        stallTimes = [max(startedAt + dur - lastSegPlaybackEndedAt, 0) for dur in durations]
#         print(stallTimes)

        bitrates = self._vVideoInfo.bitrates
        qoes = [self._rQoE(bitrates[i]/BYTES_IN_MB, bitrates[lastReq.qualityIndex]/BYTES_IN_MB, st) for i, st in enumerate(stallTimes)]
        bestQl = np.argmax(qoes)
        return bestQl, qoes[bestQl]


#=============================================
    def _rAddToAgentBuffer(self, req, simIds=None):
        if self._vAgent.nextSegmentIndex > req.segId:
            return
        assert self._vAgent.nextSegmentIndex == req.segId or req.syncSeg
        if self._vAgent.nextSegmentIndex == req.segId:
            assert req.segId in self._vCatched and (round(self._vAgent._vMaxPlayerBufferLen - self._vAgent.bufferLeft, 3) >= self._vVideoInfo.segmentDuration or req.syncSeg)

        waitTime = self._vAgent.bufferAvailableIn()
        assert waitTime <= 0 or req.syncSeg
        playableIn = req.segId * self._vVideoInfo.segmentDuration + self._vAgent._vGlobalStartedAt - (self._vAgent.bufferLeft * ( 1 - req.syncSeg)) - self.now
        if playableIn > 0:
            self.runAfter(playableIn, self._rAddToAgentBuffer, req, 0)
            return
        lastStalls = self._vAgent._vTotalStallTime
        lastQoE = self._rQoEAll()
        self._vAgent._rAddToBufferInternal(req)
        if req.segId in self._vSegIdRNNKeyMap:
            rnnkey = self._vSegIdRNNKeyMap[req.segId]
            del self._vSegIdRNNKeyMap[req.segId]
#             qoe = self._vAgent.QoE

            startedAt = req.extraData.get("started", req.downloadStarted)
            deadLine = req.extraData["deadLine"]
            shouldFinished = startedAt + deadLine
            finishedAt = req.downloadFinished

            idle = abs(shouldFinished - finishedAt)
            idleFrac = idle/deadLine if deadLine != 0 else 1

            totalIdle = self._vTotalIdleTime
            totalPlayable = self._vAgent._vTotalPlayableTime

            idleFrac = totalIdle/totalPlayable if totalPlayable > 0 else 1
            idleFrac = min(idleFrac, 1)


            qls = self._vAgent.bitratePlayed[-2:]

            rebuf = (self._vAgent._vTotalStallTime - lastStalls)
            qoe = self._rQoE(qls[1] / BYTES_IN_MB, qls[0]/BYTES_IN_MB, rebuf)
#             qoe = self._rQoEAll()
            reward = qoe - lastQoE
            ret = self._rFindOptimalQualityLevel(req)
            if ret == None:
                return

            bestQl, bestQoE = ret

            reward = qoe - bestQoE

            reward = qoe - idleFrac


            rnnkey, outofbound = rnnkey
            self._vPensieveQualityLearner.addReward(rnnkey, reward)
            #add reward

#=============================================
#=============================================
#=============================================
AGENT_TRACE_MAP = {}
def plotIdleStallTIme(dpath, group):
    if not os.path.isdir(dpath):
        os.makedirs(dpath)

    colors = ["blue", "green", "red", "cyan", "magenta", "yellow", "black"]

    pltHtmlPath = os.path.join(dpath,"groupP2PTimeout.html")
    open(pltHtmlPath, "w").close()
    eplt = EasyPlot()
    for ql,grpSet in group.groups.items():
        for grp in grpSet:
            grpLabel = str([x._vPeerId for x in grp.getAllNode()])
            label = "<hr><h2>BufferLen</h2>"
            label += " NumNode:" + str(len(grp.getAllNode()))
            label += " Quality Index: " + str(grp.qualityLevel)
            eplt.addFig()
            for i, ag in enumerate(grp.getAllNode()):
                pltData = ag._vAgent._vBufferLenOverTime
                Xs, Ys = list(zip(*pltData))
                eplt.plot(Xs, Ys, marker="x", label=str(ag._vPeerId), color=colors[i%len(colors)])

                label += "\n<br><span style=\"color: " + colors[i%len(colors)] + "\" >PeerId: " + str(ag._vPeerId)
                label += " avgQualityIndex: " + str(ag._vAgent.avgQualityIndex)
                label += " avgStallTime: " + str(ag._vAgent.totalStallTime)
                label += " startedAt: " + str(ag._vAgent._vStartedAt)
                label += " traceIdx: " + str(AGENT_TRACE_MAP.get(ag._vPeerId, 0))
                label += "</span>"
            eplt.setFigHeader(label)
            label = "<h2>workingTime</h2>"
            eplt.addFig()
            for i, ag in enumerate(grp.getAllNode()):
                pltData = ag._vWorkingTimes
                Xs, Ys, Zs = list(zip(*pltData))
                eplt.step(Xs, Ys, toolTipData=Zs, marker="o", label="idleTime", where="pre", color=colors[i%len(colors)])
            eplt.setFigHeader(label)
            label = "<h2>StallTime</h2>"
            eplt.addFig()
            for i, ag in enumerate(grp.getAllNode()):
                pltData = ag._vAgent._vTimeSlipage
                Xs, Ys, Zs = list(zip(*pltData))
                eplt.plot(Xs, Ys, toolTipData=Zs, marker="o", label="idleTime", where="pre", color=colors[i%len(colors)])
            eplt.setFigHeader(label)

            label = "<h2>qualityLevel</h2>"
            eplt.addFig()
            for i, ag in enumerate(grp.getAllNode()):
                pltData = ag._vAgent._vQualitiesPlayedOverTime
                Xs, Ys, Zs = list(zip(*pltData))
                Ys = [ag._vVideoInfo.bitrates[x]/(1000000) for x in Ys]
                eplt.step(Xs, Ys, toolTipData=Zs, marker="o", label="idleTime", where="post", color=colors[i%len(colors)])
            eplt.setFigHeader(label)

    with open(pltHtmlPath, "w") as fp:
        eplt.printFigs(fp, width=1000, height=400)

#=============================================
def experimentGroupP2PBig(traces, vi, network):
    randstate.loadCurrentState()
    simulator = Simulator()
    grp = GroupManager(4, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []
    maxTime = 0
    startsAts= np.random.randint(5, vi.duration/2, size=network.numNodes())
    trx = np.random.randint(len(traces), size=network.numNodes())
    for x, nodeId in enumerate(network.nodes()):
        idx = trx[x]
        startsAt = startsAts[x]
        trace = traces[idx]
        env = GroupP2PDeterQaRNN(vi= vi, traces= trace, simulator= simulator, grp=grp, peerId=nodeId, abr=BOLA, modelPath="ResModelPathRNNQa")
        simulator.runAt(startsAt, env.start, 5)
        maxTime = 101.0 + x
        AGENT_TRACE_MAP[nodeId] = idx
        ags.append(env)
    simulator.run()
    grp.printGroupBucket()
    for i,a in enumerate(ags):
        assert a._vFinished # or a._vDead
    if __name__ == "__main__":
        plotIdleStallTIme("results/stall-idle/", grp)
    return ags

def experimentGroupP2PSmall(traces, vi, network):
    simulator = Simulator()
    grp = GroupManager(4, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []

    for trx, nodeId, startedAt in [( 5, 267, 107), (36, 701, 111), (35, 1800, 124), (5, 2033, 127)]:
        trace = traces[trx]
        env = GroupP2PDeterQaRNN(vi, trace, simulator, None, grp, nodeId)
        simulator.runAt(startedAt, env.start, 5)
        AGENT_TRACE_MAP[nodeId] = trx
        ags.append(env)

    simulator.run()
    grp.printGroupBucket()
    for i,a in enumerate(ags):
        assert a._vFinished # or a._vDead
    if __name__ == "__main__":
        plotIdleStallTIme("results/stall-idle/", grp)
    return ags

def main():
#     randstate.storeCurrentState() #comment this line to use same state as before
    for fpath in glob.glob("videofilesizes/*.py"):
#         randstate.storeCurrentState() #comment this line to use same state as before
        randstate.loadCurrentState()
        traces = load_trace.load_trace()
        vi = video.loadVideoTime("./videofilesizes/sizes_qBVThFwdYTc.py")
        vi = video.loadVideoTime("./videofilesizes/sizes_penseive.py")
        vi = video.loadVideoTime(fpath)
        vi = video.loadVideoTime("./videofilesizes/sizes_qBVThFwdYTc.py")
        assert len(traces[0]) == len(traces[1]) == len(traces[2])
        traces = list(zip(*traces))
#         network = P2PNetwork("./p2p-Gnutella04.txt")
        network = P2PNetwork()

        experimentGroupP2PBig(traces, vi, network)
        return

if __name__ == "__main__":
    for x in range(3):
        main()
        print("=========================\n")
        break
