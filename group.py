
class Group():
    def __init__(s, ql):
        s.nodes = []
        s.schedules = {}
        s.segMents = 0
        s.nodeAddedWithSegId = {}
        s.qualityLevel = ql

    def __schedule(s, segId):
        nodeslist = list(s.nodes)
        nodeslist.sort(key=lambda x: - s.nodeAddedWithSegId[x])
        for i, segId in enumerate(range(segId, 1000)):
            x = i % len(nodeslist)
            s.schedules[segId] = nodeslist[x]

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

class GroupManager():
    def __init__(self, peersPerGroup = 3, defaultQL = 3):
        self.groups = []
        self.peers = {}
        self.peersPerGroup = peersPerGroup
        self.defaultQL = defaultQL

    def add(s, node, segId = 0, ql = -1):
        ql = s.defaultQL if ql < 0 else ql
        group = None
        for grp in s.groups:
            if grp.numNodes() < s.peersPerGroup and grp.qualityLevel == ql:
                group = grp
                break

        if not group:
            group = Group(ql)
            s.groups.append(group)

        group.add(node, segId)
        s.peers[node] = group

    def remove(s, node, segId = 0):
        if node not in s.peers:
            return
        grp = s.peers[node]
        grp.remove(node, segId)
        if grp.numNodes() == 0:
            s.groups.remove(grp)
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

