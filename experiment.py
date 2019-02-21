import load_trace
import videoInfo as video
from p2pnetwork import P2PNetwork
import randStateInit as randstate

from envGroupP2P import experimentGroupP2P
from envSimple import experimentSimpleEnv
from envSimpleP2P import experimentSimpleP2P

from abrFastMPC import AbrFastMPC
from abrRobustMPC import AbrRobustMPC
from abrBOLA import BOLA
from abrPensiev import AbrPensieve

import matplotlib.pyplot as plt

def plotAgentsData(results, attrib, pltTitle, xlabel):
#     plt.clf()
    plt.figure()
    pltData = []
    for name, res in results.items():
        Xs, Ys = [], []
        for x, ag in enumerate(res):
            y = eval("ag._vAgent." + attrib)
            Xs.append(x)
            Ys.append(y)
        pltData += [Xs, Ys]
        plt.plot(Xs, Ys, label=name)
    plt.legend(ncol = 2, loc = "upper center")
    plt.title(pltTitle)
    plt.xlabel(xlabel)
#     plt.show()

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
    testCB["SimpleEnv"] = (experimentSimpleEnv, traces, vi, network, BOLA)
    testCB["SimpleEnv"] = (experimentSimpleEnv, traces, vi, network, AbrFastMPC)
    testCB["SimpleEnv"] = (experimentSimpleEnv, traces, vi, network, AbrRobustMPC)
#     testCB["SimpleEnv"] = (experimentSimpleEnv, traces, vi, network, AbrPensieve)
    testCB["GroupP2P"] = (experimentGroupP2P, traces, vi, network)
#     testCB["SimpleP2P"] = experimentSimpleP2P

    results = {}

    for name, cb in testCB.items():
        randstate.loadCurrentState()
        ags = runExperiments(*cb)
        results[name] = ags

    plotAgentsData(results, "QoE", "QoE", "Player Id")
    plotAgentsData(results, "avgBitrate", "Average bitrate played`", "Player Id")
    plotAgentsData(results, "avgQualityIndex", "Average quality index played`", "Player Id")
    plotAgentsData(results, "avgQualityIndexVariation", "Average quality index variation", "Player Id")
    plotAgentsData(results, "totalStallTime", "Stall Time", "Player Id")
    plotAgentsData(results, "startUpDelay", "Start up delay", "Player Id")


    plt.show()


if __name__ == "__main__":
    main()
