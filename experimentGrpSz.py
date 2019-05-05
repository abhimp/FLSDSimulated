import os
import numpy as np
import matplotlib.pyplot as plt
import collections as cl
import sys

from util import load_trace
from util import videoInfo as video
from util.p2pnetwork import P2PNetwork
from util import randStateInit as randstate
from simenv.GroupP2PBasic import GroupP2PBasic
from simenv.GroupP2PTimeout import GroupP2PTimeout
from simenv.GroupP2PTimeoutSkip import GroupP2PTimeoutSkip
from simenv.GroupP2PTimeoutInc import GroupP2PTimeoutInc
from simenv.GroupP2PDeter import GroupP2PDeter
from simenv.Simple import Simple
from simenv.DHT import DHT
from simulator.simulator import Simulator
from util.group import GroupManager
# from simenv.SimpleP2P import experimentSimpleP2P
from abr.FastMPC import AbrFastMPC
from abr.RobustMPC import AbrRobustMPC
from abr.BOLA import BOLA
from util.cdnUsages import CDN

# from simenv.GroupP2PTimeoutRNNTest import GroupP2PTimeoutRNN
# from abrPensiev import AbrPensieve
# from simenv.GroupP2PTimeoutIncRNN import GroupP2PTimeoutIncRNN
GroupP2PTimeoutRNN = None
GroupP2PTimeoutIncRNN = None
AbrPensieve = None


RESULT_DIR_ = "./results/GroupSizePlot"
RESULT_DIR = RESULT_DIR_
BUFFER_LEN_PLOTS = "results/bufferlens"
STALLTIME_IDLETIME_PLOTS = "results/stall-idle"

def getPMF(x):
    x = [y for y in x]
    freq = list(cl.Counter(x).items())
    elements = zip(*freq)
    s = sum(elements[1])
    pdf = [(k[0],float(k[1])/s) for k in freq]
    # pdf.sort
    return pdf


def getCMF(elements):
    x = [y for y in elements]
    freq = list(cl.Counter(x).items())
    freq.sort(key = lambda x:x[0])
    x,y = zip(*freq)
    s = sum(y)
    cmf = [(p, float(sum(y[:i+1]))/s) for i, p in enumerate(x)]
    return cmf

def getCount(elements):
    x = [y for y in elements]
    freq = list(cl.Counter(x).items())
    freq.sort(key = lambda x:x[0])
    return freq
    x,y = zip(*freq)
    return x,y

def savePlotData(Xs, Ys, legend, pltTitle):
    dpath = os.path.join(RESULT_DIR, pltTitle.replace(" ", "_"))
    if not os.path.isdir(dpath):
        os.makedirs(dpath)
    fpath = os.path.join(dpath, legend + ".dat")
    with open(fpath, "w") as fp:
        assert len(Xs) == len(Ys)
        st = "\n".join(str(x) + "\t" + str(y) for x, y in zip(Xs, Ys))
        fp.write(st)

def restorePlotData(legend, pltTitle):
    dpath = os.path.join(RESULT_DIR, pltTitle.replace(" ", "_"))
    fpath = os.path.join(dpath, legend + ".dat")
    assert os.path.isfile(fpath)

    with open(fpath) as fp:
        Xs, Ys = list(zip(*[[float(x) for x in y.strip().split()] for y in fp]))
        return Xs, Ys

def plotStoredData(legends, _, pltTitle, xlabel):
#     plt.clf()
    plt.figure()
    pltData = []
    for name in legends:
        Xs, Ys = restorePlotData(name, pltTitle)
        pltData += [Xs, Ys]
        plt.plot(Xs, Ys, label=name)
    plt.legend(ncol = 2, loc = "upper center")
    plt.title(pltTitle)
    plt.xlabel(xlabel)

def findIgnorablePeers(results):
    p = set()
    for name, res in results.items():
        if name not in ["GrpDeter", "GroupP2PBasic", "GroupP2PTimeout", "GroupP2PTimeoutSkip", "GroupP2PTimeoutRNN", "GroupP2PTimeoutIncRNN"]:
            continue
#         x = []
        for ag in res:
            if not ag._vGroup or ag._vGroup.isLonepeer(ag) or len(ag._vGroupNodes) != ag._vGroup.peersPerGroup:
                p.add(ag.networkId)
    return p
