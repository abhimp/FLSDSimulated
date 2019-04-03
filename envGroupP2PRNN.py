import os
from myprint import myprint
import math
import json
import matplotlib.pyplot as plt
import numpy as np
import glob

from envSimple import SimpleEnvironment, np, Simulator, load_trace, video, P2PNetwork
from group import GroupManager
import randStateInit as randstate
from easyPlotViewer import EasyPlot
from calculateMetric import measureQoE
# from rnnTimeout import getPensiveLearner, saveLearner
import rnnAgent
import rnnQuality


GROUP_JOIN_THRESHOLD = 10
BYTES_IN_MB = 1000000

LOG_LOCATION = "./results/"

class GroupP2PEnvRNN(SimpleEnvironment):
    def __init__(self, vi, traces, simulator, abr = None, grp = None, peerId = None, modelPath=None, *kw, **kws):
        super().__init__(vi, traces, simulator, abr, peerId, *kw, **kws)
#         self._vAgent = Agent(vi, self, abr)
        self._vDownloadPending = False
        self._vDownloadPendingRnnkey = None
        self._vSegIdRNNKeyMap = {}
        self._vSegmentDownloading = -1
        self._vGroup = grp
        self._vCatched = {}
        self._vOtherPeerRequest = {}
        self._vTotalDownloaded = 0
        self._vTotalUploaded = 0
        self._vStarted = False
        self._vFinished = False
        self._vModelPath = modelPath

        self._vGroupNodes = None
        self._vQueue = []

        self._vGroupSegDetails = []

        self._vEarlyDownloaded = 0
        self._vNormalDownloaded = 0
        self._vThroughPutData = []
        self._vDownloadQueue = []
        self._vServingPeers = {}
        self._vDownloadedReqByItSelf = []
        self._vTimeoutDataAndDecision = {} # segId -> data
        self._vPlayBackDlCnt = 0
        self._vPlayerIdInGrp = -1
        self._vGroupStartedFromSegId = -1
        self._vImStarter = False
        self._vGroupStarted = False
        self._vNextGroupDownloader = -1
        self._vNextGroupDLSegId = -1
        self._vPensieveAgentLearner = None if not self._vModelPath  else rnnAgent.getPensiveLearner(list(range(5)), summary_dir = self._vModelPath)
        self._vPensieveQualityLearner = None if not self._vModelPath  else rnnQuality.getPensiveLearner(list(range(len(self._vVideoInfo.bitrates))), summary_dir = self._vModelPath)

#=============================================
    def start(self, startedAt = -1):
        super().start(startedAt)
        self._vAgent.addStartupCB(self.playerStartedCB)

#=============================================
    def playerStartedCB(self, *kw, **kwa):
        self._vStarted = True

#=============================================
    def die(self):
        self._vDead = True
        self._vGroup.remove(self, self._vAgent.nextSegmentIndex)

#=============================================
    def schedulesChanged(self, changedFrom, nodes, sched):
#         self._vGroupNodes = nodes
        newNodes = [x for x in nodes if x._vPlayerIdInGrp == -1]
        assert len(newNodes) == 1 #anything else is a disaster
        if newNodes[0] == self:
            self._vPlayerIdInGrp = len(nodes) - 1
        if newNodes[0] != self:
            if len(nodes) == 2:
                self.requestRpc(newNodes[0]._rGroupStarted)
        self._vGroupNodes = nodes
        syncTime = self.now + 1
        self._vSimulator.runAt(syncTime, self._vAgent._rSyncNow) 




#=============================================
    def _rGroupStarted(self):
        assert len(set([x._vPlayerIdInGrp for x in self._vGroupNodes])) == len(self._vGroupNodes)
        if len(self._vGroupNodes) == 2 and not self._vGroupStarted:
            self._vGroupStarted = self._vImStarter = True

#=============================================
    def _rGetRtt(self, node):
        return self._vGroup.getRtt(self, node)

#=============================================
    def _rTransmissionTime(self, *kw):
        return self._vGroup.transmissionTime(self, *kw)

