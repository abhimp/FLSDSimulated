import os
import numpy as np
import matplotlib.pyplot as plt
import collections as cl
import sys

import load_trace
import videoInfo as video
from simulator import Simulator
from p2pnetwork import P2PNetwork
import randStateInit as randstate
from envGroupP2PTimeoutInc import GroupP2PEnvTimeoutInc
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
    allowed = ["GroupP2PTimeoutInc", "GroupP2PEnvTimeoutIncRNN"] 
    if "-h" in sys.argv or len(sys.argv) <= 1:
        print(" ".join(allowed))
        return
    allowed = sys.argv[1:]
    if "GroupP2PEnvTimeoutIncRNN" in allowed and GroupP2PEnvTimeoutIncRNN is None:
        from envGroupP2PTimeoutIncRNNTest import GroupP2PEnvTimeoutIncRNN as gpe
        GroupP2PEnvTimeoutIncRNN = gpe

    randstate.loadCurrentState()
    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
#     vi = video.loadVideoTime("./videofilesizes/sizes_qBVThFwdYTc.py")
#     vi = video.loadVideoTime("./videofilesizes/sizes_penseive.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()

    testCB = {}
    testCB["GroupP2PTimeoutInc"] = (GroupP2PEnvTimeoutInc, traces, vi, network)
    testCB["GroupP2PEnvTimeoutIncRNN"] = (GroupP2PEnvTimeoutIncRNN, traces, vi, network, BOLA, None, "ModelPath")

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



if __name__ == "__main__":
#     for x in range(20):
        main()
#     main2()
