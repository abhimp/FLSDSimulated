import os
import numpy as np
import matplotlib.pyplot as plt
import collections as cl
import sys
import argparse

from util import load_trace
import util.videoInfo as video
from util.p2pnetwork import P2PNetwork
import util.randStateInit as randstate
from simenv.GroupP2PBasic import GroupP2PBasic
from simenv.GroupP2PDeter import GroupP2PDeter
from simenv.GroupP2PDeterRemoteBuf import GroupP2PDeter as GrpDeterRemote
from simenv.GroupP2PDeterRemoteBufShared import GroupP2PDeterShared
from simenv.Simple import Simple
from simenv.DHT import DHT
from simulator.simulator import Simulator
from util.group import GroupManager
# from simenv.SimpleP2P import experimentSimpleP2P
from abr.FastMPC import AbrFastMPC
from abr.RobustMPC import AbrRobustMPC
from abr.BOLA import BOLA
from util.cdnUsages import CDN
from util.segmentRequest import SegmentUsage

from test_shared_dl import SharedDownloader

AbrPensieve = None
GroupP2PRNN = None
GroupP2PDeterQaRNN = None

SHARED_LINK_ENABLED = False


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
        if name not in ["GrpDeter", "GroupP2PBasic"]:
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
    pltCoreTitle = "coreNetworkUsage"
    pltCoreData = []

    for name, res in cdns.items():
        Xs, Ys = list(zip(*res.uploaded))
        savePlotData(Xs, Ys, name, pltTitle)
        plt.plot(Xs, Ys, label=name)

        Xs, Ys = list(zip(*res.uploadRequests))
        savePlotData(Xs, Ys, name + "_cnt", pltTitle)

        Xs, Ys = list(zip(*res.throughputGran(60000)))
        savePlotData(Xs, Ys, name, pltCoreTitle)
        pltCoreData += [(Xs, Ys, name)]

    plt.legend(ncol = 2, loc = "upper center")
    plt.title(pltTitle)
    dpath = os.path.join(RESULT_DIR, pltTitle.replace(" ", "_"))
    plt.savefig(dpath + "_cmf.eps", bbox_inches="tight")
    plt.savefig(dpath + "_cmf.png", bbox_inches="tight")

    plt.clf()
    plt.rc('font', **font)
    plt.figure(figsize=figsize, dpi=150)
    for x in pltCoreData:
        plt.plot(x[0], x[1], label=x[2])
    plt.legend(ncol = 2, loc = "upper center")
    plt.title(pltCoreTitle)
    dpath = os.path.join(RESULT_DIR, pltCoreTitle.replace(" ", "_"))
    plt.savefig(dpath + ".eps", bbox_inches="tight")
    plt.savefig(dpath + ".png", bbox_inches="tight")




def measureBenefit(results, lonePeers):
    if "GrpDeterRm" not in results:
        return
    dags = {n.networkId:n for n in results["GrpDeterRm"]}
    RES_PATH = "./results/benefit/"
    for name, res in results.items():
        if name == "GrpDeterRm":
            continue
        ags = {n.networkId:n for n in res}
        benQoE = []
        benQ = []
        for n in ags:
            assert n in dags
            if n in lonePeers:
                continue
            qoep = ags[n]._vAgent.QoE
            qoed = dags[n]._vAgent.QoE
            benQoE.append((qoed - qoep)/abs(qoep))
            avqp = ags[n]._vAgent.avgBitrate
            avqd = dags[n]._vAgent.avgBitrate
            benQ.append((avqd - avqp)/abs(avqp))

        benQoEDir = os.path.join(RES_PATH, "QoE")
        if not os.path.isdir(benQoEDir):
            os.makedirs(benQoEDir)
        benQDir = os.path.join(RES_PATH, "bitrate")
        if not os.path.isdir(benQDir):
            os.makedirs(benQDir)

        with open(os.path.join(benQoEDir, name + ".dat"), "w") as fp:
            print(*benQoE, sep="\n", file = fp)
        with open(os.path.join(benQDir, name + ".dat"), "w") as fp:
            print(*benQ, sep="\n", file = fp)


