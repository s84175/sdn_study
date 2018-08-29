#-*-coding:utf8-*-
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import tcp
from ryu.lib.packet import ether_types
from ryu.lib.packet import arp
from ryu.topology import event, switches
from ryu.topology.api import get_link
import networkx as nx
G = nx.DiGraph()
class SHORTPATH(app_manager.RyuApp):
     OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
     def __init__(self, *args, **kwargs):
  	 super(SHORTPATH, self).__init__(*args, **kwargs)
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


     # mac位址學習
     def mac_learning(self, dpid, src,dst, in_port):
         self.mac_to_port.setdefault(dpid, {})
	 #字典是否存在交換機信息
         if src in self.mac_to_port[dpid]:
	     #如果存在則in_port是否不一樣
             if in_port != self.mac_to_port[dpid][src]:
		 #如果in_port不一樣則發生arp風暴 
                 return False
	 #不存在則添加
         else:
             	self.mac_to_port[dpid][src] = in_port
             	return True


     #ryu自帶發現拓撲（執行程式時需加--observe-links）
     def get_topo(self,ev,dpid,src,in_port):
        links_list = get_link(self.topology_api_app, None)
        for link in links_list:
                G.add_edges_from([(link.src.dpid, link.dst.dpid,                                                     {'port': link.src.port_no})])
	if src not in G.nodes():
		G.add_nodes_from([src])
		G.add_edges_from([(src,dpid,{'port':in_port})])
		G.add_edges_from([(dpid,src,{'port':in_port})])
	if dpid not in G.nodes():
		G.add_nodes_from(dpid)
 

     @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER) 
     def _packet_in_handler(self, ev):
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
	 for p in pkt.protocols:
                print("the protocol is",p.protocol_name)
         dst = eth.dst
         src = eth.src
         dpid = datapath.id
         self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)
         self.mac_learning(dpid, src,dst, in_port)
	 self.get_topo(ev,dpid,src,in_port)
	 #最短路徑算法
         if dst in G.nodes():
         	print '尋找最短路徑'
                actions=[]
                path=nx.shortest_path(G,source=src,target=dst)
                print 'path:',path
                next = path[path.index(dpid) + 1]
                out_port = G[dpid][next]['port']
                print 'out_port:',out_port
                actions.append(parser.OFPActionOutput(out_port))
         else:
	     #將arp風暴封包進行丟包動作
             if self.mac_learning(dpid, src,dst, in_port) is False:
		 print 'arp風暴丟棄'
		 print 'drop:',dpid,':',src,':',dst,':',in_port
		 actions = []
                 out_port = ofproto.OFPPC_NO_RECV
		 actions.append(parser.OFPActionOutput(out_port))
             else:
		 print 'flooding'
	  	 actions = [] 
                 out_port = ofproto.OFPP_FLOOD
		 actions.append(parser.OFPActionOutput(out_port))
         actions = [parser.OFPActionOutput(out_port)]
         if out_port != ofproto.OFPP_FLOOD:
             match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
             if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                 self.add_flow(datapath, 10, match, actions, msg.buffer_id)
                 return
             else:
                 self.add_flow(datapath, 10, match, actions)
         data = None
         if msg.buffer_id == ofproto.OFP_NO_BUFFER:
             data = msg.data
         out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                   in_port=in_port, actions=actions, data=data)
         datapath.send_msg(out)
