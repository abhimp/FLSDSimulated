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
from simenv.GroupP2PRNN import GroupP2PRNN as GroupP2PRNNTrain
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

class GroupP2PRNN(GroupP2PRNNTrain):
    def __init__(self, vi, traces, simulator, abr = None, grp = None, peerId = None, modelPath=None, *kw, **kws):
        super().__init__(vi=vi, traces=traces, simulator=simulator, abr=abr, grp=grp, peerId=peerId, modelPath=modelPath, *kw, **kws)
        self.playerAction = list(range(5))
        self._vPensieveAgentLearner = None if not self._vModelPath  else rnnAgent.getPensiveLearner(self.playerAction, summary_dir = self._vModelPath, nn_model = NN_MODEL_AGE, readOnly=True)
        actions = list(range(len(self._vVideoInfo.bitrates) -1, -1, -1))
        self._vPensieveQualityLearner = None if not self._vModelPath  else rnnQuality.getPensiveLearner(actions, summary_dir = self._vModelPath, nn_model = NN_MODEL_QUA, readOnly=True)


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
