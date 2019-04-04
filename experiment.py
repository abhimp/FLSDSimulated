import os
import numpy as np
import matplotlib.pyplot as plt
import collections as cl
import sys

import load_trace
import videoInfo as video
from p2pnetwork import P2PNetwork
import randStateInit as randstate
from envGroupP2PBasic import GroupP2PEnvBasic
from envGroupP2PTimeout import GroupP2PEnvTimeout
from envGroupP2PTimeoutSkip import GroupP2PEnvTimeoutSkip
from envGroupP2PTimeoutInc import GroupP2PEnvTimeoutInc
from envGroupP2PRNNTest import GroupP2PEnvRNN
from envGroupP2PDeter import GroupP2PEnvDeter
from envSimple import SimpleEnvironment
from envDHT import DHTEnvironment
from simulator import Simulator
from group import GroupManager
# from envSimpleP2P import experimentSimpleP2P
from abrFastMPC import AbrFastMPC
from abrRobustMPC import AbrRobustMPC
from abrBOLA import BOLA
from cdnUsages import CDN

# from envGroupP2PTimeoutRNNTest import GroupP2PEnvTimeoutRNN
# from abrPensiev import AbrPensieve
# from envGroupP2PTimeoutIncRNN import GroupP2PEnvTimeoutIncRNN
GroupP2PEnvTimeoutRNN = None
GroupP2PEnvTimeoutIncRNN = None
AbrPensieve = None


RESULT_DIR = "./results/GenPlots"
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
        if name not in ["GroupP2PBasic", "GroupP2PTimeout", "GroupP2PTimeoutSkip", "GroupP2PEnvTimeoutRNN", "GroupP2PEnvTimeoutIncRNN"]:
            continue
        for ag in res:
            if not ag._vGroup or ag._vGroup.isLonepeer(ag) or len(ag._vGroupNodes) <= 1:
                p.add(ag.networkId)
    return p

def plotAgentsData(results, attrib, pltTitle, xlabel, lonePeers = []):
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
            if ag.networkId in lonePeers:
                continue
            y = eval("ag." + attrib)
            Xs.append(x)
            Ys.append(y)

        savePlotData(Xs, Ys, name, pltTitle)
        pltData[name] = Ys
        Xs, Ys = list(zip(*getCMF(Ys)))
        savePlotData(Xs, Ys, name+"_cmf", pltTitle)
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

def plotCDNData(cdns):
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
        savePlotData(Xs, Ys, name, pltTitle)
        plt.plot(Xs, Ys, label=name)

    plt.legend(ncol = 2, loc = "upper center")
    plt.title(pltTitle)
    dpath = os.path.join(RESULT_DIR, pltTitle.replace(" ", "_"))
    plt.savefig(dpath + "_cmf.eps", bbox_inches="tight")
    plt.savefig(dpath + "_cmf.png", bbox_inches="tight")

GLOBAL_STARTS_AT = 5

