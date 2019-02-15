
class Group():
    def __init__(s, ql, network):
        s.nodes = []
        s.schedules = {}
        s.segMents = 0
        s.nodeAddedWithSegId = {}
        s.qualityLevel = ql
        s.network = None

    def __schedule(s, segId):
        nodeslist = list(s.nodes)
        nodeslist.sort(key=lambda x: - s.nodeAddedWithSegId[x])
        for i, seg in enumerate(range(segId, 1000)):
            x = i % len(nodeslist)
            s.schedules[seg] = nodeslist[x]

        for n in s.nodes:
            n.schedulesChanged(segId)

    def numNodes(s):
        return len(s.nodes)

    def add(s, node, segId = 0):
        if node in s.nodes:
            return
        s.nodes.append(node)
        s.nodeAddedWithSegId[node] = segId
        s.__schedule(segId)

    def remove(s, node, segId = 0):
        if node not in s.nodes:
            return
        s.nodes.remove(node)
        del s.nodeAddedWithSegId[node]
        s.__schedule(segId)

    def currentSchedule(s, node, segId):
        if node not in s.nodes:
            raise Exception("Node not in the group")
        if segId not in s.schedules:
            return
        if segId < s.nodeAddedWithSegId[node]:
            return
        downloader = s.schedules[segId]
        return downloader

    def isNeighbour(s, node):
        return node in s.nodeAddedWithSegId

    def isSuitable(self, node):
        if not self.network: return True
        for n in self.nodes:
            if not self.network.isClose(node.networkId, n.networkId):
                return False
        return True

SPEED_TOLARANCE_PERCENT = 0

class GroupManager():
    def __init__(self, peersPerGroup = 3, defaultQL = 3, videoInfo = None, network = None):
        self.groups = {}
        self.peers = {}
        self.peersPerGroup = peersPerGroup
        self.defaultQL = defaultQL
        self.videoInfo = videoInfo
        self.network = network

    def add(s, node, segId = 0, ql = -1):
        ql = s.defaultQL if ql < 0 else ql

        conn = node.connectionSpeedBPS
        
        if s.videoInfo:
            connQl = ql
            connTol = conn * (1 + SPEED_TOLARANCE_PERCENT/100.0)
            while connQl > 0:
                if connTol >= s.videoInfo.bitrates[connQl]:
                    break
                connQl -= 1
            if ql != connQl:
                print("assiging ql:", connQl, "instead of", ql)
            ql = connQl


        group = None
        for grp in s.groups.get(ql, []):
            assert grp.qualityLevel == ql
            if grp.numNodes() < s.peersPerGroup and grp.isSuitable(node):
                group = grp
                break

        if not group:
            group = Group(ql, s.network)
            grps = s.groups.setdefault(ql, [])
            grps.append(group)

        s.peers[node] = group
        group.add(node, segId)

    def remove(s, node, segId = 0):
        if node not in s.peers:
            return
        grp = s.peers[node]
        grp.remove(node, segId)
#         if grp.numNodes() == 0:
#             s.groups.remove(grp)
        del s.peers[node]

    def currentSchedule(s, node, segId):
        if node not in s.peers:
            return
        return s.peers[node].currentSchedule(node, segId)

    def isNeighbour(s, me, node):
        if me not in s.peers:
            return False
        return s.peers[me].isNeighbour(node)

    def getQualityLevel(s, node):
        if node not in s.peers:
            raise Exception("node not found")
        return s.peers[node].qualityLevel

    def getRtt(self, node1, node2):
        return self.network.getRtt(node1.networkId, node2.networkId)

    def transmissionTime(self, node1, node2, size):
        if not self.network:
            raise Exception("No p2p")
        return self.network.transmissionTime(node1.networkId, node2.networkId, size)

