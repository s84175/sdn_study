#-*-coding:utf8-*-
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.topology.api import get_link
import networkx as nx
G = nx.DiGraph()
class multipath(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(multipath, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
	self.topology_api_app = self
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)


    #判斷是否爲風暴
    def mac_learning(self,dpid,src,dst,in_port):
	self.mac_to_port.setdefault(dpid,{})
	#字典是否存在交換機信息
	if src in self.mac_to_port[dpid]:
		#如果存在則判斷in_port是否不一樣
		if in_port!=self.mac_to_port[dpid][src]:
			#如果in_port不一樣則發生arp風暴 
			return False
	#不存在則添加
	else:
		self.mac_to_port[dpid][src]=in_port
		return True


	#取得完整拓撲
    def get_topo(self,src,dpid,in_port):
        links_list = get_link(self.topology_api_app,None)
        for link in links_list:
                G.add_edges_from([(link.src.dpid,link.dst.dpid,{'port':link.src.port_no})])
        if src not in G.nodes():
                G.add_nodes_from(src)
                G.add_edges_from([(src,dpid,{'port':in_port})])
                G.add_edges_from([(dpid,src,{'port':in_port})])
        if dpid not in G.nodes():
                G.add_nodes_from(dpid)


	#這裡使用組表來做多路徑的轉發其中type=SELECT
    def add_group(self,dpid,dst,src,eth,in_port,msg,datapath,ofproto,parser):
    	actions = []
        buckets = []
        out_ports = []
	#計算兩點間多重路徑
        all_shortest_paths=list(nx.all_shortest_paths(G,source=src,target=dst))
        for path in all_shortest_paths:
        	if dpid in path:
                	next = path[path.index(dpid) + 1]
                        out_port = G[dpid][next]['port']
                       	if out_port not in out_ports:
                        	out_ports.append(out_port)
        if len(out_ports) ==1:
        	match = parser.OFPMatch(in_port=in_port,eth_src=src,eth_dst=dst)
                actions = [parser.OFPActionOutput(out_ports[0])]
        elif len(out_ports)!=1:
        	weight = 100
                group_id = dpid
                for out_port in out_ports:
                	actions.append([parser.OFPActionOutput(out_port)])
                for i in range(len(actions)):
                        buckets.append(parser.OFPBucket(weight=weight,actions=actions[i]))
                req = parser.OFPGroupMod(datapath,ofproto.OFPGC_ADD,ofproto.OFPGT_SELECT,group_id,buckets)
                datapath.send_msg(req)
                match = parser.OFPMatch(in_port=in_port,eth_src=src,eth_dst=dst)
                actions = [parser.OFPActionGroup(group_id=group_id)]
    	if msg.buffer_id != ofproto.OFP_NO_BUFFER:
        	self.add_flow(datapath,10,match,actions,msg.buffer_id)
        else:
                self.add_flow(datapath,10,match,actions)


	#arp處理
    def arp_handler(self,dpid,src,dst,in_port,msg,datapath,ofproto,parser):
	#如果arp會造成風暴則丟棄
    	if self.mac_learning(dpid,src,dst,in_port) is False:
                out_port = ofproto.OFPPC_NO_RECV
        elif dst == 'ff:ff:ff:ff:ff:ff':
        	out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
        	data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug("packet truncated: only %s of %s bytes",
                              ev.msg.msg_len, ev.msg.total_len)
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
             match = parser.OFPMatch(eth_type=eth.ethertype)
             actions = []
             self.add_flow(datapath, 10, match, actions)
             return
        if eth.ethertype == ether_types.ETH_TYPE_IPV6:
             match = parser.OFPMatch(eth_type=eth.ethertype)
             actions = []
             self.add_flow(datapath, 10, match, actions)
             return
	dst = eth.dst
        src = eth.src
        dpid = datapath.id
	self.mac_learning(dpid,src,dst,in_port)
        self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)
	self.get_topo(src,dpid,in_port)
        if dst in G.nodes:
		self.add_group(dpid,dst,src,eth,in_port,msg,datapath,ofproto,parser)				
        else:
		self.arp_handler(dpid,src,dst,in_port,msg,datapath,ofproto,parser)


