from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import vlan
from ryu.ofproto import ether
vlanid=[[2,3],[2,3]]
vlan_ports=[[1,2],[1,2]]
normal_ports=[[3],[3]]
trunk_ports = [[4],[4]]

class SimpleSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
	self.trunk_to_port = {}
	self.vlan_to_port = {}
	self.src_vid = {}
	for i in range(len(vlanid)):
		for j in vlanid[i]:
			self.vlan_to_port.setdefault(i+1,{})
			self.vlan_to_port[i+1].setdefault(j,{})
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


    def dict_learning(self,dpid):
        self.mac_to_port.setdefault(dpid, {})
        print ' mactoport:',self.mac_to_port
        self.trunk_to_port.setdefault(dpid,{})
        print 'trunktoport:',self.trunk_to_port


    def breakdown_trunk_ports(self,src,dpid,pkt,eth,dst):
    	if src in self.mac_to_port[dpid]:
        	vlan_tag = 0
                pkt.add_protocol(vlan.vlan(vid=vlan_tag,
                         ethertype=ether.ETH_TYPE_8021Q))
                eth = pkt.get_protocols(ethernet.ethernet)[0]
                dst = eth.dst
                src = eth.src
        elif src in self.src_vid:
                vlan_tag = self.src_vid[src]
                print 'src_vid:',vlan_tag
                pkt.add_protocol(vlan.vlan(vid=vlan_tag,                                                                 ethertype=ether.ETH_TYPE_8021Q))
                eth = pkt.get_protocols(ethernet.ethernet)[0]
                dst = eth.dst
                src = eth.src


    def add_vlan_tag_to_vlan_port(self,dpid,in_port,pkt,src):
    	vlan_tag=vlanid[dpid-1][in_port-1]
        pkt.add_protocol(vlan.vlan(vid=vlan_tag,
                  ethertype=ether.ETH_TYPE_8021Q))
        print" added vlan id"
        self.vlan_to_port[dpid][vlan_tag][src] = in_port
        print 'vlan_to_port:',self.vlan_to_port


    def set_src_vid(self):
	for key,value in self.vlan_to_port.items():
                for key1,value1 in value.items():
                        for key2,value2 in value1.items():
                                self.src_vid.setdefault(key2,key1)


    def breakdown_in_port(self,in_port,src,dpid,pkt,eth,dst):
        if in_port in normal_ports[dpid-1]:
                self.mac_to_port[dpid][src] = in_port

        elif in_port in trunk_ports[dpid-1]:
                self.trunk_to_port[dpid][src] = in_port
                self.breakdown_trunk_ports(src,dpid,pkt,eth,dst)

        elif in_port in vlan_ports[dpid-1]:
                self.add_vlan_tag_to_vlan_port(dpid,in_port,pkt,src)


    def vlan_to_trunk_port(self,dst,dpid,src_vlan,parser,ofproto,msg,datapath,in_port,src):
    	actions = []
        if dst in self.vlan_to_port[dpid][src_vlan]:
        	out_port = self.vlan_to_port[dpid][src_vlan][dst]
        elif dst in self.mac_to_port[dpid] :
                out_port = ofproto.OFPP_IN_PORT
        elif dst == 'ff:ff:ff:ff:ff:ff':
                out_port  = ofproto.OFPP_FLOOD
        else:
                out_port = trunk_ports[dpid-1][0]
        actions.append(parser.OFPActionOutput(out_port))
        if out_port != ofproto.OFPP_FLOOD:
        	match = parser.OFPMatch(in_port=in_port, eth_dst=dst,                                                           eth_src=src, vlan_vid=(0x1000 | src_vlan))
                if msg.buffer_id != ofproto.OFP_NO_BUFFER:
	                self.add_flow(datapath,10,match,actions,msg.buffer_id)
                else:
                        self.add_flow(datapath,10,match,actions)
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)


    def normal_to_trunk_port(self,dst,dpid,src_vlan,parser,ofproto,msg,datapath,in_port,src):
    	actions = []
        if dst in self.mac_to_port[dpid]:
 	       out_port = self.mac_to_port[dpid][dst]
        elif dst == 'ff:ff:ff:ff:ff:ff':
               out_port = ofproto.OFPP_FLOOD
        actions.append(parser.OFPActionOutput(out_port))

        if out_port != ofproto.OFPP_FLOOD:
               match = parser.OFPMatch(in_port=in_port, eth_dst=dst,                                                           eth_src=src, vlan_vid=(0x1000 | src_vlan))
               if msg.buffer_id != ofproto.OFP_NO_BUFFER:
	               self.add_flow(datapath,10,match,actions,msg.buffer_id)
               else:
                       self.add_flow(datapath,10,match,actions)
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)


    def normal_to_normal(self,dst,dpid,src_vlan,parser,ofproto,msg,datapath,in_port,src):
	actions = []
        if dst in self.mac_to_port[dpid]:
        	out_port = self.mac_to_port[dpid][dst]
        else :
                out_port = ofproto.OFPP_FLOOD
        actions.append(parser.OFPActionOutput(out_port))
        if out_port != ofproto.OFPP_FLOOD:
        	 match  = parser.OFPMatch(in_port=in_port,eth_src=src,eth_dst=dst)
                 if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                 	self.add_flow(datapath,10,match,actions,msg.buffer_id)
                 else:
                        self.add_flow(datapath,10,match,actions)
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

   
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        # If you hit this you might want to increase
        # the "miss_send_length" of your switch
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
	self.dict_learning(dpid)
        self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)
	self.breakdown_in_port(in_port,src,dpid,pkt,eth,dst)
	self.set_src_vid()

	src_vlan = 'NULL'
        for p in pkt.protocols:
                print("the protocol is",p.protocol_name)
		if p.protocol_name == 'vlan':
			src_vlan = p.vid
		else :
			src_vlan = 'NULL'
	if src_vlan !='NULL' and src_vlan !=0:
		self.vlan_to_trunk_port(dst,dpid,src_vlan,parser,ofproto,msg,datapath,in_port,src)
	elif src_vlan == 0:
		self.normal_to_trunk_port(dst,dpid,src_vlan,parser,ofproto,msg,datapath,in_port,src)
	else :
		self.normal_to_normal(dst,dpid,src_vlan,parser,ofproto,msg,datapath,in_port,src)
