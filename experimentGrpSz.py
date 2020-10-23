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
from simenv.FLiDASH import FLiDASH as GrpDeterRemote
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
import shutil

AbrPensieve = None
GroupP2PRNN = None
GroupP2PDeterQaRNN = None


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
        if name not in ["GrpDeter", "GroupP2PBasic"]:
            continue
        for ag in res:
            if not ag._vGroup or ag._vGroup.isLonepeer(ag) or len(ag._vGroupNodes) != ag._vGroup.peersPerGroup:
                p.add(ag.networkId)
    return p


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

def plotCDNData(grpSz, cdns):
    font = {'family' : 'normal',
            'weight' : 'bold',
            'size'   : 22}

    figsize=(7, 5)
    pltData = {}
    pltTitle = "cdnUploaded"
    for name, res in cdns.items():
        Xs, Ys = list(zip(*res.uploaded))
        savePlotData(Xs, Ys, name + "_" + str(grpSz), pltTitle)

        Xs, Ys = list(zip(*res.uploadRequests))
        savePlotData(Xs, Ys, name + "_" + str(grpSz) + "_cnt", pltTitle)


def plotSegUseData(grpSz, segUses, pltTitle):
    font = {'family' : 'normal',
            'weight' : 'bold',
            'size'   : 22}

    figsize=(7, 5)
#     plt.clf()
#     plt.rc('font', **font)
#     plt.figure(figsize=figsize, dpi=150)
    pltData = {}


    dpath = os.path.join(RESULT_DIR, pltTitle.replace(" ", "_"))
    if not os.path.isdir(dpath):
        os.makedirs(dpath)

    for name, res in segUses.items():
        dlCnt   = res._vDownloadCnt
        dlBytes = res._vDownloadBytes
        plCnt   = res._vPlayedCnt
        plBytes = res._vPlayedBytes

        wastage = res.getWastage()

        segUseFreq = res.getPlaybackFreq()

        pltData[name] = (dlCnt, dlBytes, plCnt, plBytes, wastage)

        Xs, Ys = list(zip(*getCMF(segUseFreq)))
        savePlotData(Xs, Ys, name + "_" + str(grpSz) + "_cnt", pltTitle)
        with open(dpath + "/segUse.dat", "a") as fp:
            print("#grpSz, dlCnt, dlBytes, plCnt, plBytes, wastage", file=fp)
            print(grpSz, dlCnt, dlBytes, plCnt, plBytes, wastage, file=fp)


    return pltData


GLOBAL_STARTS_AT = 5

def getDict(**kws):
    return kws

def runExperiments(grpSz, envCls, traces, vi, network, abr = BOLA, result_dir=None, modelPath = None):
    simulator = Simulator()
    grp = GroupManager(grpSz, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []
    players = len(list(network.nodes()))
    idxs = [x%len(traces) for x in range(players)] #np.random.randint(len(traces), size=players)
    startsAts = np.random.randint(GLOBAL_STARTS_AT + 1, vi.duration/2, size=players)
    CDN.clear()
    SegmentUsage.clear()
    for x, nodeId in enumerate(network.nodes()):
        idx = idxs[x]
        trace = traces[idx]
        startsAt = startsAts[x]
        env = envCls(vi = vi, traces = trace, simulator = simulator, grp=grp, peerId=nodeId, abr=abr, logpath=result_dir, modelPath=modelPath)
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
    testCB["GroupP2PDeterQaRNN"] = getDict(envCls=GroupP2PDeterQaRNN, traces=traces, vi=vi, network=network, abr=BOLA, result_dir=None, modelPath="ResModelPathRNNQa/")

    return testCB

def parseArg(experiments):
    global EXIT_ON_CRASH, MULTI_PROC
    parser = argparse.ArgumentParser(description='Experiment')
    parser.add_argument('--exit-on-crash',  help='Program will exit after first crash', action="store_true")
    parser.add_argument('--no-slave-proc',  help='No new Process will created for slave', action="store_true")
    parser.add_argument('--no-quality-rnn-proc',  help='Quality rnn will run in same process as parent', action="store_true")
    parser.add_argument('--no-agent-rnn-proc',  help='Agent rnn will run in same process as parent', action="store_true")
    parser.add_argument('exp', help=experiments, nargs='+')
    args = parser.parse_args()
    EXIT_ON_CRASH = args.exit_on_crash
    MULTI_PROC = not args.no_slave_proc
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
    allowed = ["BOLA", "FastMPC", "RobustMPC", "Penseiv", "GroupP2PBasic", "DHTEnvironment", "GroupP2PRNN", "GrpDeter", "GrpDeterRm", "GroupP2PDeterQaRNN"]

    allowed = parseArg(" ".join([f"'{x}'" for x in allowed]))

    importLearningModules(allowed)
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
    testCB = getTestObj(traces, vi, network)

    segUsages = {}

    if os.path.exists(RESULT_DIR):
       shutil.rmtree(RESULT_DIR)

    for grpSz in [3, 4, 5, 6, 7, 8, 9, 10]:
#     for grpSz in [10]:
        results = {}
        cdns = {}
        segUses = {}
        for name in allowed:
            assert name in testCB
            cb = testCB[name]
            randstate.loadCurrentState()
            ags, cdn, segUse = runExperiments(grpSz = grpSz, **cb)
            results[name] = ags
            cdns[name] = cdn
            segUses[name] = segUse

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
        plotAgentsData(grpSz, results, "_vRPCCont", "Small message passing", "Player Id", lonePeers)
        plotAgentsData(grpSz, results, "totalWorkingTime", "workingTime", "Player Id", lonePeers)
        plotAgentsData(grpSz, results, "_vRPCCont", "Small message passing", "Player Id", lonePeers)
        plotAgentsData(grpSz, results, "downloadCnt", "Normal Download Count", "Player Id", lonePeers)
        plotAgentsData(grpSz, results, "forceDownloadRatio", "Force Download Ratio", "Player Id", lonePeers)
        plotAgentsData(grpSz, results, "groupContriCount", "Group Contri Ratio", "Player Id", lonePeers)

        plotCDNData(grpSz, cdns)

        segUsages[grpSz] = plotSegUseData(grpSz, segUses, pltTitle = "segWatage")




#     plt.show()

#     plotBufferLens(results)
#     plotIdleStallTIme(results)



if __name__ == "__main__":
#     for x in range(20):
        main()
#     main2()
