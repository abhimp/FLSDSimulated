import os
import sys
import load_trace
import pickle
import numpy as np
import glob
import randStateInit
import pdb
import time
import traceback as tb

import videoInfo as video
from envGroupP2PTimeoutIncRNN import GroupP2PEnvTimeoutIncRNN
from envGroupP2PRNN import GroupP2PEnvRNN
from envSimple import SimpleEnvironment
from simulator import Simulator
from group import GroupManager
from p2pnetwork import P2PNetwork
#from rnnTimeout import saveLearner, setSlaveId, quitCentralServer, runCentralServer, slavecleanup
import rnnAgent, rnnQuality
import util.multiprocwrap as mp
import graphs
import gc
from util.email import sendErrorMail
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

def runExperiments(envCls, traces, vi, network, abr = None, result_dir = None, expId = 0, *kw, **kws):
    randStateInit.loadCurrentState()
    simulator = Simulator()
    grp = GroupManager(4, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []
    for x, nodeId in enumerate(network.nodes()):
        idx = x%len(traces)
        trace = traces[idx]
        startsAt = np.random.randint(vi.duration/2)
        env = envCls(vi = vi, traces = trace, simulator = simulator, grp=grp, peerId=nodeId, abr=abr, resultpath = result_dir, *kw, **kws)
        simulator.runAt(startsAt, env.start, 5)
        ags.append(env)
    simulator.run()
    for i,a in enumerate(ags):
        assert a._vFinished # or a._vDead
    rnnAgent.saveLearner()
    rnnQuality.saveLearner()
    return ags

def movecore(dest, slvId, pid, x):
    if not os.path.isdir(dest):
        os.makedirs(dest)
    count = 10
    while not os.path.isfile("core") and count:
        count -= 1
        time.sleep(1)
    try:
        os.rename("core", os.path.join(dest, "core_%s_%s_%s"%(x, slvId, pid)))
    except:
        print("not core found", file=sys.stderr)
        pass

def runSlave(pq, sq, slvId):
    rnnAgent.setSlaveId(slvId)
    rnnQuality.setSlaveId(slvId)
    while True:
        q = sq.get()
        if q == "quit":
            rnnQuality.slavecleanup()
            rnnAgent.slavecleanup()
            exit(0)
        expId = q[1].get("expId", -1)
        try:
            runExperiments(*q[0], **q[1])
        except:
            trace = sys.exc_info()
            simpTrace = "<br>\n".join(tb.format_tb(trace[2]))
            pq.put({"status":False, "slvId": slvId, "expId": expId, "tb": simpTrace})
            grant = sq.get()
            rnnQuality.slavecleanup()
            rnnAgent.slavecleanup()
            os.abort()
        print(slvId + ": garbageCollection:", gc.collect())
        pq.put({"status":True, "slvId": slvId, "expId": expId})


MULTI_PROC = True
NUM_EXP_PER_SLV = 1

EMAIL_PASS = None

def main():
    global EMAIL_PASS
    if os.path.isfile("emailpass.txt"):
        EMAIL_PASS = open("emailpass.txt").read().strip()

    subjects = "GroupP2PTimeoutRNN"
    modelPath = "ResModelPathRNN"
    numSlave = 2
    slaveIds = ["slv%d"%(x+1) for x in range(numSlave)]
    slvQs = {x:mp.Queue() for x in slaveIds}
    slvExpCnt = {x:0 for x in slaveIds}
    procQueue = mp.Queue()
    slaveProcs = {}

    subjects = subjects.split(",")
    networks = graphs.networks #glob.glob("./graph/*.txt")
    videos = VIDEO_FILES[:35] #glob.glob("./videofilesizes/*.py")
    traces = load_trace.load_trace()
    traces = list(zip(*traces))
    centralLearnerQua = None
    centralLearnerAge = None
    expParams = [(vidPath, netPath, tc) for netPath in networks[:40] for vidPath in videos for tc in ["tc1"]]
    total = len(expParams)

    if MULTI_PROC:
        if not centralLearnerQua and not centralLearnerAge:
            vi = video.loadVideoTime(videos[0])
            centralLearnerQua = rnnQuality.runCentralServer(slaveIds, list(range(len(vi.bitrates))), summary_dir = modelPath)
            centralLearnerAge = rnnAgent.runCentralServer(slaveIds, list(range(5)), summary_dir = modelPath) #assuming max 5 player in a group
        for x in slaveIds:
            p = mp.Process(target=runSlave, args = (procQueue, slvQs[x], x))
            p.start()
            slaveProcs[x] = p

    finished = 0
    started = 0
    with open(RESULT_DIR+"/progress", "w") as fp:
        print("finished: ", finished, "of", total, file=fp)


    for vidPath, netPath, tc in expParams:
        vi = video.loadVideoTime(vidPath)
        p2p = P2PNetwork(netPath)
        if p2p.numNodes() < 10:
            continue

        result_dir = os.path.join(RESULT_DIR, tc)
        if not os.path.isdir(result_dir):
            os.makedirs(result_dir)

        randstatefp = os.path.join(result_dir, "randstate")
        if len(slaveIds) == 0:
            status = procQueue.get()
            slvId = status["slvId"]
            expId = status.get("expId", -1)
            slvExpCnt[slvId] += 1
            if not status["status"]:
                slvQs[slvId].put(True)
                slaveProcs[slvId].join()
                if EMAIL_PASS:
                    sendErrorMail("Slave crashed expId:" + str(expId) + ", slaveIds:" + str(slvId) + "", "it crashed expId:" + str(expId) + ", slaveIds:" + str(slvId) + "<br>\n" + str(status.get("tb", "")), EMAIL_PASS)
                with open("/tmp/testproc", "a") as fp:
                    print("permission to crash for slv", slvId, "pid:", slaveProcs[slvId].pid, "expId:", expId, file=fp)
                    print("permission to crash for slv", slvId, "pid:", slaveProcs[slvId].pid, "expId:", expId)
                movecore("./cores/", slvId, slaveProcs[slvId].pid, expId)
                p = mp.Process(target=runSlave, args = (procQueue, slvQs[slvId], slvId))
                p.start()
                slaveProcs[slvId] = p
                slvExpCnt[slvId] = 0
            if slvExpCnt[slvId] >= NUM_EXP_PER_SLV:
                print("Quting a slv")
                slvQs[slvId].put("quit")
                print("waiting to join")
                slaveProcs[slvId].join()
                print("joined")
                with open("/tmp/testproc", "a") as fp:
                    print("killed one child with id", slvId, "and respwaned", file=fp)
                p = mp.Process(target=runSlave, args = (procQueue, slvQs[slvId], slvId))
                p.start()
                slaveProcs[slvId] = p
                slvExpCnt[slvId] = 0

            slaveIds.append(slvId)

            finished += 1
            print("="*40)
            print("finished: ", finished, "of", total, "expId:", expId)
            print("="*40)
            with open(RESULT_DIR+"/progress", "w") as fp:
                print("finished: ", finished, "of", total, file=fp)
        slvId = slaveIds.pop()

        print("Starting", started, "with", (vidPath, netPath, tc))
        if MULTI_PROC:
            slvQs[slvId].put([(GroupP2PEnvRNN, traces, vi, p2p, None, result_dir), {"modelPath" : modelPath, "expId" :started}])
        else:
#             rnnAgent.setSlaveId(slvId)
#             rnnQuality.setSlaveId(slvId)
            runExperiments(GroupP2PEnvRNN, traces, vi, p2p, None, result_dir, modelPath=modelPath)
            finished += 1

        print("Started", started)
        started += 1
        if finished >= 1:
            break

    while len(slaveIds) < numSlave and MULTI_PROC:
        status = procQueue.get()
        slvId = status["slvId"]
        expId = status.get("expId", -1)
        if not status["status"]:
            slvQs[slvId].put(True)
            slaveProcs[slvId].join()
            with open("/tmp/testproc", "a") as fp:
                print("permission to crash for slv", slvId, "pid:", slaveProcs[slvId].pid, "expId:", expId, file=fp)
            movecore("./cores/", slvId, slaveProcs[slvId].pid, expId)
        else:
            slvQs[slvId].put("quit")
            slaveProcs[slvId].join()
        slaveIds.append(slvId)
        with open(RESULT_DIR+"/progress", "w") as fp:
            print("finished: ", finished, "of", total, file=fp)

    if MULTI_PROC:
        print("Turning off central server")
        rnnAgent.quitCentralServer()
        rnnQuality.quitCentralServer()
        centralLearnerAge.join()
        centralLearnerQua.join()
        print("finished")



if __name__ == "__main__":
    try:
        main()
    except:
        trace = sys.exc_info()
        if EMAIL_PASS:
            trace = sys.exc_info()
            simpTrace = "<br>\n".join(tb.format_tb(trace[2]))
            sendErrorMail("Master crashed", simpTrace, EMAIL_PASS)
        pdb.set_trace()
        os.abort()
