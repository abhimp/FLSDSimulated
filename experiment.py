import load_trace
import videoInfo as video
from p2pnetwork import P2PNetwork
import randStateInit as randstate

from envGroupP2P import experimentGroupP2P
from envSimple import experimentSimpleEnv
from envSimpleP2P import experimentSimpleP2P

import matplotlib.pyplot as plt

def plotAvgBitRate(results):
#     plt.clf()
    plt.figure()
    pltData = []
    for name, res in results.items():
        Xs, Ys = [], []
        for x, ag in enumerate(res):
            y = ag._vAgent.avgBitrate
            Xs.append(x)
            Ys.append(y)
        pltData += [Xs, Ys]
        plt.plot(Xs, Ys, label=name)
    plt.legend(ncol = 2, loc = "upper center")
    plt.title("Average Bitrate played")
    plt.xlabel("Player Id")
#     plt.show()

def plotAvgQualityIndex(results):
#     plt.clf()
    plt.figure()
    pltData = []
    for name, res in results.items():
        Xs, Ys = [], []
        for x, ag in enumerate(res):
            y = ag._vAgent.avgQualityIndex
            Xs.append(x)
            Ys.append(y)
        pltData += [Xs, Ys]
        plt.plot(Xs, Ys, label=name)
    plt.legend(ncol = 2, loc = "upper center")
    plt.title("Average Quality Index played")
    plt.xlabel("Player Id")
#     plt.show()

def plotAvgQualityIndexVariation(results):
#     plt.clf()
    plt.figure()
    pltData = []
    for name, res in results.items():
        Xs, Ys = [], []
        for x, ag in enumerate(res):
            y = ag._vAgent.avgQualityIndexVariation
            Xs.append(x)
            Ys.append(y)
        pltData += [Xs, Ys]
        plt.plot(Xs, Ys, label=name)
    plt.legend(ncol = 2, loc = "upper center")
    plt.title("Average Quality Index variation")
    plt.xlabel("Player Id")
#     plt.show()

def plotQoE(results):
#     plt.clf()
    plt.figure()
    pltData = []
    for name, res in results.items():
        Xs, Ys = [], []
        for x, ag in enumerate(res):
            y = ag._vAgent.QoE
            Xs.append(x)
            Ys.append(y)
        pltData += [Xs, Ys]
        plt.plot(Xs, Ys, label=name)
    plt.legend(ncol = 2, loc = "upper center")
    plt.title("QoE")
    plt.xlabel("Player Id")
#     plt.show()

def plotStallTime(results):
#     plt.clf()
    plt.figure()
    pltData = []
    for name, res in results.items():
        Xs, Ys = [], []
        for x, ag in enumerate(res):
            y = ag._vAgent.totalStallTime
            Xs.append(x)
            Ys.append(y)
        pltData += [Xs, Ys]
        plt.plot(Xs, Ys, label=name)
    plt.legend(ncol = 2, loc = "upper center")
    plt.title("Total stall time")
    plt.xlabel("Player Id")
#     plt.show()

def plotStartupDelay(results):
#     plt.clf()
    plt.figure()
    pltData = []
    for name, res in results.items():
        Xs, Ys = [], []
        for x, ag in enumerate(res):
            y = ag._vAgent.startUpDelay
            Xs.append(x)
            Ys.append(y)
        pltData += [Xs, Ys]
        plt.plot(Xs, Ys, label=name)
    plt.legend(ncol = 2, loc = "upper center")
    plt.title("start up delay")
    plt.xlabel("Player Id")
#     plt.show()

def runExperiments(cb, traces, vi, network):
    return cb(traces, vi, network)

def main():
#     randstate.storeCurrentState() #comment this line to use same state as before
    randstate.loadCurrentState()
    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()
    
    testCB = {}
    testCB["SimpleEnv"] = experimentSimpleEnv
    testCB["GroupP2P"] = experimentGroupP2P
#     testCB["SimpleP2P"] = experimentSimpleP2P

    results = {}

    for name, cb in testCB.items():
        randstate.loadCurrentState()
        ags = runExperiments(cb, traces, vi, network)
        results[name] = ags

    plotQoE(results) 
    plotAvgBitRate(results)
    plotAvgQualityIndex(results)
    plotAvgQualityIndexVariation(results)
    plotStallTime(results)
    plotStartupDelay(results)

    plt.show()


#         experimentGroupP2P(traces, vi, network)
#         experimentSimpleEnv(traces, vi, network)
#         experimentSimpleP2P(traces, vi, network)


if __name__ == "__main__":
    main()