#=============================================
    def requestRpc(self, func, *argv, **kargv):
        node = func.__self__
        assert node != self
        delay = self._rGetRtt(node) 
        self.runAfter(delay, node.recvRPC, func, self, *argv, **kargv)

#=============================================
    def requestLongRpc(self, func, clen, *argv, **kargv):
        node = func.__self__
        assert node != self
        delay = self._rTransmissionTime(node, clen)
        self.runAfter(delay, node.recvRPC, func, self, *argv, **kargv)

#=============================================
    def recvRPC(self, func, node, *argv, **kargv):
        s = func.__self__
        assert s == self and node.__class__ == self.__class__
        func(*argv, **kargv)

    def gossipSend(self, func, *argv, **kargv):
        strfunc = func.__name__
        for node in self._vGroupNodes:
            if node == self:
                continue
            self.requestRpc(node.gossipRcv, strfunc, *argv, **kargv)

    def gossipRcv(self, strfunc, *argv, **kargv):
        func = self.__getattribute__(strfunc)
        func(*argv, **kargv)

#=============================================
    def _rGetMyQuality(self, nextQl, segId, rnnkey):
        _, lastPlayerId, lastQl = list(zip(*([(0,0,0), (0,0,0)] + self._vGroupSegDetails[-5:])))

        lastPlayerId = [0]*5 + list(lastPlayerId)
        lastQl = [0]*5 + list(lastQl)
        
        lastClens = [0]*5 + [r.clen for r in self._vDownloadedReqByItSelf[-5:]]
        lastStartsAt = [0]*5 + [r.downloadStarted for r in self._vDownloadedReqByItSelf[-5:]]
        lastFinishAt = [0]*5 + [r.downloadFinished for r in self._vDownloadedReqByItSelf[-5:]]
        pendings = [0]*5 + [len(n._vDownloadQueue) for n in self._vGroupNodes]

        deadline = self._vAgent._vGlobalStartedAt + segId*self._vVideoInfo.segmentDuration - self.now
        
        state = (lastPlayerId[-5:], lastQl[-5:], lastClens[-5:], lastStartsAt[-5:], lastFinishAt[-5:], pendings[-5:], deadline)
        
        self._vSegIdRNNKeyMap[segId] = rnnkey

        ql = self._vPensieveQualityLearner.getNextAction(rnnkey, state)
        return ql
        
        if nextQl > -1:
            return nextQl
        return 0

#=============================================
    def _rGetNextDownloader(self, segId):
        globalPlaybackTime = self.now - self._vAgent._vGlobalStartedAt
        pendings = [0] * 5
        pendings += [len(n._vDownloadQueue) for n in self._vGroupNodes]

        curbufs = [0]*5 + [n._vAgent.bufferLeft for n in self._vGroupNodes]
        pbdelay = [0]*5 + [n._vAgent.playbackTime - globalPlaybackTime for n in self._vGroupNodes]
        uploaded = [n._vTotalUploaded for n in self._vGroupNodes]
        uploaded = [0] *5 + [x for x in (np.array(uploaded) - np.mean(uploaded))/BYTES_IN_MB]
        lastDlAt = [n._vWorkingTimes[-1][0] for n in self._vGroupNodes]
        lastDlAt = [0]*5 + [x for x in np.array(lastDlAt) - self.now]
        estThrput = [0]*5 + [n._rPredictedThroughput()/1000000 for n in self._vGroupNodes]
        deadline = self._vAgent._vGlobalStartedAt + segId*self._vVideoInfo.segmentDuration - self.now

        players = [0]*5 + [n._vPlayerIdInGrp for n in self._vGroupNodes]

        rnnkey = (self.networkId, segId)

        state = (pendings[-5:], curbufs[-5:], pbdelay[-5:], uploaded[-5:], lastDlAt[-5:], players[-5:], estThrput[-5:], deadline)
    
        nextPlayer = self._vPensieveAgentLearner.getNextAction(rnnkey, state)
        #print(rnnkey, state)
        
        penalty = 0
        if nextPlayer >= len(self._vGroupNodes):
            penalty = 1000
            nextPlayer = np.random.randint(len(self._vGroupNodes))

    
        return nextPlayer, (rnnkey, penalty)

