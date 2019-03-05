'''envRLS - Rapid Live Streaming Environment

'''
from p2pnetwork import P2PRandomNetwork
from envSimpleP2P import P2PGroup
from envSimple import SimpleEnvironment
from simulator import Simulator

import numpy as np
import load_trace
import videoInfo as video

SUPERPEER_ID = 0

'''
Rapid Livestreaming environment.
This environment takes care of agents connected according to our topology
and manages the data download
'''

'''
This is the environment for a single agent. The actual agent delegates responsibility of downloading the chunk to the single agent environment.
Code mostly copied from envSimple.SingleEnvironment
'''
class SingleAgentEnv():
    def __init__(self, vi, traces, simulator, nodeId, abr=None):
        # the catch here is that the traces we have is a map of neighbor node link to the cooked trace
        self.cookedTime, self.cookedBW, self.traceFile = {}, {}, {}
        self.lastBandwidthPtr = {}

        for node in traces:
            self.cookedTime[node], self.cookedBW, self.traceFile = traces[node]
            self.lastBandwidthPtr[node] =  int(np.random.uniform(1, len(self._vCookedTime[node])))

       # the agent that the environment takes care of
        self.agent = agent
        
        self.simulator = simulator
        self.isDead = False
        self.videoInfo = vi
        self.hasFinished = False
        self.nodeId = nodeId
        
        # neighbors
        self.peers = traces.keys()

        # check if it is a super peer neighbor i.e neighbor of peer id 0
        self.isSuperPeerNeighbor = SUPERPEER_ID in self.peers
        
        # metadata related to downloaded times
        self.lastDownloadedAt = 0
        self.idleTimes = []
        self.totalIdleTime = 0
        self.totalWorkingTime = 0

        # the downloaded chunks so far
        # mapping from segid->quality->data
        self.collectedChunks = {}
        # if it is the super peer, all the chunks of all qualities are present
        if nodeId == SUPERPEER_ID:
            init_superpeer()
    
    '''Performs initialization required for a super peer
    Invoked only when nodeId = SUPERPEER_ID
    '''
    def init_superpeer():
        for quality in range(len(self.videoInfo.fileSizes)):
            self.collectedChunks[quality] = {}
            for segid in range(len(self.videoInfo.fileSizes[quality])):
                if segid == len(self.videoInfo.fileSizes[quality])-1:
                    # the last segment might not have duration as vi.segmentDuration
                    duration = self.videoInfo.duration - segid*self.videoInfo.segmentDuration
                else:
                    duration = self.videoInfo.segmentDuration
                self.collectedChunks[quality][segid] = SegmentRequest(quality, 0, 0, duration, segId, self.videoInfo.fileSizes[quality][segid], self)

    def getNow(self):
        return self.simulator.getNow()

    def finishedAfter(self, after   ):
        self.simulator.runAfter(after, self.finish)

    def runAfter(self, after, *kw, **kws):
        return self.simulator.runAfter(after, *kw, **kws)

    def finish(self):
        print("Peer %s has finished playback\n" % self.nodeId)
        self.agent._rFinish()
        self.hasFinished = True

    def start(self, startedAt=-1):
        if not self.agent:
            raise Exception("Node agent to start")
        self.lastDownloadedAt = self.getNow()
        self.agent.start(startedAt)


    '''
    Takes care of choosing which peer to download from.
    Possible actions:
    1. Choose from the neighbors of the node
    2. Choose from the super peer
    3. Stall for now. (TODO: add support)
    '''
    def getPeerToFetchFrom(self, segId):
        # TODO: Plug in the ABR

        '''for now, uses the below GREEDY strategy
        1. Check all the neighbors to see which has the segment ID
        2. Among all those that have it, use the one with best throughput at the moment
        3. if none have it, use the super peer.
        '''
        candidates = []
        for neighbor in self.peers:
            if segId in neighbor.collectedChunks:
               candidates.append(neighbor)
        
        if len(candidates) == 0:
            # fetch from superpeer
            return SUPERPEER_ID
        
        for node in candidates:
            # CONTINUE HERE NEXT
            # TODO: get the best candidate   
            pass


    '''
    This is the entry point which the agent calls for downloading the data
    '''
    def _rDownloadNextData(self, nextSegId, nextQuality, sleepTime):
        if self.isDead: return
        
        # TODO: The ABR policy is delegated to the agent at present. We must add logic to handle P2P fetching
        
        neighborToFetchFrom = self.getPeerToFetchFrom()
        self._rFetchSegment(nextSegId, nextQuality, sleepTime)

 

def setupEnv(traces, vi, network, abr=None):
   simulator = Simulator()
   agents = []
   trace_map = {}

   # allocate different traces for each link in the network
   for x, nodeId in enumerate(network.nodes()):
        link_traces = {}
        for neighbor in network.grp.neighbors(nodeId):
           edge = (min(neighbor, nodeId), max(neighbor, nodeId))
           if edge not in trace_map:
               idx = np.random.randint(len(traces))
               link_traces[neighbor] = traces[idx]
               trace_map[edge] = traces[idx]
           else:
               link_traces[neighbor] = trace_map[edge]
       # TODO: make an environment
   

def main():
    network = P2PRandomNetwork(6)
    # By default, we assume super peer to be node id 0

    traces = load_trace.load_trace()
    vi = video.loadVideoTime("./videofilesizes/sizes_0b4SVyP0IqI.py")
    assert len(traces[0]) == len(traces[1]) == len(traces[2])
    traces = list(zip(*traces))
    setupEnv(traces, vi, network)

if __name__ == '__main__':
    main()