GLOBAL_STARTS_AT = 5

def getDict(**kws):
    return kws

def runExperiments(envCls, traces, vi, network, abr = BOLA, result_dir=None, modelPath = None):
    simulator = Simulator()
    grp = GroupManager(4, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []
    players = len(list(network.nodes()))
    idxs = [x%len(traces) for x in range(players)] #np.random.randint(len(traces), size=players)
    startsAts = np.random.randint(GLOBAL_STARTS_AT + 1, vi.duration/2, size=players)
    CDN.clear()
    SegmentUsage.clear()

    sharedLink = None
    if SHARED_LINK_ENABLED:
        sharedLink = SharedDownloader(simulator, linkCapa = 10*len(list(network.nodes()))*1000*1000)
    for x, nodeId in enumerate(network.nodes()):
        idx = idxs[x]
        trace = traces[idx]
        startsAt = startsAts[x]
        env = envCls(vi = vi, traces = trace, simulator = simulator, grp=grp, peerId=nodeId, abr=abr, logpath=result_dir, modelPath=modelPath, sharedLink=sharedLink)
        simulator.runAt(startsAt, env.start, GLOBAL_STARTS_AT)
        ags.append(env)
    simulator.run()
    for i,a in enumerate(ags):
        assert a._vFinished and a._vAgent._vFinished # or a._vDead
    return ags, CDN.getInstance(), SegmentUsage.getInstance() #cdn is singleton, so it is perfectly okay get the instance

def importLearningModules(allowed):
    global AbrPensieve, GroupP2PRNN, GroupP2PDeterQaRNN
    if "Penseiv" in allowed and AbrPensieve is None:
        from abr.Pensiev import AbrPensieve as abp
        AbrPensieve = abp

    if "GroupP2PRNN" in allowed and GroupP2PRNN is None:
        from simenv.GroupP2PRNNTest import GroupP2PRNN as obj
        GroupP2PRNN = obj

    if "GroupP2PDeterQaRNN" in allowed and GroupP2PDeterQaRNN is None:
        from simenv.GroupP2PDeterQaRNN import GroupP2PDeterQaRNN as obj
        GroupP2PDeterQaRNN = obj


def getTestObj(traces, vi, network):
    testCB = {}
    #envCls, traces, vi, network, abr = BOLA, result_dir=None, modelPath = None, rnnAgentModule=None, rnnQualityModule=None
    testCB["BOLA"] = getDict(envCls=Simple, traces=traces, vi=vi, network=network, abr=BOLA)
    testCB["FastMPC"] = getDict(envCls=Simple, traces=traces, vi=vi, network=network, abr=AbrFastMPC)
    testCB["RobustMPC"] = getDict(envCls=Simple, traces=traces, vi=vi, network=network, abr=AbrRobustMPC)
    testCB["Penseiv"] = getDict(envCls=Simple, traces=traces, vi=vi, network=network, abr=AbrPensieve)
    testCB["GroupP2PBasic"] = getDict(envCls=GroupP2PBasic, traces=traces, vi=vi, network=network)
    testCB["DHTEnvironment"] = getDict(envCls=DHT, traces=traces, vi=vi, network=network)
    testCB["GroupP2PRNN"] = getDict(envCls=GroupP2PRNN, traces=traces, vi=vi, network=network, abr=BOLA, result_dir=None, modelPath="ResModelPathRNN/")
    testCB["GrpDeter"] = getDict(envCls=GroupP2PDeter, traces=traces, vi=vi, network=network, abr=BOLA, result_dir=None, modelPath="ResModelPathRNN/")
    testCB["GrpDeterRm"] = getDict(envCls=GrpDeterRemote, traces=traces, vi=vi, network=network, abr=BOLA, result_dir=None)
    testCB["GrpDeterShared"] = getDict(envCls=GroupP2PDeterShared, traces=traces, vi=vi, network=network, abr=BOLA, result_dir=None)
    testCB["GroupP2PDeterQaRNN"] = getDict(envCls=GroupP2PDeterQaRNN, traces=traces, vi=vi, network=network, abr=BOLA, result_dir=None, modelPath="ResModelPathRNNQa/")

    return testCB

def parseArg(experiments):
    global EXIT_ON_CRASH, MULTI_PROC, SHARED_LINK_ENABLED
    parser = argparse.ArgumentParser(description='Experiment')
    parser.add_argument('--exit-on-crash',  help='Program will exit after first crash', action="store_true")
    parser.add_argument('--no-slave-proc',  help='No new Process will created for slave', action="store_true")
    parser.add_argument('--no-quality-rnn-proc',  help='Quality rnn will run in same process as parent', action="store_true")
    parser.add_argument('--no-agent-rnn-proc',  help='Agent rnn will run in same process as parent', action="store_true")
    parser.add_argument('--shared-link', help="Add link as sharedLink", action="store_true")
    parser.add_argument('exp', help=experiments, nargs='+')
    args = parser.parse_args()
    EXIT_ON_CRASH = args.exit_on_crash
    MULTI_PROC = not args.no_slave_proc

    if args.shared_link:
        SHARED_LINK_ENABLED = True

    if "EXP_ENV_LEARN_PROC_QUALITY" in os.environ:
        del os.environ["EXP_ENV_LEARN_PROC_QUALITY"]
    if "EXP_ENV_LEARN_PROC_AGENT" in os.environ:
        del os.environ["EXP_ENV_LEARN_PROC_AGENT"]
    if args.no_quality_rnn_proc:
        os.environ["EXP_ENV_LEARN_PROC_QUALITY"] = "NO"
    elif args.no_agent_rnn_proc:
        os.environ["EXP_ENV_LEARN_PROC_AGENT"] = "NO"

    return args.exp


def main():
    allowed = ["BOLA", "FastMPC", "RobustMPC", "Penseiv", "GroupP2PBasic", "DHTEnvironment", "GroupP2PRNN", "GrpDeter", "GrpDeterRm", "GrpDeterShared", "GroupP2PDeterQaRNN"]

    allowed = parseArg(" ".join([f"'{x}'" for x in allowed]))

    importLearningModules(allowed)
#     randstate.storeCurrentState() #comment this line to use same state as before
    randstate.loadCurrentState()
    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    vi = video.loadVideoTime("./videofilesizes/sizes_qBVThFwdYTc.py")
#     vi = video.loadVideoTime("./videofilesizes/sizes_penseive.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()
#     network = P2PNetwork("/tmp/dummygrp.txt")
    testCB = getTestObj(traces, vi, network)
    results = {}
    cdns = {}
    segUses = {}

#     for name, cb in testCB.items():
    for name in allowed:
        assert name in testCB
        cb = testCB[name]
        randstate.loadCurrentState()
        ags, cdn, segUse = runExperiments(**cb)
        results[name] = ags
        cdns[name] = cdn
        segUses[name] = segUse

    print("ploting figures")
    print("="*30)

    lonePeers = findIgnorablePeers(results)

    plotAgentsData(results, "_vAgent.QoE", "QoE", "Player Id", lonePeers)
    plotAgentsData(results, "_vAgent.avgBitrate", "Average bitrate played", "Player Id", lonePeers)
    plotAgentsData(results, "_vAgent.avgQualityIndex", "Average quality index played", "Player Id", lonePeers)
    plotAgentsData(results, "_vAgent.avgQualityIndexVariation", "Average quality index variation", "Player Id", lonePeers)
    plotAgentsData(results, "_vAgent.avgStallTime", "Stall Time", "Player Id", lonePeers)
    plotAgentsData(results, "_vAgent.startUpDelay", "Start up delay", "Player Id", lonePeers)
    plotAgentsData(results, "idleTime", "IdleTime", "Player Id", lonePeers)
    plotAgentsData(results, "_vAgent.avgBitrateVariation", "Average Bitrate Variation", "Player Id", lonePeers)
    plotAgentsData(results, "totalWorkingTime", "workingTime", "Player Id", lonePeers)

    plotCDNData(cdns)

    measureBenefit(results, lonePeers)
#     plt.show()

#     plotBufferLens(results)
#     plotIdleStallTIme(results)



if __name__ == "__main__":
#     for x in range(20):
        main()
#     main2()