#               x += [ag.networkId]
#         if len(x) > 0:
#             if len(p) > 0:
#                 assert x == p[-1]
#             p.append(x)
#     if len(p): print(p)
#     return set(p[-1]) if len(p) else []


def saveAgentsDataMulitAttrib(grpSz, results, attribs, pltTitle, lonePeers = []):
    for name, res in results.items():
        Xs, Ys = [], []
        for x, ag in enumerate(res):
            if ag.networkId in lonePeers:
                continue
            if not ag._vGroup or len(ag._vGroupNodes) != grpSz:
                continue
            y = []
            for at in attribs:
                y.append(eval("ag." + at))
            y = " ".join(str(i) for i in y)
            Xs.append(x)
            Ys.append(y)
        savePlotData(Xs, Ys, name + "_"+str(grpSz), pltTitle)


def plotAgentsData(grpSz, results, attrib, pltTitle, xlabel, lonePeers = []):
    font = {'family' : 'normal',
            'weight' : 'bold',
            'size'   : 22}

    figsize=(7, 5)
    plt.clf()
    plt.rc('font', **font)
    plt.figure(figsize=figsize, dpi=150)
    assert min([len(res) for name, res in results.items()]) == max([len(res) for name, res in results.items()])
    pltData = {}
    for name, res in results.items():
        Xs, Ys = [], []
        for x, ag in enumerate(res):
            if not ag._vGroup or len(ag._vGroupNodes) != grpSz:
                continue
            y = eval("ag." + attrib)
            Xs.append(x)
            Ys.append(y)

        savePlotData(Xs, Ys, name + "_"+str(grpSz), pltTitle)
        pltData[name] = Ys
        Xs, Ys = list(zip(*getCMF(Ys)))
        savePlotData(Xs, Ys, name + "_"+str(grpSz) + "_cmf", pltTitle)
        plt.plot(Xs, Ys, label=name)
    plt.legend(ncol = 2, loc = "upper center")
    plt.title(pltTitle)
#     plt.xlabel(xlabel)
    dpath = os.path.join(RESULT_DIR, pltTitle.replace(" ", "_"))
#     x,l = plt.xticks()
#     plt.xticks(x, l, rotation=20)
    plt.savefig(dpath + "_cmf.eps", bbox_inches="tight")
    plt.savefig(dpath + "_cmf.png", bbox_inches="tight")
#     plt.show()
    plt.clf()
    plt.rc('font', **font)
    plt.figure(figsize=figsize, dpi=150)
    names, Yss = list(zip(*pltData.items()))
    plt.boxplot(Yss, labels=names, notch=True)
    plt.title(pltTitle)
    x,l = plt.xticks()
    plt.xticks(x, l, rotation=20)
    plt.savefig(dpath + "_box.png", bbox_inches="tight")
    plt.savefig(dpath + "_box.eps", bbox_inches="tight")

def plotCDNData(grpSz, cdns):
    font = {'family' : 'normal',
            'weight' : 'bold',
            'size'   : 22}

    figsize=(7, 5)
    plt.clf()
    plt.rc('font', **font)
    plt.figure(figsize=figsize, dpi=150)
    pltData = {}
    pltTitle = "cdnUploaded"
    for name, res in cdns.items():
        Xs, Ys = list(zip(*res.uploaded))
        savePlotData(Xs, Ys, name + "_"+str(grpSz), pltTitle)
        plt.plot(Xs, Ys, label=name)

    plt.legend(ncol = 2, loc = "upper center")
    plt.title(pltTitle)
    dpath = os.path.join(RESULT_DIR, pltTitle.replace(" ", "_"))
    plt.savefig(dpath + "_cmf.eps", bbox_inches="tight")
    plt.savefig(dpath + "_cmf.png", bbox_inches="tight")

GLOBAL_STARTS_AT = 5

