import os
import sys
import load_trace
import pickle
import numpy as np
import glob

import videoInfo as video
from envGroupP2PTimeoutRNN import GroupP2PEnvTimeoutRNN
from envSimple import SimpleEnvironment
from simulator import Simulator
from group import GroupManager
from p2pnetwork import P2PNetwork
from rnnTimeout import getPensiveLearner, saveLearner
# from envSimpleP2P import experimentSimpleP2P

RESULT_DIR = "results"

def savePlotData(Xs, Ys, Zs, legend, pltTitle, result_dir):
    dpath = os.path.join(result_dir, pltTitle.replace(" ", "_"))
    if not os.path.isdir(dpath):
        os.makedirs(dpath)
    fpath = os.path.join(dpath, legend + ".dat")
    with open(fpath, "w") as fp:
        assert len(Xs) == len(Ys)
        st = "\n".join(str(x) + "\t" + str(y) + "\t" + str(z) for x, y, z in zip(Xs, Ys, Zs))
        fp.write(st)

def saveRawResults(results, result_dir):
    dpath = os.path.join(result_dir, "raw_results")
    if not os.path.isdir(dpath):
        os.makedirs(dpath)
    for name, res in results.items():
        fpath = os.path.join(dpath, name + ".dat")
        with open(fpath, "wb") as f:
            pickle.dump(res, f, pickle.HIGHEST_PROTOCOL)
            print("saved")


def plotAgentsData(results, attrib, pltTitle, xlabel, result_dir):
    assert min([len(res) for name, res in results.items()]) == max([len(res) for name, res in results.items()])
    pltData = {}
    for name, res in results.items():
        Xs, Ys, Zs = [], [], []
        for x, ag in enumerate(res):
            y = eval("ag." + attrib)
            z = ag.networkId
            Xs.append(x)
            Ys.append(y)
            Zs.append(y)

        savePlotData(Xs, Ys, Zs, name, pltTitle, result_dir)

def runExperiments(envCls, traces, vi, network, abr = None, result_dir = None, *kw, **kws):
    simulator = Simulator()
    grp = GroupManager(4, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []
    for x, nodeId in enumerate(network.nodes()):
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        startsAt = np.random.randint(vi.duration/2)
        env = envCls(vi = vi, traces = trace, simulator = simulator, grp=grp, peerId=nodeId, abr=abr, resultpath = result_dir, *kw, **kws)
        simulator.runAt(startsAt, env.start, 5)
        ags.append(env)
    simulator.run()
    for i,a in enumerate(ags):
        assert a._vFinished # or a._vDead
    return ags


if __name__ == "__main__":
    subjects = "GroupP2PTimeoutRNN"
    modelPath = "ModelPath"


    subjects = subjects.split(",")
    networks = glob.glob("./graph/*.txt")
    videos = glob.glob("./videofilesizes/*.py")
    traces = load_trace.load_trace()
    traces = list(zip(*traces))
    for vidPath in videos:
         vi = video.loadVideoTime(vidPath)
         for netPath in networks:
            p2p = P2PNetwork(netPath)
            if p2p.numNodes() < 10:
                continue

            for tc in ["tc1"]: #, "tc2", "tc3"]:
                result_dir = os.path.join(RESULT_DIR, tc)
                if not os.path.isdir(result_dir):
                    os.makedirs(result_dir)

                randstatefp = os.path.join(result_dir, "randstate")
                #print(GroupP2PEnvTimeoutRNN, traces, vi, p2p, None, result_dir, modelPath)
                runExperiments(GroupP2PEnvTimeoutRNN, traces, vi, p2p, None, result_dir, modelPath=modelPath)

    saveLearner()