#=============================================
    def _rSetNextDownloader(self, playerId, segId, rnnkey, lastPlayerId, lastQl):
        if not self._vGroupStarted:
            self._vGroupStarted = True
            self._vGroupStartedFromSegId = segId 
        self._vNextGroupDownloader = playerId
        self._vNextGroupDLSegId = segId
        self._vGroupSegDetails.append((segId - 1, lastPlayerId, lastQl))
        if playerId != self._vPlayerIdInGrp:
            return #ignore the msg
        if segId >= self._vVideoInfo.segmentCount: #endof video
            return
        waitTime = self._vAgent._rIsAvailable(segId) 
        if waitTime > 0:
            self.runAfter(waitTime, self._rSetNextDownloader, playerId, segId, rnnkey, lastPlayerId, lastQl)
            return
        self._rDownloadAsTeamPlayer(segId, rnnkey = rnnkey)

#=============================================
    def _rDownloadAsTeamPlayer(self, segId, rnnkey = None, ql = -1):
        nextDownloader, rnnkey = self._rGetNextDownloader(segId)
        ql = self._rGetMyQuality(ql, segId, rnnkey)
        self.gossipSend(self._rSetNextDownloader, nextDownloader, segId+1, rnnkey, self._vPlayerIdInGrp, ql)
        self._rAddToDownloadQueue(segId, ql, rnnkey=rnnkey)
        self._rSetNextDownloader(nextDownloader, segId + 1, rnnkey, self._vPlayerIdInGrp, ql)

#=============================================
    def _rPredictedThroughput(self):
        #as per rate based algo
        thrpt = [1/x for t, x in self._vThroughPutData[-5:]]
        return len(thrpt)/sum(thrpt)

#=============================================
    def _rAddToDownloadQueue(self, nextSegId, nextQuality, position=float("inf"), sleepTime = 0, rnnkey = None):
        if sleepTime > 0:
            self.runAfter(sleepTime, self._rAddToDownloadQueue, nextSegId, nextQuality)
            return
        position = min(position, len(self._vDownloadQueue))
        self._vDownloadQueue.insert(position, (nextSegId, nextQuality, rnnkey))
        self._rDownloadFromDownloadQueue()

#=============================================
    def _rDownloadFromDownloadQueue(self):
        if self._vDownloadPending:
            return
        while len(self._vDownloadQueue):
            segId, ql, rnnkey = self._vDownloadQueue.pop(0)
            self._rFetchSegment(segId, ql)
            self._vDownloadPending = True
            self._vDownloadPendingRnnkey = rnnkey
            break

#=============================================
    def _rDownloadNextData(self, nextSegId, nextQuality, sleepTime):
        if sleepTime > 0:
            self.runAfter(sleepTime, self._rDownloadNextData, nextSegId, nextQuality, 0)
            return

        if nextSegId in self._vCatched:
            self._rAddToAgentBuffer(self._vCatched[nextSegId])
            return

        if not self._vGroupStarted or self._vGroupStartedFromSegId > nextSegId:
            self._rAddToDownloadQueue(nextSegId, nextQuality, sleepTime=sleepTime)
            return

        if self._vImStarter:
            self._vImStarter = False
            self._vGroupStarted = True
            self._vGroupStartedFromSegId = nextSegId
            self._rDownloadAsTeamPlayer(nextSegId, ql = nextQuality)
            return

#=============================================
    def _rAddToAgentBuffer(self, req, simIds=None):
        if self._vAgent.nextSegmentIndex > req.segId:
            return
        assert self._vAgent.nextSegmentIndex == req.segId
        waitTime = self._vAgent.bufferAvailableIn()
        if waitTime > 0:
            self.runAfter(waitTime, self._rAddToAgentBuffer, req, 0)
            return
        lastStalls = self._vAgent._vTotalStallTime
        self._vAgent._rAddToBufferInternal(req)
        if req.segId in self._vSegIdRNNKeyMap:
            rnnkey = self._vSegIdRNNKeyMap[req.segId]
            del self._vSegIdRNNKeyMap[req.segId]
            qoe = self._vAgent.QoE

            qls = self._vAgent.bitratePlayed[-2:]

            diff = abs(qls[0] - qls[1])/BYTES_IN_MB
            rebuf = self._vAgent._vTotalStallTime - lastStalls
            qoe = qls[1] / BYTES_IN_MB - diff - 4.3 * rebuf
            self._vPensieveQualityLearner.addReward(rnnkey, qoe)
            #add reward