def runExperiments(grpSz, envCls, traces, vi, network, abr = BOLA, result_dir=None, modelPath = None):
    simulator = Simulator()
    grp = GroupManager(grpSz, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []
    players = len(list(network.nodes()))
    idxs = [x%len(traces) for x in range(players)] #np.random.randint(len(traces), size=players)
    startsAts = np.random.randint(GLOBAL_STARTS_AT + 1, vi.duration/2, size=players)
    CDN.clear()
    for x, nodeId in enumerate(network.nodes()):
        idx = idxs[x]
        trace = traces[idx]
        startsAt = startsAts[x]
        env = envCls(vi = vi, traces = trace, simulator = simulator, grp=grp, peerId=nodeId, abr=abr, logpath=result_dir, modelPath=modelPath)
        simulator.runAt(startsAt, env.start, GLOBAL_STARTS_AT)
        ags.append(env)
    simulator.run()
    for i,a in enumerate(ags):
        assert a._vFinished # or a._vDead
    return ags, CDN.getInstance() #cdn is singleton, so it is perfectly okay get the instance

def main():
    global GroupP2PTimeoutRNN, AbrPensieve, GroupP2PTimeoutIncRNN
    allowed = ["GrpDeter", "GroupP2PTimeoutInc", "GroupP2PTimeoutIncRNN"]
    if "-h" in sys.argv or len(sys.argv) <= 1:
        print(" ".join(allowed))
        return
    allowed = sys.argv[1:]
    if "GroupP2PTimeoutIncRNN" in allowed and GroupP2PTimeoutIncRNN is None:
        from simenv.GroupP2PTimeoutIncRNNTest import GroupP2PTimeoutIncRNN as gpe
        GroupP2PTimeoutIncRNN = gpe

#     randstate.storeCurrentState() #comment this line to use same state as before
    randstate.loadCurrentState()
    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    vi = video.loadVideoTime("./videofilesizes/sizes_qBVThFwdYTc.py")
#     vi = video.loadVideoTime("./videofilesizes/sizes_qBVThFwdYTc.py")
#     vi = video.loadVideoTime("./videofilesizes/sizes_penseive.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()
#     network = P2PNetwork("./graph/p2p-Gnutella04.txt")

    testCB = {}
    testCB["GroupP2PTimeoutInc"] = (GroupP2PTimeoutInc, traces, vi, network)
    testCB["GroupP2PTimeoutIncRNN"] = (GroupP2PTimeoutIncRNN, traces, vi, network, BOLA, None, "ModelPath")
    testCB["GrpDeter"] = (GroupP2PDeter, traces, vi, network, BOLA, None, "ResModelPathRNN/")

    results = {}
    cdns = {}

    for grpSz in [3, 4, 5, 6, 7, 8, 9, 10]:
        for name in allowed:
            assert name in testCB
            cb = testCB[name]
            randstate.loadCurrentState()
            ags, cdn = runExperiments(grpSz, *cb)
            results[name] = ags
            cdns[name] = cdn

        print("ploting figures")
        print("="*30)

        lonePeers = findIgnorablePeers(results)

        saveAgentsDataMulitAttrib(grpSz, results, ["_vTotalUploaded","_vTotalDownloaded"] , "upload_download", lonePeers)
        saveAgentsDataMulitAttrib(grpSz, results, ["_vEarlyDownloaded","_vNormalDownloaded"] , "earlydownload", lonePeers)

        plotAgentsData(grpSz, results, "_vAgent.QoE", "QoE", "Player Id", lonePeers)
        plotAgentsData(grpSz, results, "_vAgent.avgBitrate", "Average bitrate played", "Player Id", lonePeers)
        plotAgentsData(grpSz, results, "_vAgent.avgQualityIndex", "Average quality index played", "Player Id", lonePeers)
        plotAgentsData(grpSz, results, "_vAgent.avgQualityIndexVariation", "Average quality index variation", "Player Id", lonePeers)
        plotAgentsData(grpSz, results, "_vAgent.totalStallTime", "Stall Time", "Player Id", lonePeers)
        plotAgentsData(grpSz, results, "_vAgent.startUpDelay", "Start up delay", "Player Id", lonePeers)
        plotAgentsData(grpSz, results, "idleTime", "IdleTime", "Player Id", lonePeers)
        plotAgentsData(grpSz, results, "_vAgent.avgBitrateVariation", "Average Bitrate Variation", "Player Id", lonePeers)
        plotAgentsData(grpSz, results, "totalWorkingTime", "workingTime", "Player Id", lonePeers)

        plotCDNData(grpSz, cdns)

#     plt.show()

#     plotBufferLens(results)
#     plotIdleStallTIme(results)



if __name__ == "__main__":
#     for x in range(20):
        main()
#     main2()
