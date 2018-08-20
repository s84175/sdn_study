# -*- coding: UTF-8 -*-

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import vlan
from ryu.ofproto import ether
#新增vlanid,左邊為switch1,右邊為switch2
vlanid=[[2,3],[2,3]]
#新增端口d,左邊為switch1,右邊為switch2
#inport[dpid-1]
inport=[[1,2],[1,2]]
#設定trunk ,左邊為switch1,右邊為switch2
trunk=[4,4]
#交換機數目
switch_num = 2
class SimpleSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
	self.vlan_to_port = {1:{2:{},3:{}},2:{2:{},3:{}}}#儲存帶vlan的src:inport
	self.trunk_to_port={}
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install table-miss flow entry
        #
        # We specify NO BUFFER to max_len of the output action due to
        # OVS bug. At this moment, if we specify a lesser number, e.g.,
        # 128, OVS will send Packet-In with invalid buffer_id and
        # truncated packet data. In that case, we cannot output packets
        # correctly.
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})
	self.trunk_to_port.setdefault(dpid,{})
        self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)
	print("")
	#對有vlan的port所發出的封包添加vlan也就是802.1Q協定
	if in_port in inport[dpid-1]:
		vlan_tag=vlanid[dpid-1][in_port-1]
		pkt.add_protocol(vlan.vlan(vid=vlan_tag,
				ethertype=ether.ETH_TYPE_8021Q))
		print" added vlan id"
		self.vlan_to_port[dpid][vlan_tag][src] = in_port
	#設定trunk端口
	elif in_port in trunk:
		for i in range(0, switch_num):
			#跳過本地交換機
			if i == dpid - 1:
				continue
			#如果src無設定vlan經過trunk之後設定vlan為0
			else:
				if src in self.mac_to_port[i + 1]:
					vlan_tag = 0
					pkt.add_protocol(vlan.vlan(vid=vlan_tag,
							ethertype=ether.ETH_TYPE_8021Q))
					#更新協定
					eth = pkt.get_protocols(ethernet.ethernet)[0]
					dst = eth.dst
					src = eth.src
					self.trunk_to_port[dpid][src] = in_port
				else:
					
					for j in vlanid[i]:
						#經trunk再添加一次vlanid
						# j is vlan id
						if src in self.vlan_to_port[i + 1][j]:
							tport = self.vlan_to_port[i+1][j][src]
							vlan_tag = vlanid[i][tport-1]
							pkt.add_protocol(vlan.vlan(vid=vlan_tag,												ethertype=ether.ETH_TYPE_8021Q))
							eth = pkt.get_protocols(ethernet.ethernet)[0]
							dst = eth.dst
							src = eth.src
							self.trunk_to_port[dpid][src] = in_port
	else:
		self.mac_to_port[dpid][src] = in_port
	print('inport:',in_port)
	print('mac to port:',self.mac_to_port)
	print('vlan to port:' ,self.vlan_to_port)
	print('trunk to port:',self.trunk_to_port)
	#將src_vlan移出來
	src_vlan = 'NULL'
	for p in pkt.protocols:
		if p.protocol_name == 'vlan':
			actions = []
			src_vlan = p.vid
			print(" the src vlan is", src_vlan)
			f = parser.OFPMatchField.make(ofproto.OXM_OF_VLAN_VID
							, src_vlan)
			actions.append(parser.OFPActionPushVlan(33024))
			actions.append(parser.OFPActionSetField(f))
			data = None
			if msg.buffer_id == ofproto.OFP_NO_BUFFER:
				data = msg.data
			mod = parser.OFPPacketOut(datapath, buffer_id=msg.buffer_id, in_port=in_port, actions=actions,data=data)
		else:
			src_vlan = 'NULL'
	
	# for vlan tag 如果有vlanid
	if src_vlan != 'NULL' and src_vlan !=0:
		actions=[]
		#帶vlanid 的端口有四種可執行動作
		#第一種:目的端為相同vlan 則發往同台交換機相同vlan的port
		if dst in self.vlan_to_port[dpid][src_vlan]: 
           		out_port = self.vlan_to_port[dpid][src_vlan][dst]
			print('output:',self.vlan_to_port[dpid][src_vlan][dst])
		#第二種:目的端如果port為一般port則不轉發
		elif dst in self.mac_to_port[dpid] :
			out_port = ofproto.OFPP_IN_PORT
		#第三種:flooding
		elif dst == 'ff:ff:ff:ff:ff:ff':
			out_port= ofproto.OFPP_FLOOD
		#第四種:發往具有相同vlan的別台交換機端口
		else:
			out_port = trunk[dpid-1]
		actions.append(parser.OFPActionOutput(out_port))		
	elif src_vlan == 0:
		actions=[]
		if  dst in self.mac_to_port[dpid]:
			out_port = self.mac_to_port[dpid][dst]
		elif dst == 'ff:ff:ff:ff:ff:ff':
			out_port = ofproto.OFPP_FLOOD
		actions.append(parser.OFPActionOutput(out_port))	
		
				

	# for normal:
	else:
		actions=[]
		if dst in self.mac_to_port[dpid]:
			out_port = self.mac_to_port[dpid][dst]
			print('mac:',self.mac_to_port)
		else:
			out_port = ofproto.OFPP_FLOOD
		
	        actions.append(parser.OFPActionOutput(out_port))

	if src_vlan !='NULL':	
	
		if out_port != ofproto.OFPP_FLOOD:
                	match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src, vlan_vid=(0x1000 | src_vlan))
			actions.append(parser.OFPActionPopVlan())
                	self.add_flow(datapath, 1, match, actions)

	


        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)
