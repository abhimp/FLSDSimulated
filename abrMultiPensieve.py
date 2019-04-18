from abrPensiev import *

'''
This class helps using the Pensieve algorithm as fallback for getting the right quality from Super Peer

The main difference from AbrPensieve is that this handles requests intelligently, relevant lastChunk data is taken only from the last time it connected to the Super Peer. 
'''
class AbrMultiPensieve(AbrPensieve):
    
    def getNextDownloadTime(self, *kw, **kws):
        if len(self.agent._vRequests) == 0:
            return 0, 0

        requests = self.agent._vRequests
        print("Downloaded by: ", requests[0].downloader.nodeId, " from ", requests[0].segmentDownloadedFrom)
        superpeer_requests = [request for request in requests if request.segmentDownloadedFrom == 0]
        
        if len(superpeer_requests) == 0:
            # Tricky part now, what if the agent has never contacted the super peer before?
            # Fallback to the default ABR policy
            return self.agent._rWhenToDownload(kw)
        else:
            req = superpeer_requests[-1]
            bufferLeft = self.agent._vBufferUpto - self.agent._vPlaybacktime
            if bufferLeft < 0:
                bufferLeft = 0

            post_data = {
                    'lastquality': self.agent._vLastBitrateIndex,
                    'RebufferTime': self.agent._vTotalStallTime,
                    'lastChunkFinishTime': req.downloadFinished * M_IN_K,
                    'lastChunkStartTime': req.downloadStarted * M_IN_K,
                    'lastChunkSize': req.clen,
                    'buffer': bufferLeft,
                    'lastRequest': self.agent.nextSegmentIndex,

                    'a_dim' : len(self.video.bitratesKbps),
                    'bitrates' : self.video.bitratesKbps,
                    'tot_chunks' : self.video.segmentCount,
                    'bitrate_reward' : self.video.bitrateReward,
                    'video' : self.video,
                    'input' : self.input_dict,
                    }
            return self.getSleepTime(bufferLeft), self.abr.do_POST(post_data)


