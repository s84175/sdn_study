#!/usr/bin/python

"""
This example shows how to create an empty Mininet object
(without a topology object) and add nodes to it manually.
"""

from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def emptyNet():

    "Create an empty network and add nodes to it."

    net = Mininet( controller=RemoteController )

    info( '*** Adding controller\n' )
    net.addController( 'c0',controller=RemoteController,ip='192.168.0.131' )

    info( '*** Adding hosts\n' )
    h1 = net.addHost( 'h1', ip='10.0.0.1' )
    h2 = net.addHost( 'h2', ip='10.0.0.2' )
    h3 = net.addHost( 'h3', ip='10.0.0.3' )
    h4 = net.addHost( 'h4', ip='10.0.0.4' )
    h5 = net.addHost( 'h5', ip='10.0.0.5' )
    h6 = net.addHost( 'h6', ip='10.0.0.6' )
#    h7 = net.addHost( 'h7', ip='10.0.0.7' )
#    h8 = net.addHost( 'h8', ip='10.0.0.8' )
#    h9 = net.addHost( 'h9', ip='10.0.0.9' )
#    h10 = net.addHost( 'h10', ip='10.0.0.10' )
    

    info( '*** Adding switch\n' )
    s1 = net.addSwitch( 's1' )
    s2 = net.addSwitch( 's2' )

    info( '*** Creating links\n' )
    net.addLink( h1, s1 ,1,1)
    net.addLink( h2, s1 ,1,2)
    net.addLink( h3, s1 ,1,3)
    net.addLink( h4, s2 ,1,1)
    net.addLink( h5, s2 ,1,2)
    net.addLink( h6, s2 ,1,3)
#    net.addLink( h6, s2 ,1,1)
#    net.addLink( h7, s2 ,1,2)
#    net.addLink( h8, s2 ,1,3)
#    net.addLink( h9, s2 ,1,4)
#    net.addLink( h10, s2 ,1,5)
    net.addLink( s1, s2 ,4,4)

   # net.addLink( h7, s1 )
    info( '*** Starting network\n')
    net.start()

    info( '*** Running CLI\n' )
    CLI( net )

    info( '*** Stopping network' )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    emptyNet()