#=============================================
    def _rAddToBuffer(self, req, simIds = None):
        self._vDownloadPending = False
        rnnkey = self._vDownloadPendingRnnkey
        self._rDownloadFromDownloadQueue()
        if self._vStarted:
            self._vPlayBackDlCnt += 1
        self._vThroughPutData += [(self.now, req.throughput)]
        self._vDownloadedReqByItSelf += [req]

        if req.segId not in self._vCatched:
            if self._vAgent.nextSegmentIndex == req.segId:
               self._rAddToAgentBuffer(req, simIds)
            self._vCatched[req.segId] = req

        if self._vPlayBackDlCnt == GROUP_JOIN_THRESHOLD:
            self._vConnectionSpeed = self._rPredictedThroughput()/1000000
            self._vGroup.add(self, self._vAgent.nextSegmentIndex+2)

        if self._vGroupNodes:
            self.gossipSend(self._rRecvReq, self, req)

        if not rnnkey:
            return

        deadline = self._vAgent._vGlobalStartedAt + req.segId * self._vVideoInfo.segmentDuration
        reward = deadline - self.now
        rnnkey, outofbound = rnnkey
        reward -= outofbound
        uploaded = [n._vTotalUploaded for n in self._vGroupNodes]
        contri = abs(self._vTotalUploaded - np.mean(uploaded))/BYTES_IN_MB
        reward -= contri

        #call rnn obj for working 
        self._vPensieveAgentLearner.addReward(rnnkey, reward)


#=============================================
    def _rRecvReq(self, node, req):
        if self._vAgent.nextSegmentIndex == req.segId and req.segId not in self._vCatched:
            self._rAddToAgentBuffer(req, None)
        if req.segId not in self._vCatched:
            node._vTotalUploaded += req.clen
            self._vTotalDownloaded += req.clen #i.e. peer download
        self._vCatched[req.segId] = req

#=============================================
#=============================================
#=============================================
AGENT_TRACE_MAP = {}
def experimentGroupP2PSmall(traces, vi, network):
    simulator = Simulator()
    grp = GroupManager(4, len(vi.bitrates)-1, vi, network)#np.random.randint(len(vi.bitrates)))

    deadAgents = []
    ags = []

    for trx, nodeId, startedAt in [( 5, 267, 107), (36, 701, 111), (35, 1800, 124), (5, 2033, 127)]:
        trace = traces[trx]
        env = GroupP2PEnvRNN(vi, trace, simulator, None, grp, nodeId)
        simulator.runAt(startedAt, env.start, 5)
        AGENT_TRACE_MAP[nodeId] = trx
        ags.append(env)

    simulator.run()
    grp.printGroupBucket()
    for i,a in enumerate(ags):
        assert a._vFinished # or a._vDead
#         logThroughput(a)
#     if __name__ == "__main__":
#         plotIdleStallTIme("results/stall-idle/", grp)
    return ags

def main():
#     randstate.storeCurrentState() #comment this line to use same state as before
    for fpath in glob.glob("videofilesizes/*.py"):
#         randstate.storeCurrentState() #comment this line to use same state as before
        randstate.loadCurrentState()
        traces = load_trace.load_trace()
        vi = video.loadVideoTime("./videofilesizes/sizes_qBVThFwdYTc.py")
        vi = video.loadVideoTime("./videofilesizes/sizes_penseive.py")
        vi = video.loadVideoTime(fpath)
        assert len(traces[0]) == len(traces[1]) == len(traces[2])
        traces = list(zip(*traces))
        network = P2PNetwork("./p2p-Gnutella04.txt")

        experimentGroupP2PSmall(traces, vi, network)
        return

if __name__ == "__main__":
    for x in range(3):
        main()
        print("=========================\n")
        break
