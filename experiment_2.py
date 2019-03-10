
import load_trace
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

def runExperiments(envCls, traces, vi, network, abr = None):
    simulator = Simulator()
    grp = GroupManager(4, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []
    for x, nodeId in enumerate(network.nodes()):
        idx = np.random.randint(len(traces))
        trace = traces[idx]
        startsAt = np.random.randint(vi.duration/2)
        env = envCls(vi = vi, traces = trace, simulator = simulator, grp=grp, peerId=nodeId, abr=abr)
        simulator.runAt(startsAt, env.start, 5)
        ags.append(env)
    simulator.run()
    for i,a in enumerate(ags):
        assert a._vFinished # or a._vDead
    return ags

def main():
#     randstate.storeCurrentState() #comment this line to use same state as before
    randstate.loadCurrentState()
    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    vi = video.loadVideoTime("./videofilesizes/sizes_qBVThFwdYTc.py")
    vi = video.loadVideoTime("./videofilesizes/sizes_penseive.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()

    testCB = {}
    testCB["BOLA"] = (SimpleEnvironment, traces, vi, network, BOLA)
    testCB["FastMPC"] = (SimpleEnvironment, traces, vi, network, AbrFastMPC)
    testCB["RobustMPC"] = (SimpleEnvironment, traces, vi, network, AbrRobustMPC)
    testCB["Penseiv"] = (SimpleEnvironment, traces, vi, network, AbrPensieve)
    testCB["GroupP2PBasic"] = (GroupP2PEnvBasic, traces, vi, network)
    testCB["GroupP2PTimeout"] = (GroupP2PEnvTimeout, traces, vi, network)

    results = {}

    for name, cb in testCB.items():
        randstate.loadCurrentState()
        ags = runExperiments(*cb)
        results[name] = ags

if __name__ = "__main__":
    
