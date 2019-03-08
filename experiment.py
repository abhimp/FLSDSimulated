import os
import load_trace
import videoInfo as video
from p2pnetwork import P2PNetwork
import randStateInit as randstate

from envGroupP2PBasic import experimentGroupP2PBasic
from envGroupP2PTimeout import experimentGroupP2PTimeout
from envSimple import experimentSimpleEnv
from envSimpleP2P import experimentSimpleP2P

from abrFastMPC import AbrFastMPC
from abrRobustMPC import AbrRobustMPC
from abrBOLA import BOLA
from abrPensiev import AbrPensieve

import matplotlib.pyplot as plt
import mpld3

import collections as cl

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
    plt.figure(figsize=(15, 5), dpi=150)
    pltData = []
    for name, res in results.items():
        Xs, Ys = [], []
        for x, ag in enumerate(res):
            y = eval("ag." + attrib)
            Xs.append(x)
            Ys.append(y)
#         Xs, Ys = list(zip(*getCMF(Ys)))
        savePlotData(Xs, Ys, name, pltTitle)
        pltData += [Xs, Ys]
        plt.hist(Ys, label=name, rwidth=0.05, histtype="bar")
    plt.legend(ncol = 2, loc = "upper center")
    plt.title(pltTitle)
    plt.xlabel(xlabel)
    dpath = os.path.join(RESULT_DIR, pltTitle.replace(" ", "_"))
    plt.savefig(dpath + ".png", bbox_inches="tight")
#     plt.show()


def plotBufferLens(results):
    dpath = os.path.join(BUFFER_LEN_PLOTS)
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
            ax1.plot(Xs, Ys, marker="x", label=models[i] + "-buffLen")

            pltData = ag._vAgent._vQualitiesPlayedOverTime
            Xs, Ys = list(zip(*pltData))
            ax2.step(Xs, Ys, marker="o", label=models[i]+"-quality", where="post")
        fig.legend(ncol = 2, loc = "upper center")
        pltPath = os.path.join(dpath,"%04d.png"%(it))
        fig.savefig(pltPath, bbox_inches="tight")



def storeAsPlotViewer(path, fig, ag):
    with open(path, "a") as fp:
        print("<br><br>", file=fp)
        print("<div><b>", ag, "</b></div>", file=fp)
        print('<div style="float:left; display:inline-block; width:95%">', file=fp)
        mpld3.save_html(fig, fp)
        print('</div><div style="clear:both"></div><br>', file=fp)
        
def plotIdleStallTIme(results):
    dpath = os.path.join(STALLTIME_IDLETIME_PLOTS)
    if not os.path.isdir(dpath):
        os.makedirs(dpath)
    models = list(results.keys())
    res = [results[r] for r in models]
    res = list(zip(*res))

    colors = ["blue", "green", "red", "cyan", "magenta", "yellow", "black"]
    
    pltHtmlPath = os.path.join(dpath,"plot.html")
    open(pltHtmlPath, "w").close()
    for it,exp in enumerate(res):
        plt.clf()
        plt.figure(figsize=(15, 7), dpi=100)
        fig, ax1 = plt.subplots(figsize=(15, 7), dpi=90)
        for i, ag in enumerate(exp):
            pltData = ag._vAgent._vBufferLenOverTime
            Xs, Ys = list(zip(*pltData))
            ax1.plot(Xs, Ys, marker="x", label=models[i] + "-buffLen", c=colors[(2*i)%len(colors)])

            pltData = ag._vIdleTimes
            Xs, Ys = list(zip(*pltData))
            ax1.step(Xs, Ys, marker="o", label=models[i]+"-quality", where="post", c=colors[(2*i+1)%len(colors)])

        fig.legend(ncol = 2, loc = "upper center")
        pltPath = os.path.join(dpath,"%04d.png"%(it))
        ag = exp[models.index("GroupP2PBasic")]
        label = "PeerId" + str(ag._vPeerId) 
        label += " NumNode:" + str(len(ag._vGroup.getAllNode(ag))) 
        label += " Quality Index: " + str(ag._vGroup.getQualityLevel(ag))
#         fig.savefig(pltPath, bbox_inches="tight")

        storeAsPlotViewer(pltHtmlPath, fig, label)

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
#     testCB["SimpleEnv-BOLA"] = (experimentSimpleEnv, traces, vi, network, BOLA)
#     testCB["SimpleEnv-FastMPC"] = (experimentSimpleEnv, traces, vi, network, AbrFastMPC)
#     testCB["SimpleEnv-RobustMPC"] = (experimentSimpleEnv, traces, vi, network, AbrRobustMPC)
#     testCB["SimpleEnv-Penseiv"] = (experimentSimpleEnv, traces, vi, network, AbrPensieve)
    testCB["GroupP2PBasic"] = (experimentGroupP2PBasic, traces, vi, network)
    testCB["GroupP2PTimeout"] = (experimentGroupP2PTimeout, traces, vi, network)
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


#     plt.show()

#     plotBufferLens(results)
#     plotIdleStallTIme(results)


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
