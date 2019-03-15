'''envRLS - Rapid Live Streaming Environment

'''
from p2pnetwork import P2PRandomNetwork
from envSimpleP2P import P2PGroup
from envSimple import SimpleEnvironment
from simulator import Simulator
from agent import Agent
from segmentRequest import SegmentRequest
from bisect import bisect_left

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
        
        # this is the bandwidth pointer which points to a random timestep in the trace which is assumed to be the starting point for our node's bandwidth 
        self.startBandwidthPtr = {}

        # the time when the agent started
        self.start_time = None
        
        for node in traces:
            self.cookedTime[node], self.cookedBW[node], self.traceFile[node] = traces[node]
            self.startBandwidthPtr[node] =  int(np.random.uniform(1, len(self.cookedTime[node])))

       # the agent that the environment takes care of
        self.agent = Agent(vi, self, abr)
        
        self.simulator = simulator
        self.isDead = False
        self.videoInfo = vi
        self.hasFinished = False
        self.nodeId = nodeId
        
        # neighbors
        self.peers = traces.keys()
        self.neighbor_envs = {}

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
            self.init_superpeer()
    

    '''Returns duration of a particular segment ad quality
    '''
    def getDuration(self, segid, quality):
        if segid == len(self.videoInfo.fileSizes[quality])-1:
            # the last segment might not have duration as vi.segmentDuration
            duration = self.videoInfo.duration - segid*self.videoInfo.segmentDuration
        else:
            duration = self.videoInfo.segmentDuration
        return duration    


    '''Performs initialization required for a super peer
    Invoked only when nodeId = SUPERPEER_ID
    '''
    def init_superpeer(self):
        print("Init superpeer")
        for quality in range(len(self.videoInfo.fileSizes)):
            for segid in range(len(self.videoInfo.fileSizes[quality])):
                duration = self.getDuration(segid, quality) 
                if segid not in self.collectedChunks:
                    self.collectedChunks[segid] = {}
                self.collectedChunks[segid][quality] = SegmentRequest(quality, 0, 0, duration, segid, self.videoInfo.fileSizes[quality][segid], self)

    
    def setNeighbors(self, neighbor_envs):
        # neighbor_envs is a mapping between the neighbor id to the corresponding env object
        self.neighbor_envs = neighbor_envs
   
    
    '''Get the data corresponding to the quality/segId requested
    '''
    def getData(self, segid, quality):     
        assert segid in self.collectedChunks
        # there is atleast one quality present for the requested segid
        assert len(self.collectedChunks[segid]) > 0
        if quality in self.collectedChunks[segid]:
            return self.collectedChunks[segid][quality]
        else:
            # TODO: make sure this branch is not called by inserting appropriate logic in fetchSegment
            print("Node %s: Requested quality %s for segid %s not available" % (self.nodeId, str(quality), str(segid)))
            for quality in self.collectedChunks[segid]:
                return self.collectedChunks[segid][quality]
        

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


    '''
    Get the corresponding timestep in the trace data to the current time in the simulator
    '''   
    def getTraceTimestep(self, neighbor):
        now = self.simulator.getNow()
        assert self.start_time != None
        time_elapsed = now - self.start_time

        cooked_time = self.cookedTime[neighbor]
        i = self.startBandwidthPtr[neighbor]
        trace_start_time = cooked_time[i-1]

        total_trace_time = cooked_time[-1]
        # as we will loop the trace after 'total_trace_time' period, take modulo 
        time_elapsed = time_elapsed % total_trace_time
        
        # corresponding time to simulator.getNow() in the trace dataset
        trace_timestep = (trace_start_time + time_elapsed) % total_trace_time
        return trace_timestep 


    '''
    Get the present pointer to the trace dataset according to the current time in the simulator
    '''
    def getTracePointer(self, neighbor):
        trace_timestep = self.getTraceTimestep(neighbor)
        print("Trace timestep: %s, Trace file: %s" % (str(trace_timestep), str(self.traceFile[neighbor]))) 
        cooked_time = self.cookedTime[neighbor]
        i = bisect_left(cooked_time, trace_timestep)
        print("Detected bw is %s" % str(self.cookedBW[neighbor][i]))
        return i


    '''
    Gets the bandwidth of the link between the node and the given neighbor
    '''
    def getBandwidth(self, neighbor):
        print("Trace file: %s" % self.traceFile[neighbor])
        i = self.getTracePointer(neighbor)
        return self.cookedBW[neighbor][i]


    def start(self, startedAt=-1):
        if not self.agent:
            raise Exception("Node agent to start")
        self.lastDownloadedAt = self.getNow()
        print("Agent starting: "+ str(self.nodeId))
        self.start_time = self.simulator.getNow()
        # the super peer doesn't need to download
        if self.nodeId != SUPERPEER_ID: 
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
        
        candidates = np.array([])
        print("Node %d:" % self.nodeId)
        for neighbor in self.peers:
            if segId in self.neighbor_envs[neighbor].collectedChunks:
               np.append(candidates, neighbor)
        
        if len(candidates) == 0:
            # fetch from superpeer
            return SUPERPEER_ID
       
        # the bandwidth changes cannot be predicted by the node throughout time, so it takes into consideration the present bandwidth of the link and calculates throughput accordingly

        # TODO: POSSIBLE HEURISTICS:
        # 1. Best bandwidth [x]
        # 2, Best available quality of segment [ ]
        # 3. Greedy QoE optimization [ ]
        return candidates[np.argmax([self.getBandwidth(n) for n in candidates])]


    '''Compute the time taken to fetch a particular segment from neighbor
    '''
    def timeTaken(self, neighbor, data):
        duration = data._segmentDuration
        chunk_len = data._clen
        # start point in the trace data
        start_trace_timestep = self.getTraceTimestep(neighbor)
        i = self.getTracePointer(neighbor)
        
        sent_size = 0.0  # the amount of data sent
        time = 0.0
        while True:
            throughput = self.cookedBW[neighbor][i]
            if i == 0:
                # increment it as we need to use from 1 to len(trace)-1
                i += 1

            trace_dur = self.cookedTime[neighbor][i]-self.cookedTime[neighbor][i-1]
            # 0.95 accounts for TCP overhead and loss
            packet_payload = throughput * (1024 * 1024 / 8) * trace_dur * 0.95
            # if we near the end of the segment/chunk, we need to compute only the fraction of the duration taken
            if sent_size + packet_payload >= chunk_len:
                frac_time = trace_dur * (chunk_len-sent_size) / packet_payload
                time += frac_time
                break
            time += trace_dur
            sent_size += packet_payload
            i += 1
            i = i % len(self.cookedBW[neighbor])

        time += 0.08 #delay
        time *= np.random.uniform(0.9, 1.1)
        print("Time taken = %s"% str(time))
        return time


    '''Fetches the segment nextSegId from neighbor
    Right now,the quality param as the neighbor would have only one quality of the segment
    '''
    def fetchSegment(self, neighbor, nextSegId, nextQuality):
        timeneeded = 0.0
        if neighbor == SUPERPEER_ID:
            # the super peer is used to receive the segment
            print("Node %d : Fetching from superpeer %s %s" % (self.nodeId, str(nextSegId), str(nextQuality)))
            data = self.neighbor_envs[neighbor].getData(nextSegId, nextQuality)
        else:
            print("Node %d : Fetching from peer %d %s %s" % (self.nodeId, neighbor, str(nextSegId), str(nextQuality)))
            data = self.neighbor_envs[neighbor].getData(nextSegId, nextQuality)
        
        #segment_duration = 
        # TODO: add RTT to timeneeded
        time_taken= self.timeTaken(neighbor, data)    
        timeneeded += time_taken
        chsize = self.videoInfo.fileSizes[nextQuality][nextSegId]
        now = self.simulator.getNow()
        segment_duration = self.getDuration(nextSegId, nextQuality) 

        self.simulator.runAfter(timeneeded, self.postFetchSegment, nextQuality, now, segment_duration, nextSegId, chsize)

    
    '''Event to perform post fetching essentials like adding to the playback buffer'''
    def postFetchSegment(self, quality, start_time, segment_duration, segid, chsize):
        now = self.simulator.getNow()
        req = SegmentRequest(quality, start_time, now, segment_duration, segid, chsize, self)
        self.addToBuffer(req)

    
    '''Add to agent's playback buffer'''
    def addToBuffer(self, req):
        if self.isDead:
            return
        self.agent._rAddToBufferInternal(req)


    '''
    This is the entry point which the agent calls for downloading the data
    '''
    def _rDownloadNextData(self, nextSegId, nextQuality, sleepTime):
        if self.isDead:
           return
        assert sleepTime >= 0
        assert nextSegId < self.videoInfo.segmentCount

       # TODO: The ABR policy is delegated to the agent at present. We must add logic to handle P2P fetching
        neighborToFetchFrom = self.getPeerToFetchFrom(nextSegId)
        print(neighborToFetchFrom)
        
        self.simulator.runAfter(sleepTime, self.fetchSegment, neighborToFetchFrom, nextSegId, nextQuality)


def setupEnv(traces, vi, network, abr=None):
    simulator = Simulator()
    agents = []
    trace_map = {}
    envs = {}

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
        
        # allot a trace to the super peer link if not present in immediate neighors
        if SUPERPEER_ID not in network.grp.neighbors(nodeId):
            idx = np.random.randint(len(traces))
            link_traces[SUPERPEER_ID] = traces[idx]

        env = SingleAgentEnv(vi, link_traces, simulator, nodeId)
        envs[nodeId] = env
        print("Starting node %d" % nodeId)

    for x, nodeId in enumerate(network.nodes()):
        neighbors = network.grp.neighbors(nodeId) 

        neighbor_envs = {neighbor: envs[neighbor] for neighbor in neighbors}
        if nodeId != SUPERPEER_ID and SUPERPEER_ID not in neighbor_envs:
            neighbor_envs[SUPERPEER_ID] = envs[SUPERPEER_ID]
        envs[nodeId].setNeighbors(neighbor_envs)
        simulator.runAt(101.0 + x, envs[nodeId].start, 5)
    simulator.run()


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
