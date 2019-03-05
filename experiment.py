import os
import load_trace
import videoInfo as video
from p2pnetwork import P2PNetwork
import randStateInit as randstate

from envGroupP2P_2 import experimentGroupP2P
from envSimple import experimentSimpleEnv
from envSimpleP2P import experimentSimpleP2P

from abrFastMPC import AbrFastMPC
from abrRobustMPC import AbrRobustMPC
from abrBOLA import BOLA
from abrPensiev import AbrPensieve

import matplotlib.pyplot as plt

RESULT_DIR = "./results/"
BUFFER_LEN_PLOTS = "bufferlens"

def savePlotData(Xs, Ys, legend, pltTitle):
    dpath = os.path.join(RESULT_DIR, pltTitle.replace(" ", "_"))
    if not os.path.isdir(dpath):
        os.makedirs(dpath)
    fpath = os.path.join(dpath, legend + "d.dat")
    with open(fpath, "w") as fp:
        assert len(Xs) == len(Ys)
        st = "\n".join(str(x) + "\t" + str(y) for x, y in zip(Xs, Ys))
        fp.write(st)

def restorePlotData(legend, pltTitle):
    dpath = os.path.join(RESULT_DIR, pltTitle.replace(" ", "_"))
    fpath = os.path.join(dpath, legend + "d.dat")
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

def plotAgentsData(results, attrib, pltTitle, xlabel):
#     plt.clf()
    plt.figure()
    pltData = []
    for name, res in results.items():
        Xs, Ys = [], []
        for x, ag in enumerate(res):
            y = eval("ag." + attrib)
            Xs.append(x)
            Ys.append(y)
        savePlotData(Xs, Ys, name, pltTitle)
        pltData += [Xs, Ys]
        plt.scatter(Xs, Ys, label=name)
    plt.legend(ncol = 2, loc = "upper center")
    plt.title(pltTitle)
    plt.xlabel(xlabel)
#     plt.show()

def plotBufferLens(results):
    dpath = os.path.join(RESULT_DIR, BUFFER_LEN_PLOTS)
    if not os.path.isdir(dpath):
        os.makedirs(dpath)
    models = list(results.keys())
    res = [results[r] for r in models]
    res = list(zip(*res))

    for it,exp in enumerate(res):
        plt.clf()
        plt.figure(figsize=(15, 5), dpi=150)
        fig, ax1 = plt.subplots(figsize=(15, 5), dpi=150)
        ax2 = ax1.twinx()
        for i, ag in enumerate(exp):
            pltData = ag._vAgent._vBufferLenOverTime
            Xs, Ys = list(zip(*pltData))
            ax1.plot(Xs, Ys, label=models[i] + "-buffLen")
            
            pltData = ag._vAgent._vQualitiesPlayedOverTime
            Xs, Ys = list(zip(*pltData))
            ax2.step(Xs, Ys, label=models[i]+"-quality", where="post")
        fig.legend(ncol = 2, loc = "upper center")
        pltPath = os.path.join(dpath,"%04d.png"%(it))
        fig.savefig(pltPath, bbox_inches="tight")

def runExperiments(cb, *kw, **kws):
    return cb(*kw, **kws)

def main():
#     randstate.storeCurrentState() #comment this line to use same state as before
    randstate.loadCurrentState()
    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()
    
    testCB = {}
    testCB["SimpleEnv-BOLA"] = (experimentSimpleEnv, traces, vi, network, BOLA)
#     testCB["SimpleEnv-FastMPC"] = (experimentSimpleEnv, traces, vi, network, AbrFastMPC)
#     testCB["SimpleEnv-RobustMPC"] = (experimentSimpleEnv, traces, vi, network, AbrRobustMPC)
#     testCB["SimpleEnv-Penseiv"] = (experimentSimpleEnv, traces, vi, network, AbrPensieve)
    testCB["GroupP2P"] = (experimentGroupP2P, traces, vi, network)
#     testCB["SimpleP2P"] = (experimentSimpleP2P, traces, vi, network)

    results = {}

    for name, cb in testCB.items():
        randstate.loadCurrentState()
        ags = runExperiments(*cb)
        results[name] = ags

    print("ploting figures")
    print("="*30)

    plotAgentsData(results, "_vAgent.QoE", "QoE", "Player Id")
    plotAgentsData(results, "_vAgent.avgBitrate", "Average bitrate played", "Player Id")
    plotAgentsData(results, "_vAgent.avgQualityIndex", "Average quality index played", "Player Id")
    plotAgentsData(results, "_vAgent.avgQualityIndexVariation", "Average quality index variation", "Player Id")
    plotAgentsData(results, "_vAgent.totalStallTime", "Stall Time", "Player Id")
    plotAgentsData(results, "_vAgent.startUpDelay", "Start up delay", "Player Id")
    plotAgentsData(results, "idleTime", "IdleTime", "Player Id")
    plotAgentsData(results, "totalWorkingTime", "workingTime", "Player Id")


    plt.show()

    plotBufferLens(results)


def main2():
    testCB = {}
    testCB["SimpleEnv-BOLA"] = (experimentSimpleEnv)
    testCB["SimpleEnv-FastMPC"] = (experimentSimpleEnv)
    testCB["SimpleEnv-RobustMPC"] = (experimentSimpleEnv)
#     testCB["SimpleEnv-Penseiv"] = (experimentSimpleEnv, traces, vi, network, AbrPensieve)
    testCB["GroupP2P"] = (experimentGroupP2P)
#     testCB["SimpleP2P"] = experimentSimpleP2P

    results = [x for x in testCB]

    plotAgentsData(results, "_vAgent.QoE", "QoE", "Player Id")
    plotAgentsData(results, "_vAgent.avgBitrate", "Average bitrate played", "Player Id")
    plotAgentsData(results, "_vAgent.avgQualityIndex", "Average quality index played", "Player Id")
    plotAgentsData(results, "_vAgent.avgQualityIndexVariation", "Average quality index variation", "Player Id")
    plotAgentsData(results, "_vAgent.totalStallTime", "Stall Time", "Player Id")
    plotAgentsData(results, "_vAgent.startUpDelay", "Start up delay", "Player Id")
    plotAgentsData(results, "idleTime", "IdleTime", "Player Id")
    plotAgentsData(results, "totalWorkingTime", "workingTime", "Player Id")


    plt.show()

if __name__ == "__main__":
    main()
#     main2()
