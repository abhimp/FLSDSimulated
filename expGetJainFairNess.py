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
from envGroupP2PRNNTest import GroupP2PEnvRNN

# from envGroupP2PTimeoutRNNTest import GroupP2PEnvTimeoutRNN
# from abrPensiev import AbrPensieve
# from envGroupP2PTimeoutIncRNN import GroupP2PEnvTimeoutIncRNN
GroupP2PEnvTimeoutRNN = None
GroupP2PEnvTimeoutIncRNN = None
AbrPensieve = None


RESULT_DIR = "./results/GenPlots"
BUFFER_LEN_PLOTS = "results/bufferlens"
STALLTIME_IDLETIME_PLOTS = "results/stall-idle"

VIDEO_FILES = [
    "./videofilesizes/sizes_zC1ePnMTRPY.py",
    "./videofilesizes/sizes_7HEKMRfM0vw.py",
    "./videofilesizes/sizes_mUc_aJYlCfk.py",
    "./videofilesizes/sizes_zq7iftN3in4.py",
    "./videofilesizes/sizes_iX1JY2qWq2w.py",
    "./videofilesizes/sizes_CidvwfIorPE.py",
    "./videofilesizes/sizes_cCGuvUPSYU4.py",
    "./videofilesizes/sizes_0yRnOU7s8UE.py",
    "./videofilesizes/sizes_b6P4R3y3hH0.py",
    "./videofilesizes/sizes_cn8YjC7s7B8.py",
    "./videofilesizes/sizes_DCYzcX6xzBc.py",
    "./videofilesizes/sizes_M6hRtv_x7gc.py",
    "./videofilesizes/sizes_J_JdgAFcDF0.py",
    "./videofilesizes/sizes_yv25Kx0dKBU.py",
    "./videofilesizes/sizes_L_aySa3BvdA.py",
    "./videofilesizes/sizes_kjRAWql2A3E.py",
    "./videofilesizes/sizes_G-qd6YFFbc4.py",
    "./videofilesizes/sizes_xRpLGifRHnI.py",
    "./videofilesizes/sizes_LMWw-X6t8Wc.py",
    "./videofilesizes/sizes_DwgGXGTtObc.py",
    "./videofilesizes/sizes_prNYOW0_kms.py",
    "./videofilesizes/sizes_qBVThFwdYTc.py",
    "./videofilesizes/sizes_79g40dq3M9w.py",
    "./videofilesizes/sizes_H0f7poWe8RI.py",
    "./videofilesizes/sizes_0oly6d0zlZM.py",
    "./videofilesizes/sizes_n6paI7fs5VM.py",
    "./videofilesizes/sizes_cyMnKoAdbYI.py",
    "./videofilesizes/sizes_T2vPDGzxq7o.py",
    "./videofilesizes/sizes__GcDktjpp1w.py",
    "./videofilesizes/sizes_hF8OoWadK4Q.py",
    "./videofilesizes/sizes_b80ShWk_Aro.py",
    "./videofilesizes/sizes_6jIIONaP0p4.py",
    "./videofilesizes/sizes_7CgTlg_L_Sw.py",
    "./videofilesizes/sizes_gtPIfchgItw.py",
    "./videofilesizes/sizes_1s6zy8SB3Is.py",
    "./videofilesizes/sizes_IDXTmCwAETM.py",
    "./videofilesizes/sizes_ZyBsy5SQxqU.py",
    "./videofilesizes/sizes_mRNWC0piPrQ.py",
    "./videofilesizes/sizes_Al53BulB0H0.py",
    "./videofilesizes/sizes_0b4SVyP0IqI.py",
    "./videofilesizes/sizes_szdW22mqNBQ.py",
    "./videofilesizes/sizes_O_sTdr-Aky0.py",
    "./videofilesizes/sizes_oBLXbrD8Jek.py",
    "./videofilesizes/sizes_ptWmIvm7UNk.py",
    "./videofilesizes/sizes_llxRaBrZ45s.py",
    "./videofilesizes/sizes_bSd2P0guPFk.py",
    "./videofilesizes/sizes_Yo4oP2eyDtI.py",
    "./videofilesizes/sizes_Q8vK7_B2WZ0.py",
    "./videofilesizes/sizes_u3rl8NB8xIc.py",
    "./videofilesizes/sizes_XOst4cXEXko.py",
    "./videofilesizes/sizes_PqC9g7tkrEc.py",
    "./videofilesizes/sizes_oO4xDieHKe4.py",
    "./videofilesizes/sizes_8de4XDnJUKk.py",
    "./videofilesizes/sizes__YAEitUAAZs.py",
    "./videofilesizes/sizes_tQhqs1iFHDQ.py",
    "./videofilesizes/sizes_b6TIMTvY8hM.py",
    "./videofilesizes/sizes_qpdU1t2xyok.py"
]

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
    return grp

def main():
    global GroupP2PEnvTimeoutRNN, AbrPensieve, GroupP2PEnvTimeoutIncRNN
    allowed = ["GroupP2PTimeoutInc", "GroupP2PEnvTimeoutIncRNN", "GroupP2PEnvRNN"] 
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
    testCB["GroupP2PEnvRNN"] = (GroupP2PEnvRNN, traces, vi, network, BOLA, None, "./ResModelPathRNN/")

    results = {}
    cdns = {}

#     for name, cb in testCB.items():
    for name in allowed:
        fis = []
        QoEVar = []
        for vfp in VIDEO_FILES:
            vi = video.loadVideoTime(vfp)
            assert name in testCB
            cb = testCB[name]
            randstate.loadCurrentState()
            grp = runExperiments(*cb)
            gp, igp = grp.getGroupFairness(), grp.getInterGroupFairness()
            QoEVar += grp.getQoEVariation()
            fis.append((gp, igp))

        fpath = os.path.join(RESULT_DIR, "fairness")
        if not os.path.isdir(fpath):
            os.makedirs(fpath)
        fpath = os.path.join(fpath, name+".dat")
        with open(fpath, "w") as fp:
            print("#gp igp", file=fp)
            for x in fis:
                print(*x, file=fp)

        fpath = os.path.join(RESULT_DIR, "QoEVarInGroup")
        if not os.path.isdir(fpath):
            os.makedirs(fpath)
        fpath = os.path.join(fpath, name+".dat")
        with open(fpath, "w") as fp:
            print("#", file=fp)
            for x in QoEVar:
                print(x, file=fp)




if __name__ == "__main__":
#     for x in range(20):
        main()
#     main2()
