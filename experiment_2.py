import os
import sys
import load_trace
import pickle
import numpy as np

import videoInfo as video
from p2pnetwork import P2PNetwork
import randStateInit as randstate
from envGroupP2PBasic import GroupP2PEnvBasic
from envGroupP2PTimeout import GroupP2PEnvTimeout
from envSimple import SimpleEnvironment
from simulator import Simulator
from group import GroupManager
# from envSimpleP2P import experimentSimpleP2P
from abrFastMPC import AbrFastMPC
from abrRobustMPC import AbrRobustMPC
from abrBOLA import BOLA
from abrPensiev import AbrPensieve

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

def runExperiments(envCls, traces, vi, network, abr = None, result_dir = None):
    simulator = Simulator()
    grp = GroupManager(4, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []
    for x, nodeId in enumerate(network.nodes()):
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        startsAt = np.random.randint(vi.duration/2)
        env = envCls(vi = vi, traces = trace, simulator = simulator, grp=grp, peerId=nodeId, abr=abr, resultpath = result_dir)
        simulator.runAt(startsAt, env.start, 5)
        ags.append(env)
    simulator.run()
    for i,a in enumerate(ags):
        assert a._vFinished # or a._vDead
    return ags

def main(videofile, randstatefp, result_dir, subjects = None):
#     randstate.storeCurrentState() #comment this line to use same state as before
    randstate.loadCurrentState(randstatefp)
    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    vi = video.loadVideoTime("./videofilesizes/sizes_qBVThFwdYTc.py")
    vi = video.loadVideoTime("./videofilesizes/sizes_penseive.py")
    vi = video.loadVideoTime(videofile)
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()

    testCB = {}
    testCB["BOLA"] = (SimpleEnvironment, traces, vi, network, BOLA, result_dir)
    testCB["FastMPC"] = (SimpleEnvironment, traces, vi, network, AbrFastMPC, result_dir)
    testCB["RobustMPC"] = (SimpleEnvironment, traces, vi, network, AbrRobustMPC, result_dir)
    testCB["Penseiv"] = (SimpleEnvironment, traces, vi, network, AbrPensieve, result_dir)
    testCB["GroupP2PBasic"] = (GroupP2PEnvBasic, traces, vi, network, None, result_dir)
    testCB["GroupP2PTimeout"] = (GroupP2PEnvTimeout, traces, vi, network, None, result_dir)

    results = {}

    for name, cb in testCB.items():
        if subjects and name not in subjects:
            continue
        randstate.loadCurrentState(randstatefp)
        ags = runExperiments(*cb)
        results[name] = ags

    plotAgentsData(results, "_vAgent.QoE", "QoE", "Player Id", result_dir)
    plotAgentsData(results, "_vAgent.avgBitrate", "Average bitrate played", "Player Id", result_dir)
    plotAgentsData(results, "_vAgent.avgQualityIndex", "Average quality index played", "Player Id", result_dir)
    plotAgentsData(results, "_vAgent.avgQualityIndexVariation", "Average quality index variation", "Player Id", result_dir)
    plotAgentsData(results, "_vAgent.totalStallTime", "Stall Time", "Player Id", result_dir)
    plotAgentsData(results, "_vAgent.startUpDelay", "Start up delay", "Player Id", result_dir)
    plotAgentsData(results, "idleTime", "IdleTime", "Player Id", result_dir)
    plotAgentsData(results, "totalWorkingTime", "workingTime", "Player Id", result_dir)

    saveRawResults(results, result_dir)


if __name__ == "__main__":
    resNum = "test"
    vidFile = "./videofilesizes/sizes_penseive.py"
    testcase = "tcrand"
    subjects = "BOLA,FastMPC,RobustMPC,Penseiv,GroupP2PBasic,GroupP2PTimeout"

    if len(sys.argv) > 1:
        vidFile = sys.argv[1]
    if len(sys.argv) > 2:
        resNum = sys.argv[2]
    if len(sys.argv) > 3:
        testcase = sys.argv[3]
    if len(sys.argv) > 4:
        subjects = sys.argv[4]

    subjects = subjects.split(",")

    tc = testcase
#     for tc in ["tc1", "tc2", "tc3"]:
    result_dir = os.path.join(RESULT_DIR, resNum, tc)
    if not os.path.isdir(result_dir):
        os.makedirs(result_dir)

    randstatefp = os.path.join(result_dir, "randstate")
    if not os.path.isfile(randstatefp):
        randstate.storeCurrentState(randstatefp) #comment this line to use same state as before

    main(vidFile, randstatefp, result_dir, subjects)