def runExperiments(envCls, traces, vi, network, abr = BOLA, result_dir=None, modelPath = None):
    simulator = Simulator()
    grp = GroupManager(4, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []
    players = len(list(network.nodes()))
    idxs = np.random.randint(len(traces), size=players)
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
    global GroupP2PEnvTimeoutRNN, AbrPensieve, GroupP2PEnvTimeoutIncRNN
    allowed = ["BOLA", "FastMPC", "RobustMPC", "Penseiv", "GroupP2PBasic", "GroupP2PTimeout", "GroupP2PTimeoutSkip", "GroupP2PTimeoutInc", "GroupP2PEnvTimeoutRNN", "GroupP2PEnvTimeoutIncRNN", "DHTEnvironment", "GroupP2PEnvRNN", "GrpDeter"] 
    if "-h" in sys.argv or len(sys.argv) <= 1:
        print(" ".join(allowed))
        return
    allowed = sys.argv[1:]
    if "Penseiv" in allowed and AbrPensieve is None:
        from abrPensiev import AbrPensieve as abp
        AbrPensieve = abp

    if "GroupP2PEnvTimeoutRNN" in allowed and GroupP2PEnvTimeoutRNN is None:
        from envGroupP2PTimeoutRNNTest import GroupP2PEnvTimeoutRNN as gpe
        GroupP2PEnvTimeoutRNN = gpe

    if "GroupP2PEnvTimeoutIncRNN" in allowed and GroupP2PEnvTimeoutIncRNN is None:
        from envGroupP2PTimeoutIncRNNTest import GroupP2PEnvTimeoutIncRNN as gpe
        GroupP2PEnvTimeoutIncRNN = gpe

#     randstate.storeCurrentState() #comment this line to use same state as before
    randstate.loadCurrentState()
    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    vi = video.loadVideoTime("./videofilesizes/sizes_qBVThFwdYTc.py")
#     vi = video.loadVideoTime("./videofilesizes/sizes_penseive.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()
#     network = P2PNetwork("./graph/p2p-Gnutella04.txt")

    testCB = {}
    testCB["BOLA"] = (SimpleEnvironment, traces, vi, network, BOLA)
    testCB["FastMPC"] = (SimpleEnvironment, traces, vi, network, AbrFastMPC)
    testCB["RobustMPC"] = (SimpleEnvironment, traces, vi, network, AbrRobustMPC)
    testCB["Penseiv"] = (SimpleEnvironment, traces, vi, network, AbrPensieve)
    testCB["GroupP2PBasic"] = (GroupP2PEnvBasic, traces, vi, network)
    testCB["GroupP2PTimeout"] = (GroupP2PEnvTimeout, traces, vi, network)
    testCB["GroupP2PTimeoutSkip"] = (GroupP2PEnvTimeoutSkip, traces, vi, network)
    testCB["DHTEnvironment"] = (DHTEnvironment, traces, vi, network)
    testCB["GroupP2PTimeoutInc"] = (GroupP2PEnvTimeoutInc, traces, vi, network)
    testCB["GroupP2PEnvTimeoutRNN"] = (GroupP2PEnvTimeoutRNN, traces, vi, network, BOLA, None, "ModelPath")
    testCB["GroupP2PEnvTimeoutIncRNN"] = (GroupP2PEnvTimeoutIncRNN, traces, vi, network, BOLA, None, "ModelPath")
    testCB["GroupP2PEnvRNN"] = (GroupP2PEnvRNN, traces, vi, network, BOLA, None, "ResModelPathRNN/")
    testCB["GrpDeter"] = (GroupP2PEnvDeter, traces, vi, network, BOLA, None, "ResModelPathRNN/")

    results = {}
    cdns = {}

#     for name, cb in testCB.items():
    for name in allowed:
        assert name in testCB
        cb = testCB[name]
        randstate.loadCurrentState()
        ags, cdn = runExperiments(*cb)
        results[name] = ags
        cdns[name] = cdn

    print("ploting figures")
    print("="*30)

    lonePeers = findIgnorablePeers(results)

    plotAgentsData(results, "_vAgent.QoE", "QoE", "Player Id", lonePeers)
    plotAgentsData(results, "_vAgent.avgBitrate", "Average bitrate played", "Player Id", lonePeers)
    plotAgentsData(results, "_vAgent.avgQualityIndex", "Average quality index played", "Player Id", lonePeers)
    plotAgentsData(results, "_vAgent.avgQualityIndexVariation", "Average quality index variation", "Player Id", lonePeers)
    plotAgentsData(results, "_vAgent.totalStallTime", "Stall Time", "Player Id", lonePeers)
    plotAgentsData(results, "_vAgent.startUpDelay", "Start up delay", "Player Id", lonePeers)
    plotAgentsData(results, "idleTime", "IdleTime", "Player Id", lonePeers)
    plotAgentsData(results, "_vAgent.avgBitrateVariation", "Average Bitrate Variation", "Player Id", lonePeers)
    plotAgentsData(results, "totalWorkingTime", "workingTime", "Player Id", lonePeers)

    plotCDNData(cdns)

#     plt.show()

#     plotBufferLens(results)
#     plotIdleStallTIme(results)



if __name__ == "__main__":
#     for x in range(20):
        main()
#     main2()
