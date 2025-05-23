import os
from util.myprint import myprint
import math
import json
import matplotlib.pyplot as plt
import numpy as np
import glob
import sys
import traceback as tb


from simenv.Simple import Simple, np, Simulator, load_trace, video, P2PNetwork
from simenv.GroupP2PDeterQaRNN import GroupP2PDeterQaRNN
from util.email import sendErrorMail
from util.group import GroupManager
import util.randStateInit as randstate
from util.easyPlotViewer import EasyPlot
from util.calculateMetric import measureQoE
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

class GroupP2PRNN(GroupP2PDeterQaRNN):
    def __init__(self, vi, traces, simulator, abr = None, grp = None, peerId = None, modelPath=None, *kw, **kws):
#         super().__init__(vi, traces, simulator, abr, peerId, *kw, **kws)
        super().__init__(vi=vi, traces=traces, simulator=simulator, abr=abr, grp=grp, peerId=peerId, modelPath=modelPath, *kw, **kws)
        self.playerAction = list(range(5))
        self._vPensieveAgentLearner = None if not self._vModelPath  else rnnAgent.getPensiveLearner(self.playerAction, summary_dir = self._vModelPath, nn_model = NN_MODEL_AGE)
#         self._vPensieveQualityLearner = None if not self._vModelPath  else rnnQuality.getPensiveLearner(actions, summary_dir = self._vModelPath, nn_model = NN_MODEL_QUA)

#=============================================
    def _rGetNextDownloaderFailSafe(self, segId, rnnkey=None):
        idleTimes = [ 0 if n._vDownloadPending else self.now - n._vWorkingTimes[-1][0]
                        for n in self._vGroupNodes]
        idleTimes = np.array(idleTimes)

        qlen = [len(n._vDownloadQueue) + (n==self) for n in self._vGroupNodes]
        qlen = np.array(qlen) * 100

        prog = [n._rDownloadStatus() for n in self._vGroupNodes]
        prog = [0 if x[2] == 0 else 100 - float(x[1])*100/float(x[2]) for x in prog]
        prog = np.array(prog)

        deadLinePenalty = np.array([0 if len(n._vDeadLineMissed)==0 else self._rPenaltyDegradeTime(*n._vDeadLineMissed[-1]) for n in self._vGroupNodes])

        res = idleTimes - qlen - prog - deadLinePenalty

        return np.argmax(res), rnnkey

#=============================================
    def _rGetNextDownloader(self, segId):
        globalPlaybackTime = self.now - self._vAgent._vGlobalStartedAt
        pendings = [0] * 5
        pendings += [len(n._vDownloadQueue) for n in self._vGroupNodes]

        uploaded = [n._vTotalUploadedSegs/self._vVideoInfo.segmentCount for n in self._vGroupNodes]
        uploaded = [0] *5 + [x for x in (np.array(uploaded) - np.mean(uploaded))]

        deadline = self._rGetDealine(segId)/self._vAgent.maxPlayerBufferLen #segId*self._vVideoInfo.segmentDuration - self._vAgent.playbackTime

        players = [-1]*5 + [n._vPlayerIdInGrp for n in self._vGroupNodes]

        idleTimes = [0]*5 + [ 0 if n._vDownloadPending else self.now - n._vWorkingTimes[-1][0]
                        for n in self._vGroupNodes]
        idleTimes = np.array(idleTimes)/100

        thrpt = [0]*5 + [n._vWeightedThroughput for n in self._vGroupNodes]
        thrpt = np.array([0]*5 + thrpt)/BYTES_IN_MB/8

        prog = [n._rDownloadStatus() for n in self._vGroupNodes]
        prog = [0]*5 + [0 if x[2] == 0 else float(x[1])/float(x[2]) for x in prog]
        prog = np.array(prog)

        clens = [ql[segId]/BYTES_IN_MB for ql in self._vVideoInfo.fileSizes]

        rnnkey = (self.networkId, segId)

        state = (uploaded[-5:], players[-5:], idleTimes[-5:], thrpt[-5:], prog[-5:], clens, deadline)
        state = (uploaded[-5:], idleTimes[-5:], thrpt[-5:], prog[-5:], clens, deadline)

        nextPlayer, potentials = self._vPensieveAgentLearner.getNextAction(rnnkey, state)
        #print(rnnkey, state)

        penalty = 0
        if nextPlayer >= len(self._vGroupNodes):
            npotents = potentials[:len(self._vGroupNodes)].argmax()
            nextPlayer = self.playerAction[npotents]

        assert nextPlayer < len(self._vGroupNodes)

        return nextPlayer, (rnnkey, penalty)

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

        self._vAgent._rAddToBufferInternal(req)
        if req.segId in self._vSegIdRNNKeyMap:
            rnnkey = self._vSegIdRNNKeyMap[req.segId]
            del self._vSegIdRNNKeyMap[req.segId]

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


            ret = self._rFindOptimalQualityLevel(req)
            if ret == None:
                return

            bestQl, qoes = ret
            optQl = req.extraData["optQl"]
            qoe = qoes[req.qualityIndex]
            reward = max(qoe - qoes[optQl], -50)
            reward = -abs(min(reward, 50))
            reward = reward/50.0

            rnnkey, outofbound = rnnkey
            self._vPensieveQualityLearner.addReward(rnnkey, reward)

            uploaded = [n._vTotalUploadedSegs for n in self._vGroupNodes]
            contri = abs(self._vTotalUploadedSegs - np.mean(uploaded))/self._vVideoInfo.segmentCount
            reward = -contri

            reward = 0.7 * qoe + 0.3 * reward
            #call rnn obj for working
            self._vPensieveAgentLearner.addReward(rnnkey, reward)
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
        env = GroupP2PDeter(vi, trace, simulator, None, grp, nodeId)
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
        env = GroupP2PRNN(vi, trace, simulator, None, grp, nodeId, modelPath="/tmp/tmpmodel")
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
        network = P2PNetwork("./p2p-Gnutella04.txt")
        network = P2PNetwork()

        experimentGroupP2PBig(traces, vi, network)
        return

if __name__ == "__main__":
    for x in range(3):
        main()
        print("=========================\n")
        break
