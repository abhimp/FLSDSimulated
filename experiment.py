import load_trace
import videoInfo as video
from p2pnetwork import P2PNetwork
import randStateInit as randstate

from envGroupP2P import experimentGroupP2P
from envSimple import experimentSimpleEnv
from envSimpleP2P import experimentSimpleP2P

def main():
#     randstate.storeCurrentState() #comment this line to use same state as before
    randstate.loadCurrentState()
    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    network = P2PNetwork()

    experimentGroupP2P(traces, vi, network)
    experimentSimpleEnv(traces, vi, network)
    experimentSimpleP2P(traces, vi, network)


if __name__ == "__main__":
    main()
