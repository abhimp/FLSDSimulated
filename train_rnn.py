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
    videos = VIDEO_FILES[:40] #glob.glob("./videofilesizes/*.py")
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
