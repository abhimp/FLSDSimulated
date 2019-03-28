import os
import sys
import load_trace
import pickle
import numpy as np
import glob
import matplotlib.pyplot as plt
import collections as cl


RESULT_DIR = "./plotData/"

def getCMF(elements):
    x = [y for y in elements]
    freq = list(cl.Counter(x).items())
    freq.sort(key = lambda x:x[0])
    x,y = zip(*freq)
    s = sum(y)
    cmf = [(p, float(sum(y[:i+1]))/s) for i, p in enumerate(x)]
    return cmf

def restorePlotData(legend, pltTitle, result_dir):
    dpath = os.path.join(result_dir, pltTitle.replace(" ", "_"))
    fpath = os.path.join(dpath, legend + ".dat")
    assert os.path.isfile(fpath)
    with open(fpath) as fp:
        data = []
        for line in fp:
            p = [float(x) for x in line.strip().split()]
            data.append(p[:2])
        Xs, Ys = list(zip(*data))
        assert len(Xs) == len(Ys)
        return Xs, Ys

def restorePlotDataAllTC(legend, pltTitle, result_dir):
    Xs, Ys = [], []
    for tc in ["tc1", "tc2", "tc3"]:
        resDir = os.path.join(result_dir, tc)
        x, y = restorePlotData(legend, pltTitle, resDir)
        Xs += x
        Ys += y
    return Xs, Ys

def restorePlotDataAllVid(legend, pltTitle, result_dir):
    Xs, Ys = [], []
    for vidPath in glob.glob("videofilesizes/sizes_*.py"):
        resDir = os.path.join(result_dir, os.path.basename(vidPath))
        x, y = restorePlotDataAllTC(legend, pltTitle, resDir)
        Xs += x
        Ys += y
    return Xs, Ys

def plotStoredData(legends, pltTitle, xlabel):
    plt.clf()
    plt.figure(figsize=(15, 5), dpi=150)
    pltData = {}
    resDir = os.path.join(RESULT_DIR, "powertest")
    for name in legends:
        Xs, Ys = restorePlotDataAllVid(name, pltTitle, resDir)
        pltData[name] = Ys
        Xs, Ys = list(zip(*getCMF(Ys)))
        plt.plot(Xs, Ys, label=name)

    plt.legend(ncol = 2, loc = "upper center")
    plt.title(pltTitle)
    dpath = os.path.join(RESULT_DIR, pltTitle.replace(" ", "_"))
    plt.savefig(dpath + "_cmf.png", bbox_inches="tight")


    plt.clf()
    names, Yss = list(zip(*pltData.items()))
    plt.boxplot(Yss, labels=names, notch=True, showmeans=True, showfliers=False)
    plt.title(pltTitle)
    plt.savefig(dpath + "_box.png", bbox_inches="tight")

def main():

    testCB = {}
    testCB["BOLA"] = ()
    testCB["FastMPC"] = ()
#     testCB["RobustMPC"] = ()
    testCB["Penseiv"] = ()
    testCB["GroupP2PBasic"] = ()
    testCB["GroupP2PTimeout"] = ()

    results = [x for x, y in testCB.items()]

    plotStoredData(results, "QoE", "Player Id")
    plotStoredData(results, "Average bitrate played", "Player Id")
    plotStoredData(results, "Average quality index played", "Player Id")
    plotStoredData(results, "Average quality index variation", "Player Id")
    plotStoredData(results, "Stall Time", "Player Id")
    plotStoredData(results, "Start up delay", "Player Id")
    plotStoredData(results, "IdleTime", "Player Id")
    plotStoredData(results, "workingTime", "Player Id")



if __name__ == "__main__":
    main()
